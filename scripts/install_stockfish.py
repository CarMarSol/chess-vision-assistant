"""Instala el motor oficial documentado: python -m scripts.install_stockfish."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def install_stockfish(project_root=PROJECT_ROOT, replace=False):
    root = Path(project_root)
    manifest = json.loads((root / "third_party/stockfish/provenance.json").read_text(encoding="utf-8"))
    destination = root / "bin/stockfish.exe"
    expected = manifest["binary_sha256"]
    if destination.exists():
        if sha256(destination) == expected:
            return destination
        if not replace:
            raise ValueError("Ya existe otro bin/stockfish.exe. Consérvalo o usa --replace para sustituirlo expresamente.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    # Descargar y validar fuera del destino final para conservar cualquier motor existente ante un fallo.
    with tempfile.TemporaryDirectory(prefix="stockfish-", dir=destination.parent) as temp_dir:
        archive = Path(temp_dir) / "official.zip"
        request = urllib.request.Request(manifest["official_package_url"], headers={"User-Agent": "ChessVisionAssistant"})
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        if sha256(archive) != manifest["official_package_sha256"]:
            raise ValueError("El ZIP descargado no coincide con el SHA-256 oficial documentado; no se ha instalado.")

        candidate = Path(temp_dir) / "stockfish.exe"
        with zipfile.ZipFile(archive) as package:
            with package.open(manifest["binary_in_package"]) as source, candidate.open("wb") as output:
                shutil.copyfileobj(source, output)
        if sha256(candidate) != expected:
            raise ValueError("El ejecutable descargado no coincide con sus fuentes documentadas; no se ha instalado.")
        if destination.exists() and sha256(destination) != expected and not replace:
            raise ValueError("Ha aparecido otro motor durante la descarga. Usa --replace solo si deseas sustituirlo.")
        candidate.replace(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description="Instala Stockfish 17 AVX2 oficial, verificando el ZIP y el ejecutable. Requiere CPU AVX2.")
    parser.add_argument("--replace", action="store_true", help="Sustituir un motor existente con un hash diferente")
    args = parser.parse_args()
    try:
        destination = install_stockfish(replace=args.replace)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        parser.exit(1, f"Stockfish: {error}\n")
    print(f"Stockfish 17 AVX2 verificado: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
