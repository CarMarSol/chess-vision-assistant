"""Build verified Windows portable and per-user setup artifacts from public source."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import distribution
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from scripts.prepare_publication import prepare_publication
from build_exe import pyinstaller_environment

VERSION = "1.0.0-beta.1"
APP_NAME = "ChessVisionAssistant"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _zip_tree(folder: Path, archive_path: Path, *, include_parent: bool) -> None:
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                arcname = path.relative_to(folder.parent if include_parent else folder).as_posix()
                archive.write(path, arcname)


def _copy_runtime_licenses(app_dir: Path, source: Path) -> None:
    shutil.copy2(source / "LICENSE", app_dir / "LICENSE")
    shutil.copy2(source / "THIRD_PARTY_NOTICES.md", app_dir / "THIRD_PARTY_NOTICES.md")
    licenses = app_dir / "licenses"
    (licenses).mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "licenses" / "LGPL-3.0.txt", licenses / "LGPL-3.0.txt")
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    python_version = ".".join(map(str, sys.version_info[:3]))
    python_license_dir = licenses / f"Python-{python_version}"
    python_license_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(python_license, python_license_dir / "LICENSE.txt")
    import PySide6
    from PySide6.QtCore import qVersion
    import tkinter
    tk_license_files = sorted((Path(sys.base_prefix) / "tcl").glob("tk*/license.terms"))
    if not tk_license_files:
        raise FileNotFoundError("No se encontró license.terms de Tcl/Tk del Python que empaqueta el setup")
    for path in tk_license_files:
        target = licenses / f"Tcl-Tk-{path.parent.name[2:]}" / "license.terms"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
    packages = ("PySide6", "PySide6-Essentials", "PySide6-Addons", "shiboken6",
                "opencv-python", "numpy", "mss", "chess")
    for package in packages:
        dist = distribution(package)
        for relative in dist.files or ():
            name = relative.name.lower()
            if name in {"license", "license.txt", "license.md", "copying", "copying.txt", "notice", "notice.txt"} or name.startswith("license-"):
                path = dist.locate_file(relative)
                if path.is_file():
                    target = licenses / f"{dist.metadata['Name']}-{dist.version}" / relative.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
    sources = licenses / "SOURCES.txt"
    sources.write_text(
        f"Runtime versions\nPython {python_version}; Tcl {tkinter.TclVersion}; Tk {tkinter.TkVersion}; "
        f"PySide6 {PySide6.__version__}; Qt {qVersion()}\n\n"
        "Qt for Python source (matching version tag):\n"
        f"https://code.qt.io/cgit/pyside/pyside-setup.git/tree/?h={PySide6.__version__}\n"
        "Qt source modules (matching Qt version tag):\n"
        f"https://code.qt.io/cgit/qt/qtbase.git/tree/?h=v{qVersion()}\n"
        f"https://code.qt.io/cgit/qt/qtsvg.git/tree/?h=v{qVersion()}\n"
        f"Application source archive: source/{APP_NAME}-{VERSION}-source.zip\n"
        "PySide6 source-build guidance: https://doc.qt.io/qtforpython-6/building_from_source/index.html\n"
        "Relink guidance: https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html\n"
        "GNU LGPL-3.0 text is included as licenses/LGPL-3.0.txt; official source:\n"
        "https://www.gnu.org/licenses/lgpl-3.0.txt\n",
        encoding="utf-8",
    )


def _include_public_source(app_dir: Path, public_archive: Path) -> Path:
    target = app_dir / "source" / f"{APP_NAME}-{VERSION}-source.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(public_archive, target)
    if sha256(target) != sha256(public_archive):
        raise OSError("El ZIP de fuentes públicas cambió al copiarse al paquete")
    return target


def _setup_command(payload: Path, manifest: Path, installer: Path, output: Path, work: Path) -> list[str]:
    return [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", f"{APP_NAME}-{VERSION}-Windows-Setup", "--distpath", str(output),
        "--workpath", str(work), "--specpath", str(work),
        f"--add-data={payload};.", f"--add-data={manifest};.",
        f"--add-data={installer / 'uninstall.ps1'};.",
        f"--add-data={installer / 'Desinstalar.cmd'};.",
        str(installer / "install_app.py"),
    ]


def _write_checksums(output: Path) -> None:
    names = (f"{APP_NAME}-{VERSION}-Windows-Setup.exe", f"{APP_NAME}-{VERSION}-Windows-Portable.zip")
    (output / "SHA256SUMS.txt").write_text(
        "".join(f"{sha256(output / name)}  {name}\n" for name in names), encoding="ascii",
    )


def build_release(source: Path, output: Path, stockfish_path: Path | None = None) -> tuple[Path, Path]:
    source, output = source.resolve(), output.resolve()
    public_templates = source / "scripts" / "public_piece_templates.py"
    app_templates = source / "chess_vision" / "vision" / "piece_templates.py"
    if not public_templates.is_file() or not app_templates.is_file() or app_templates.read_bytes() != public_templates.read_bytes():
        raise ValueError("El release requiere el módulo público de plantillas cburnett verificado; se rechaza una copia distinta.")
    if output.exists():
        raise FileExistsError(f"El destino ya existe; elige una carpeta nueva: {output}")

    engine = Path(stockfish_path).resolve() if stockfish_path else source / "bin" / "stockfish.exe"
    if not engine.is_file():
        raise FileNotFoundError(f"Falta el binario Stockfish verificado: {engine}")
    output.parent.mkdir(parents=True, exist_ok=True)

    setup_name = f"{APP_NAME}-{VERSION}-Windows-Setup.exe"
    portable_name = f"{APP_NAME}-{VERSION}-Windows-Portable.zip"
    with tempfile.TemporaryDirectory(prefix="chess-vision-build-", dir=output.parent) as temporary:
        work = Path(temporary)
        public_source, public_archive = prepare_publication(source, work / "public-source")
        staged_engine = public_source / "bin" / "stockfish.exe"
        staged_engine.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(engine, staged_engine)
        if engine.stat().st_size <= 0:
            raise ValueError("El ejecutable de Stockfish está vacío")

        app_dir = output / APP_NAME
        subprocess.run([
            sys.executable, str(public_source / "build_exe.py"),
            "--output-dir", str(output), "--work-dir", str(work / "pyinstaller-app"),
        ], cwd=public_source, check=True)
        if not (app_dir / f"{APP_NAME}.exe").is_file():
            raise FileNotFoundError(f"PyInstaller no produjo {app_dir / (APP_NAME + '.exe')}")
        _copy_runtime_licenses(app_dir, public_source)
        _include_public_source(app_dir, public_archive)

        (app_dir / "README-Portable.txt").write_text(
            "Chess Vision Assistant (portable)\n\n"
            "Ejecuta ChessVisionAssistant.exe. No requiere Python ni conexión a Internet.\n"
            "Puedes mover o borrar esta carpeta; no instala componentes en el sistema.\n",
            encoding="utf-8",
        )
        portable = output / portable_name
        _zip_tree(app_dir, portable, include_parent=True)

        payload = work / "payload.zip"
        _zip_tree(app_dir, payload, include_parent=False)
        payload_manifest = work / "payload.json"
        payload_manifest.write_text(json.dumps({"sha256": sha256(payload), "version": VERSION}, indent=2) + "\n",
                                    encoding="utf-8")
        installer = public_source / "installer"
        setup = output / setup_name
        setup_work = work / "pyinstaller-setup"
        setup_work.mkdir()
        setup_cmd = _setup_command(payload, payload_manifest, installer, output, setup_work)
        subprocess.run(setup_cmd, cwd=public_source, env=pyinstaller_environment(), check=True)
        produced = output / f"{APP_NAME}-{VERSION}-Windows-Setup.exe"
        if produced != setup and produced.exists():
            os.replace(produced, setup)
        if not setup.is_file():
            raise FileNotFoundError(f"PyInstaller no produjo {setup}")

    _write_checksums(output)
    return output / setup_name, output / portable_name


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1],
                        help="Copia de código; puede ser la publicación pública ya exportada")
    parser.add_argument("--output", type=Path, help="Directorio nuevo de artefactos")
    parser.add_argument("--stockfish-path", type=Path, help="Binario local; debe coincidir con provenance.json")
    args = parser.parse_args(argv)
    output = args.output or args.source / "publicacion" / "windows-release"
    setup, portable = build_release(args.source, output, args.stockfish_path)
    print(f"Setup: {setup}\nPortable: {portable}\nSHA256: {setup.parent / 'SHA256SUMS.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
