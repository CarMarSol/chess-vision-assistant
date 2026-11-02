"""Install the bundled Chess Vision Assistant application on Windows."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
import zipfile

APP_NAME = "ChessVisionAssistant"
MARKER = ".chess-vision-install.json"
DEFAULT_ROOT = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / APP_NAME
RENAME_ATTEMPTS = 10
RENAME_RETRY_DELAY = 0.4


def _resource(name: str) -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / name


def _manifest(manifest: Path) -> dict:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data.get("sha256"), str) or len(data["sha256"]) != 64:
        raise ValueError("Manifest SHA256 inválido")
    if not isinstance(data.get("version"), str):
        raise ValueError("Manifest sin versión válida")
    return data


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_member(name: str) -> tuple[str, ...]:
    if not name or "\\" in name or name.startswith("/") or ":" in name:
        raise ValueError(f"Ruta insegura en el paquete: {name!r}")
    parts = name.rstrip("/").split("/")
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise ValueError(f"Ruta insegura en el paquete: {name!r}")
    return tuple(parts)


def _validated_entries(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, tuple[str, ...]]]:
    entries = []
    names: set[str] = set()
    for info in archive.infolist():
        parts = _safe_member(info.filename)
        key = "/".join(parts).casefold()
        if key in names:
            raise ValueError(f"Ruta duplicada en el paquete: {info.filename}")
        names.add(key)
        mode = info.external_attr >> 16
        dos_attrs = info.external_attr & 0xFFFF
        if stat.S_ISLNK(mode) or (dos_attrs & 0x400):
            raise ValueError(f"Enlace o punto de reanálisis no permitido: {info.filename}")
        file_type = stat.S_IFMT(mode)
        if file_type and file_type not in (stat.S_IFREG, stat.S_IFDIR):
            raise ValueError(f"Tipo de archivo no permitido: {info.filename}")
        entries.append((info, parts))
    required = {"chessvisionassistant.exe"}
    found = {"/".join(parts).casefold() for info, parts in entries if not info.is_dir()}
    if not required <= found or not ({"bin/stockfish.exe", "_internal/bin/stockfish.exe"} & found):
        raise ValueError("El paquete no contiene ChessVisionAssistant.exe y bin/stockfish.exe")
    return entries


def _reject_reparse_chain(path: Path) -> None:
    """Reject junctions/symlinks in an existing destination path chain."""
    path = Path(os.path.abspath(path))
    for candidate in (path, *path.parents):
        if candidate.exists() and (candidate.is_symlink() or getattr(candidate.stat(), "st_file_attributes", 0) & 0x400):
            raise ValueError(f"No se admite una carpeta de reanálisis: {candidate}")


def _owned(root: Path) -> dict | None:
    marker = root / MARKER
    if not root.exists():
        return None
    _reject_reparse_chain(root)
    if not root.is_dir():
        raise ValueError(f"El destino no es una carpeta: {root}")
    _reject_tree_reparse(root)
    if not marker.is_file():
        raise FileExistsError(f"La carpeta ya existe y no pertenece a la aplicación: {root}")
    data = json.loads(marker.read_text(encoding="utf-8"))
    if data.get("app") != APP_NAME or data.get("owned") is not True:
        raise ValueError(f"El marcador de propiedad no es válido: {root}")
    expected_root = os.path.normcase(os.path.abspath(root))
    marker_root = data.get("install_root")
    if not isinstance(marker_root, str) or os.path.normcase(os.path.abspath(marker_root)) != expected_root:
        raise ValueError(f"El marcador no corresponde a esta ruta de instalación: {root}")
    return data


def _reject_tree_reparse(root: Path) -> None:
    for current, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(current) / name
            if path.is_symlink() or getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0) & 0x400:
                raise ValueError(f"No se admite contenido de reanálisis en la instalación: {path}")


def _inside_parent(path: Path, parent: Path) -> Path:
    target = Path(os.path.abspath(path))
    expected_parent = Path(os.path.abspath(parent))
    if target.parent != expected_parent or target == expected_parent:
        raise ValueError(f"Ruta fuera del directorio seguro: {target}")
    return target


def _remove_tree(path: Path, parent: Path) -> None:
    target = _inside_parent(path, parent)
    if target.exists():
        _reject_reparse_chain(target)
        _reject_tree_reparse(target)
        shutil.rmtree(target)


def _replace_with_retry(source: Path, destination: Path) -> None:
    """Retry only brief Windows sharing/access locks during an atomic rename."""
    for attempt in range(RENAME_ATTEMPTS):
        try:
            os.replace(source, destination)
            return
        except OSError as exc:
            winerror = getattr(exc, "winerror", None)
            if not isinstance(exc, PermissionError) and winerror not in (5, 32, 33):
                raise
            if attempt == RENAME_ATTEMPTS - 1:
                raise
            time.sleep(RENAME_RETRY_DELAY)


def _extract(archive: zipfile.ZipFile, entries, destination: Path) -> None:
    for info, parts in entries:
        target = destination.joinpath(*parts)
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, target.open("xb") as output:
            shutil.copyfileobj(source, output)


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def create_shortcuts(exe: Path, desktop: Path | None = None, start_menu: Path | None = None) -> None:
    """Create standard shortcuts through PowerShell and WScript.Shell."""
    if os.name != "nt":
        return
    args = []
    if desktop is None or start_menu is None:
        args.append("$shell = New-Object -ComObject WScript.Shell")
        desktop_expr = "[Environment]::GetFolderPath('DesktopDirectory')" if desktop is None else _ps_quote(str(desktop))
        menu_expr = "$shell.SpecialFolders('Programs')" if start_menu is None else _ps_quote(str(start_menu))
    else:
        desktop_expr, menu_expr = _ps_quote(str(desktop)), _ps_quote(str(start_menu))
        args.append("$shell = New-Object -ComObject WScript.Shell")
    exe = Path(exe)
    exe_expr = _ps_quote(str(exe))
    uninstaller_expr = _ps_quote(str(exe.parent / "Desinstalar.cmd"))
    args.extend([
        f"$exe = {exe_expr}; $uninstaller = {uninstaller_expr}",
        f"$desktop = {desktop_expr}; $menu = {menu_expr}",
        "$locations = @(@{ Dir = $desktop; Name = 'Chess Vision Assistant.lnk'; Target = $exe }, @{ Dir = $menu; Name = 'Chess Vision Assistant.lnk'; Target = $exe }, @{ Dir = $menu; Name = 'Desinstalar Chess Vision Assistant.lnk'; Target = $uninstaller })",
        "foreach ($item in $locations) { $dir = [string]$item.Dir; New-Item -ItemType Directory -Force -Path $dir | Out-Null; $link = $shell.CreateShortcut((Join-Path $dir $item.Name)); $link.TargetPath = [string]$item.Target; $link.WorkingDirectory = Split-Path ([string]$item.Target); $link.Save() }",
    ])
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "; ".join(args)],
                   check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def install(payload: Path, manifest: Path, install_root: Path | None = None,
            shortcuts: bool = True) -> Path:
    payload, manifest = Path(payload), Path(manifest)
    root = Path(install_root) if install_root is not None else DEFAULT_ROOT
    data = _manifest(manifest)
    if _digest(payload).lower() != data["sha256"].lower():
        raise ValueError("La verificación SHA256 del paquete ha fallado")
    with zipfile.ZipFile(payload) as archive:
        entries = _validated_entries(archive)
        parent = Path(os.path.abspath(root)).parent
        target = _inside_parent(root, parent)
        _reject_reparse_chain(parent)
        old_owner = _owned(target)
        parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f".{APP_NAME}-stage-", dir=parent))
        backup = parent / f".{APP_NAME}-backup-{os.getpid()}"
        try:
            _extract(archive, entries, stage)
            exe = stage / f"{APP_NAME}.exe"
            if not exe.is_file() or not any((stage / rel).is_file() for rel in
                                            (Path("bin/stockfish.exe"), Path("_internal/bin/stockfish.exe"))):
                raise ValueError("El paquete extraído no supera la validación")
            script_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
            for name in ("uninstall.ps1", "Desinstalar.cmd"):
                source = script_dir / name
                if source.is_file():
                    shutil.copy2(source, stage / name)
            (stage / MARKER).write_text(json.dumps({"app": APP_NAME, "owned": True,
                                                    "version": data["version"],
                                                    "install_root": str(target)}, indent=2), encoding="utf-8")
            if backup.exists():
                raise FileExistsError(f"Existe una copia temporal inesperada: {backup}")
            if old_owner is not None:
                _replace_with_retry(target, backup)
            try:
                _replace_with_retry(stage, target)
            except Exception as swap_error:
                if backup.exists():
                    try:
                        _replace_with_retry(backup, target)
                    except Exception as rollback_error:
                        raise RuntimeError(
                            f"El cambio falló y no se pudo restaurar la instalación previa; "
                            f"la copia anterior sigue en {backup}. Error del cambio: {swap_error}"
                        ) from rollback_error
                raise
            if backup.exists():
                _remove_tree(backup, parent)
        except Exception:
            if stage.exists():
                try:
                    _remove_tree(stage, parent)
                except Exception:
                    pass
            raise
    result = target / f"{APP_NAME}.exe"
    if shortcuts:
        try:
            create_shortcuts(result)
        except (OSError, subprocess.SubprocessError):
            pass
    return result


def _gui() -> int:
    root = tk.Tk()
    root.title("Chess Vision Assistant Setup")
    root.resizable(False, False)
    frame = ttk.Frame(root, padding=18)
    frame.grid()
    ttk.Label(frame, text="Instala Chess Vision Assistant para tu usuario.\nInstall Chess Vision Assistant for your user.",
              justify="center").grid(row=0, column=0, padx=8, pady=(0, 12))
    status = tk.StringVar(value="Listo para instalar · Ready to install")
    ttk.Label(frame, textvariable=status, wraplength=360).grid(row=1, column=0, pady=5)
    progress = ttk.Progressbar(frame, mode="indeterminate", length=330)
    progress.grid(row=2, column=0, pady=8)
    button = ttk.Button(frame, text="Instalar / Install")
    button.grid(row=3, column=0, pady=(8, 0))
    events: queue.Queue = queue.Queue()
    running = False
    poll_scheduled = False

    def schedule_poll() -> None:
        nonlocal poll_scheduled
        if running and not poll_scheduled:
            poll_scheduled = True
            root.after(100, poll)

    def start() -> None:
        nonlocal running
        if running:
            return
        running = True
        button.state(["disabled"])
        progress.start(10)
        status.set("Instalando… · Installing…")
        def worker():
            try:
                events.put((True, install(_resource("payload.zip"), _resource("payload.json"))))
            except Exception as exc:
                events.put((False, str(exc)))
        threading.Thread(target=worker, daemon=True).start()
        schedule_poll()

    def poll() -> None:
        nonlocal running, poll_scheduled
        poll_scheduled = False
        if not running:
            return
        try:
            success, value = events.get_nowait()
        except queue.Empty:
            schedule_poll()
            return
        running = False
        progress.stop()
        button.state(["!disabled"])
        if success:
            status.set("Instalación completada · Installation complete")
            if messagebox.askyesno("Chess Vision Assistant", "Instalación completada. ¿Abrir ahora?\nInstallation complete. Open now?"):
                os.startfile(str(value))
        else:
            status.set("No se pudo completar · Installation failed")
            messagebox.showerror("Chess Vision Assistant", value)

    def close() -> None:
        if running:
            messagebox.showinfo("Chess Vision Assistant", "La instalación sigue en curso. Espera a que termine.\nInstallation is still running. Please wait.")
            return
        root.destroy()

    button.configure(command=start)
    root.protocol("WM_DELETE_WINDOW", close)
    root.mainloop()
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--no-shortcuts", action="store_true")
    parser.add_argument("--install-dir", type=Path)
    args = parser.parse_args(argv)
    if args.silent:
        try:
            install(_resource("payload.zip"), _resource("payload.json"), args.install_dir,
                    shortcuts=not args.no_shortcuts)
            return 0
        except Exception as exc:
            print(f"Instalación fallida: {exc}", file=sys.stderr)
            return 1
    return _gui()


if __name__ == "__main__":
    raise SystemExit(main())
