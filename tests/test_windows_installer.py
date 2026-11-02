import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from installer import install_app


class WindowsInstallerTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / ".installer-test-tmp"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.base = Path(self.temp.name)
        self.payload = self.base / "payload.zip"
        self.manifest = self.base / "payload.json"
        self._write_payload({
            "ChessVisionAssistant.exe": b"new executable",
            "bin/stockfish.exe": b"engine",
            "data/settings-default.json": b"{}",
        })

    def tearDown(self):
        self.temp.cleanup()

    def _write_payload(self, members, version="1.0.0-beta.1"):
        with zipfile.ZipFile(self.payload, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)
        self.manifest.write_text(json.dumps({
            "sha256": hashlib.sha256(self.payload.read_bytes()).hexdigest(),
            "version": version,
        }), encoding="utf-8")

    def test_installs_payload_and_preserves_appdata_profile(self):
        target = self.base / "Programs" / "ChessVisionAssistant"
        profile = self.base / "AppData" / "ChessVisionAssistant" / "settings.json"
        profile.parent.mkdir(parents=True)
        profile.write_text('{"language":"es"}', encoding="utf-8")
        result = install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertEqual(result, target / "ChessVisionAssistant.exe")
        self.assertEqual(result.read_bytes(), b"new executable")
        self.assertEqual((target / "bin" / "stockfish.exe").read_bytes(), b"engine")
        marker = json.loads((target / install_app.MARKER).read_text())
        self.assertEqual(marker["version"], "1.0.0-beta.1")
        self.assertEqual(marker["install_root"], str(target.resolve()))
        self.assertEqual(profile.read_text(encoding="utf-8"), '{"language":"es"}')

        self._write_payload({"ChessVisionAssistant.exe": b"updated", "bin/stockfish.exe": b"engine"}, version="1.0.1")
        updated = install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertEqual(updated.read_bytes(), b"updated")
        self.assertEqual(json.loads((target / install_app.MARKER).read_text())["version"], "1.0.1")
        self.assertEqual(profile.read_text(encoding="utf-8"), '{"language":"es"}')

    def test_bad_sha_does_not_touch_destination(self):
        target = self.base / "Programs" / "ChessVisionAssistant"
        self.manifest.write_text(json.dumps({"sha256": "0" * 64, "version": "1"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertFalse(target.parent.exists())

    def test_accepts_stockfish_in_pyinstaller_internal_tree(self):
        self._write_payload({"ChessVisionAssistant.exe": b"app", "_internal/bin/stockfish.exe": b"engine"})
        target = self.base / "Programs" / "ChessVisionAssistant"
        result = install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertTrue(result.is_file())
        self.assertEqual((target / "_internal" / "bin" / "stockfish.exe").read_bytes(), b"engine")

    def test_zip_traversal_is_rejected_before_extraction(self):
        self._write_payload({"ChessVisionAssistant.exe": b"app", "bin/stockfish.exe": b"sf", "../escape.txt": b"x"})
        target = self.base / "Programs" / "ChessVisionAssistant"
        with self.assertRaisesRegex(ValueError, "Ruta insegura"):
            install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertFalse((self.base / "escape.txt").exists())
        self.assertFalse(target.parent.exists())

    def test_zip_symlink_is_rejected(self):
        with zipfile.ZipFile(self.payload, "w") as archive:
            archive.writestr("ChessVisionAssistant.exe", b"app")
            archive.writestr("bin/stockfish.exe", b"sf")
            link = zipfile.ZipInfo("link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "outside")
        self.manifest.write_text(json.dumps({
            "sha256": hashlib.sha256(self.payload.read_bytes()).hexdigest(), "version": "1",
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Enlace"):
            install_app.install(self.payload, self.manifest, self.base / "Programs" / "ChessVisionAssistant",
                                shortcuts=False)

    def test_unmarked_existing_folder_is_untouched(self):
        target = self.base / "ChessVisionAssistant"
        target.mkdir()
        valuable = target / "mine.txt"
        valuable.write_text("keep", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertEqual(valuable.read_text(encoding="utf-8"), "keep")

    def test_marker_for_another_install_root_is_rejected_and_untouched(self):
        target = self.base / "ChessVisionAssistant"
        target.mkdir()
        marker = {"app": install_app.APP_NAME, "owned": True, "install_root": str(self.base / "Elsewhere")}
        (target / install_app.MARKER).write_text(json.dumps(marker), encoding="utf-8")
        valuable = target / "user-data.txt"
        valuable.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no corresponde"):
            install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertEqual(valuable.read_text(encoding="utf-8"), "keep")

    def test_failed_update_rolls_back_old_install(self):
        target = self.base / "ChessVisionAssistant"
        target.mkdir()
        (target / install_app.MARKER).write_text(json.dumps({
            "app": install_app.APP_NAME, "owned": True, "install_root": str(target.resolve()),
        }), encoding="utf-8")
        (target / "old.txt").write_text("old version", encoding="utf-8")
        replace = os.replace
        calls = 0

        def fail_stage_once(source, destination):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated staging swap failure")
            return replace(source, destination)

        with mock.patch.object(install_app.os, "replace", side_effect=fail_stage_once):
            with self.assertRaisesRegex(OSError, "simulated"):
                install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertEqual((target / "old.txt").read_text(encoding="utf-8"), "old version")
        self.assertFalse((target / "ChessVisionAssistant.exe").exists())
        self.assertEqual(list(target.parent.glob(".ChessVisionAssistant-stage-*")), [])

    def test_fresh_install_retries_one_windows_access_denied(self):
        target = self.base / "Programs" / "ChessVisionAssistant"
        replace = os.replace
        calls = 0

        def deny_once(source, destination):
            nonlocal calls
            calls += 1
            if calls == 1:
                error = PermissionError(5, "Access is denied")
                error.winerror = 5
                raise error
            return replace(source, destination)

        with mock.patch.object(install_app.os, "replace", side_effect=deny_once):
            result = install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertTrue(result.is_file())
        self.assertEqual(calls, 2)

    def test_permanent_swap_lock_fails_but_restores_previous_install(self):
        target = self.base / "Programs" / "ChessVisionAssistant"
        target.mkdir(parents=True)
        (target / install_app.MARKER).write_text(json.dumps({
            "app": install_app.APP_NAME, "owned": True, "install_root": str(target.resolve()),
        }), encoding="utf-8")
        (target / "old.txt").write_text("previous install", encoding="utf-8")
        replace = os.replace
        stage_attempts = 0

        def keep_stage_locked(source, destination):
            nonlocal stage_attempts
            if Path(source).name.startswith(f".{install_app.APP_NAME}-stage-"):
                stage_attempts += 1
                error = PermissionError(5, "Access is denied")
                error.winerror = 5
                raise error
            return replace(source, destination)

        with mock.patch.object(install_app.os, "replace", side_effect=keep_stage_locked), \
             mock.patch.object(install_app.time, "sleep") as sleep:
            with self.assertRaisesRegex(PermissionError, "Access is denied"):
                install_app.install(self.payload, self.manifest, target, shortcuts=False)
        self.assertEqual(stage_attempts, install_app.RENAME_ATTEMPTS)
        self.assertEqual(sleep.call_count, install_app.RENAME_ATTEMPTS - 1)
        self.assertEqual((target / "old.txt").read_text(encoding="utf-8"), "previous install")
        self.assertFalse((target / "ChessVisionAssistant.exe").exists())
        self.assertEqual(list(target.parent.glob(f".{install_app.APP_NAME}-stage-*")), [])

    @unittest.skipUnless(sys.platform == "win32", "Windows shortcut path behavior")
    def test_shortcut_creation_is_simulated_and_quotes_paths(self):
        exe = self.base / "O'Brien" / "ChessVisionAssistant.exe"
        with mock.patch.object(install_app.subprocess, "run") as run:
            install_app.create_shortcuts(exe, self.base / "Desktop", self.base / "Start Menu")
        run.assert_called_once()
        command = run.call_args.args[0]
        self.assertIn("O''Brien", command[-1])
        self.assertIn("Start Menu", command[-1])
        self.assertIn("Desinstalar Chess Vision Assistant.lnk", command[-1])
        self.assertIn("Desinstalar.cmd", command[-1])
        self.assertIn("ChessVisionAssistant.exe", command[-1])
        self.assertEqual(command[0], "powershell.exe")

    def test_gui_polls_success_and_error_once_per_attempt(self):
        class FakeRoot:
            def __init__(self):
                self.callbacks = []
                self.after_calls = 0
                self.close_handler = None
                self.destroy_calls = 0

            def title(self, *_args): pass
            def resizable(self, *_args): pass
            def protocol(self, _name, callback): self.close_handler = callback
            def after(self, _delay, callback):
                self.after_calls += 1
                self.callbacks.append(callback)
            def destroy(self): self.destroy_calls += 1
            def mainloop(self):
                for attempt in range(2):
                    button.command()
                    if attempt == 0:
                        self.close_handler()
                    while self.callbacks:
                        self.callbacks.pop(0)()

        class ImmediateThread:
            def __init__(self, target, daemon): self.target = target
            def start(self): self.target()

        root = FakeRoot()
        button, progress, status = mock.Mock(), mock.Mock(), mock.Mock()
        button.configure.side_effect = lambda **kwargs: setattr(button, "command", kwargs["command"])
        result_path = self.base / "installed.exe"
        with mock.patch.object(install_app.tk, "Tk", return_value=root), \
             mock.patch.object(install_app.tk, "StringVar", return_value=status), \
             mock.patch.object(install_app.ttk, "Frame", return_value=mock.Mock()), \
             mock.patch.object(install_app.ttk, "Label", return_value=mock.Mock()), \
             mock.patch.object(install_app.ttk, "Progressbar", return_value=progress), \
             mock.patch.object(install_app.ttk, "Button", return_value=button), \
             mock.patch.object(install_app.threading, "Thread", ImmediateThread), \
             mock.patch.object(install_app, "install", side_effect=[result_path, RuntimeError("bad payload")]), \
             mock.patch.object(install_app.messagebox, "askyesno", return_value=False), \
             mock.patch.object(install_app.messagebox, "showinfo") as showinfo, \
             mock.patch.object(install_app.messagebox, "showerror") as showerror:
            self.assertEqual(install_app._gui(), 0)

        self.assertEqual(root.after_calls, 2)
        self.assertEqual(root.callbacks, [])
        self.assertEqual(root.destroy_calls, 0)
        self.assertEqual(progress.start.call_count, 2)
        self.assertEqual(progress.stop.call_count, 2)
        self.assertEqual(showinfo.call_count, 1)
        showerror.assert_called_once()
        self.assertIn("bad payload", showerror.call_args.args[1])

    @unittest.skipUnless(shutil.which("powershell") or shutil.which("pwsh"), "PowerShell parser unavailable")
    def test_uninstaller_parses_without_running(self):
        executable = shutil.which("powershell") or shutil.which("pwsh")
        script = ROOT / "installer" / "uninstall.ps1"
        # ScriptBlock.Create compiles the source but never invokes it.
        quoted_path = "'" + str(script).replace("'", "''") + "'"
        command = f"$null = [scriptblock]::Create((Get-Content -Raw -LiteralPath {quoted_path}))"
        result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-Command", command],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
