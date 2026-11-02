"""Small packaging checks that do not run PyInstaller."""
import hashlib
from pathlib import Path
import zipfile

import pytest

from scripts import build_windows_release as release


def test_setup_command_bundles_payload_and_uninstaller_without_console(tmp_path):
    installer = tmp_path / "installer"
    command = release._setup_command(tmp_path / "payload.zip", tmp_path / "payload.json", installer,
                                    tmp_path / "dist", tmp_path / "work")
    assert "--onefile" in command and "--windowed" in command
    assert f"--add-data={tmp_path / 'payload.zip'};." in command
    assert f"--add-data={tmp_path / 'payload.json'};." in command
    assert f"--add-data={installer / 'uninstall.ps1'};." in command
    assert f"--add-data={installer / 'Desinstalar.cmd'};." in command
    assert command[-1] == str(installer / "install_app.py")


def test_pyinstaller_environment_omits_external_dll_and_python_paths(monkeypatch):
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    monkeypatch.setenv("PATH", r"C:\foreign\dlls")
    monkeypatch.setenv("PYTHONPATH", r"C:\foreign\python")
    monkeypatch.setenv("QT_PLUGIN_PATH", r"C:\foreign\qt")
    env = release.pyinstaller_environment()
    assert env["PATH"] == r"C:\Windows\System32;C:\Windows;C:\Windows\System32\Wbem"
    assert "C:\\foreign" not in env["PATH"]
    assert "PYTHONPATH" not in env and "QT_PLUGIN_PATH" not in env


def test_release_zip_layout_excludes_python_caches_and_hashes_payload(tmp_path):
    app = tmp_path / "ChessVisionAssistant"
    (app / "_internal" / "bin").mkdir(parents=True)
    (app / "ChessVisionAssistant.exe").write_bytes(b"exe")
    (app / "_internal" / "bin" / "stockfish.exe").write_bytes(b"engine")
    cache = app / "_internal" / "__pycache__"
    cache.mkdir()
    (cache / "leak.pyc").write_bytes(b"cache")

    portable = tmp_path / "portable.zip"
    payload = tmp_path / "payload.zip"
    release._zip_tree(app, portable, include_parent=True)
    release._zip_tree(app, payload, include_parent=False)

    with zipfile.ZipFile(portable) as archive:
        assert "ChessVisionAssistant/ChessVisionAssistant.exe" in archive.namelist()
        assert "ChessVisionAssistant/_internal/bin/stockfish.exe" in archive.namelist()
        assert not any("__pycache__" in name or name.endswith(".pyc") for name in archive.namelist())
    with zipfile.ZipFile(payload) as archive:
        assert "ChessVisionAssistant.exe" in archive.namelist()
        assert "_internal/bin/stockfish.exe" in archive.namelist()
    assert len(release.sha256(payload)) == 64
    assert hashlib.sha256(payload.read_bytes()).hexdigest() == release.sha256(payload)


def test_public_source_archive_is_copied_intact_into_release(tmp_path):
    app = tmp_path / "ChessVisionAssistant"
    app.mkdir()
    public_source = tmp_path / "public-source.zip"
    public_source.write_bytes(b"sanitized public source")
    bundled = release._include_public_source(app, public_source)
    assert bundled.relative_to(app).as_posix() == "source/ChessVisionAssistant-1.0.0-beta.1-source.zip"
    assert release.sha256(bundled) == release.sha256(public_source)




def test_release_refuses_non_public_template_module_before_build(tmp_path):
    source = tmp_path / "source"
    module = source / "chess_vision/vision/piece_templates.py"
    public = source / "scripts/public_piece_templates.py"
    module.parent.mkdir(parents=True)
    public.parent.mkdir(parents=True)
    module.write_text("private templates", encoding="utf-8")
    public.write_text("public templates", encoding="utf-8")
    with pytest.raises(ValueError, match="plantillas cburnett"):
        release.build_release(source, tmp_path / "out")


def test_runtime_license_collection_includes_python_tk_and_qt_versions(tmp_path):
    from PySide6.QtCore import qVersion
    import PySide6
    import sys

    app = tmp_path / "ChessVisionAssistant"
    app.mkdir()
    source = Path(__file__).resolve().parents[1]
    release._copy_runtime_licenses(app, source)
    license_root = app / "licenses"
    assert (license_root / "LGPL-3.0.txt").read_bytes() == (source / "licenses/LGPL-3.0.txt").read_bytes()
    assert (license_root / f"Python-{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}/LICENSE.txt").is_file()
    assert list(license_root.glob("Tcl-Tk-*/license.terms"))
    assert (license_root / "SOURCES.txt").read_text(encoding="utf-8").find(
        f"PySide6 {PySide6.__version__}; Qt {qVersion()}"
    ) >= 0
    assert list(license_root.glob("opencv-python-*/LICENSE-3RD-PARTY.txt"))
