"""Verify that the public artifact contains only the intended, reproducible inputs."""

import ast
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from scripts.prepare_publication import prepare_publication


def test_publication_excludes_private_assets_and_preserves_source(tmp_path):
    source = Path(__file__).resolve().parents[1]
    original = (source / "chess_vision/vision/piece_templates.py").read_bytes()
    folder, archive = prepare_publication(source, tmp_path / "public-source")
    assert (source / "chess_vision/vision/piece_templates.py").read_bytes() == original
    assert not (folder / ".git").exists()
    assert not (folder / "tests/fixtures").exists()
    assert not list(folder.rglob("*.png"))
    assert not list(folder.rglob("*.npz"))
    assert not list(folder.rglob("*.exe"))
    assert not list(folder.rglob("*.pyc"))
    assert (folder / "scripts/build_windows_release.py").is_file()
    assert (folder / "installer/install_app.py").is_file()
    assert (folder / "installer/uninstall.ps1").is_file()
    assert (folder / "installer/Desinstalar.cmd").is_file()
    assert (folder / "licenses/LGPL-3.0.txt").is_file()
    assert (folder / "tests/test_windows_release.py").is_file()
    assert (folder / "data/openings.bin").stat().st_size > 0
    assert (folder / "third_party/stockfish/provenance.json").is_file()
    stockfish = folder / "third_party/stockfish"
    provenance = json.loads((stockfish / "provenance.json").read_text(encoding="utf-8"))
    for name, expected_hash in provenance["files"].items():
        assert hashlib.sha256((stockfish / name).read_bytes()).hexdigest() == expected_hash
    public_masks = (folder / "chess_vision/vision/piece_templates.py").read_text(encoding="utf-8")
    assert public_masks == (source / "scripts/public_piece_templates.py").read_text(encoding="utf-8")
    ast.parse(public_masks)
    manifest = json.loads((folder / "PUBLICATION_MANIFEST.json").read_text(encoding="utf-8"))
    for name, expected_hash in manifest["files_sha256"].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == expected_hash
    with zipfile.ZipFile(archive) as packed:
        assert "README.md" in packed.namelist()
        assert "chess_vision/vision/piece_templates.py" in packed.namelist()
    # A second invocation cannot replace reviewable output or its ZIP.
    with pytest.raises(FileExistsError):
        prepare_publication(source, folder)
