from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys

PROJECT_ROOT = Path(os.path.abspath(__file__)).parent


def verify_stockfish_bundle(stockfish_bin):
    """Reject any engine or source bundle that differs from the documented release."""
    source_dir = Path(PROJECT_ROOT) / "third_party" / "stockfish"
    manifest = json.loads((source_dir / "provenance.json").read_text(encoding="utf-8"))
    if hashlib.sha256(Path(stockfish_bin).read_bytes()).hexdigest() != manifest["binary_sha256"]:
        raise ValueError("Stockfish no coincide con el binario oficial documentado. Actualiza sus fuentes y provenance.json antes de distribuirlo.")
    for name in ("stockfish-17-source.zip", "Copying.txt", "AUTHORS"):
        if hashlib.sha256((source_dir / name).read_bytes()).hexdigest() != manifest["files"][name]:
            raise ValueError(f"Las fuentes o avisos de Stockfish no coinciden con provenance.json: {name}")
    return source_dir


def verify_public_templates():
    public = Path(PROJECT_ROOT) / "scripts" / "public_piece_templates.py"
    packaged = Path(PROJECT_ROOT) / "chess_vision" / "vision" / "piece_templates.py"
    if not public.is_file() or not packaged.is_file() or packaged.read_bytes() != public.read_bytes():
        raise ValueError("La compilación solo acepta las plantillas públicas verificadas de cburnett.")


def pyinstaller_environment():
    """Keep unrelated user PATH DLLs (for example a bundled Poppler ICU) out of analysis."""
    env = os.environ.copy()
    system_root = Path(env.get("SystemRoot", r"C:\Windows"))
    env["PATH"] = os.pathsep.join(str(path) for path in (
        system_root / "System32", system_root,
        system_root / "System32" / "Wbem",
    ))
    for name in ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        env.pop(name, None)
    return env


def build(output_dir=None, work_dir=None):
    root = Path(PROJECT_ROOT)
    stockfish_bin = root / "bin" / "stockfish.exe"
    openings_bin = root / "data" / "openings.bin"
    output = Path(output_dir) if output_dir else root / "dist"
    work = Path(work_dir) if work_dir else root / "build"

    if not stockfish_bin.is_file():
        raise FileNotFoundError(f"No se encuentra Stockfish en: {stockfish_bin}")
    verify_stockfish_bundle(stockfish_bin)
    verify_public_templates()

    if not openings_bin.is_file():
        from chess_vision.engine.opening_book import compile_polyglot_book
        compile_polyglot_book(str(openings_bin))

    third_party_dir = root / "third_party"
    templates_dir = root / "data" / "templates"
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "ChessVisionAssistant", "--distpath", str(output),
        "--workpath", str(work), "--specpath", str(work),
        f"--add-data={stockfish_bin};bin",
        f"--add-data={openings_bin};data", f"--add-data={templates_dir};data/templates",
        "--hidden-import=PySide6.QtSvg", "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui", "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=chess", "--hidden-import=chess.polyglot", "--hidden-import=chess.engine",
        "--hidden-import=mss", "--hidden-import=cv2", "--hidden-import=numpy",
        str(root / "main.py"),
    ]
    result = subprocess.run(cmd, cwd=root, env=pyinstaller_environment())
    if result.returncode:
        raise subprocess.CalledProcessError(result.returncode, cmd)

    app_dir = output / "ChessVisionAssistant"
    # Keep human-readable source and license material at the portable app root.
    shutil.copytree(third_party_dir, app_dir / "third_party", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return app_dir


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, help="PyInstaller distpath; defaults to ./dist")
    parser.add_argument("--work-dir", type=Path, help="Isolated PyInstaller work/spec path; defaults to ./build")
    args = parser.parse_args(argv)
    app_dir = build(args.output_dir, args.work_dir)
    print(f"Compilación completada: {app_dir / 'ChessVisionAssistant.exe'}")


if __name__ == "__main__":
    main()
