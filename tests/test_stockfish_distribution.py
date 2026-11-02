"""Un cambio de motor o fuentes no debe producir una distribución mal atribuida."""

import hashlib
import json
import io
import zipfile
from pathlib import Path

import pytest

import build_exe
from scripts.install_stockfish import install_stockfish


def test_included_source_bundle_and_network_names_match_provenance():
    sources = Path(build_exe.PROJECT_ROOT) / "third_party/stockfish"
    manifest = json.loads((sources / "provenance.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        assert hashlib.sha256((sources / name).read_bytes()).hexdigest() == expected
    with zipfile.ZipFile(sources / manifest["source_archive"]) as archive:
        assert archive.testzip() is None
        prefix = "Stockfish-" + manifest["source_commit"] + "/"
        assert prefix + "src/Makefile" in archive.namelist()
        assert prefix + ".github/workflows/stockfish.yml" in archive.namelist()
        evaluate_header = archive.read(prefix + "src/evaluate.h").decode()
        for network in manifest["networks"]:
            assert network["filename"] in evaluate_header


def test_stockfish_bundle_rejects_replaced_binary_and_source(tmp_path, monkeypatch):
    monkeypatch.setattr(build_exe, "PROJECT_ROOT", str(tmp_path))
    sources = tmp_path / "third_party" / "stockfish"
    sources.mkdir(parents=True)
    engine = tmp_path / "stockfish.exe"
    engine.write_bytes(b"verified binary")
    names = ("stockfish-17-source.zip", "Copying.txt", "AUTHORS")
    for name in names:
        (sources / name).write_bytes(name.encode())
    manifest = {
        "binary_sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
        "files": {name: hashlib.sha256((sources / name).read_bytes()).hexdigest() for name in names},
    }
    (sources / "provenance.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert build_exe.verify_stockfish_bundle(engine) == sources

    engine.write_bytes(b"different engine")
    with pytest.raises(ValueError, match="binario oficial"):
        build_exe.verify_stockfish_bundle(engine)

    engine.write_bytes(b"verified binary")
    (sources / "stockfish-17-source.zip").write_bytes(b"different source")
    with pytest.raises(ValueError, match="fuentes o avisos"):
        build_exe.verify_stockfish_bundle(engine)


def test_installer_verifies_download_and_preserves_existing_engine(tmp_path, monkeypatch):
    content = b"verified engine"
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w") as archive:
        archive.writestr("stockfish/official.exe", content)
        archive.writestr("../unwanted.txt", "must not extract")
    package = memory.getvalue()
    source_dir = tmp_path / "third_party/stockfish"
    source_dir.mkdir(parents=True)
    manifest = {
        "binary_sha256": hashlib.sha256(content).hexdigest(),
        "official_package_sha256": hashlib.sha256(package).hexdigest(),
        "official_package_url": "https://github.com/official-stockfish/example.zip",
        "binary_in_package": "stockfish/official.exe",
    }
    manifest_path = source_dir / "provenance.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: io.BytesIO(package))

    engine = install_stockfish(tmp_path)
    assert engine.read_bytes() == content
    assert not (tmp_path / "unwanted.txt").exists()
    assert install_stockfish(tmp_path) == engine

    engine.write_bytes(b"personal engine")
    with pytest.raises(ValueError, match="--replace"):
        install_stockfish(tmp_path)
    assert engine.read_bytes() == b"personal engine"

    manifest["official_package_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="ZIP descargado"):
        install_stockfish(tmp_path, replace=True)
    assert engine.read_bytes() == b"personal engine"

    manifest["official_package_sha256"] = hashlib.sha256(package).hexdigest()
    manifest["binary_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="ejecutable descargado"):
        install_stockfish(tmp_path, replace=True)
    assert engine.read_bytes() == b"personal engine"

    manifest["binary_sha256"] = hashlib.sha256(content).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert install_stockfish(tmp_path, replace=True).read_bytes() == content
