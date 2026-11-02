"""Create a new, reviewable source folder and ZIP without private visual assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


ROOT_FILES = (
    "main.py", "build_exe.py", "run.bat", "README.md", "LICENSE",
    "THIRD_PARTY_NOTICES.md", "requirements.txt", "requirements-dev.txt", ".gitignore",
    "installer/install_app.py", "installer/uninstall.ps1", "installer/Desinstalar.cmd",
    "licenses/LGPL-3.0.txt",
)
PUBLIC_TESTS = (
    "__init__.py", "conftest.py", "test_engine.py", "test_styles_elo.py",
    "test_opening_book.py", "test_ui.py", "test_display_modes.py", "test_i18n.py",
    "test_piece_assets.py", "test_stockfish_distribution.py", "test_publication.py", "test_public_vision.py",
    "test_windows_release.py", "test_windows_installer.py",
)
PRIVATE_TESTS = (
    "test_vision.py", "test_game_sync.py", "test_stress_loops.py",
    "test_neo_piece_identification.py", "test_castling_and_king_regressions.py",
)


def prepare_publication(source: Path, destination: Path) -> tuple[Path, Path]:
    source, destination = source.resolve(), destination.resolve()
    input_dirs = ("chess_vision", "tests", "scripts", "data", "docs", "third_party", "installer", ".github")
    if destination == source or any(destination.is_relative_to(source / d) for d in input_dirs):
        raise ValueError("El destino debe estar separado de las carpetas de código de entrada.")
    if destination.exists() or Path(str(destination) + ".zip").exists():
        raise FileExistsError(f"El destino ya existe; elige una carpeta nueva: {destination}")

    # All required inputs are checked before creating the output folder.
    required = [source / name for name in ROOT_FILES]
    required += [source / "tests" / name for name in PUBLIC_TESTS]
    required += [source / "scripts/public_piece_templates.py", source / "scripts/install_stockfish.py"]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    if not (source / "third_party/stockfish/provenance.json").is_file():
        raise FileNotFoundError("Falta la procedencia comprobada de Stockfish.")
    if not (source / "third_party/chess_pieces/SOURCES.json").is_file():
        raise FileNotFoundError("Falta la procedencia comprobada de las piezas.")

    destination.mkdir(parents=True, exist_ok=False)

    def copy_file(path: Path) -> None:
        target = destination / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    for name in ROOT_FILES:
        copy_file(source / name)
    for path in (source / "chess_vision").rglob("*.py"):
        if "__pycache__" not in path.parts and path.name != "piece_templates.py":
            copy_file(path)
    shutil.copy2(source / "scripts/public_piece_templates.py",
                 destination / "chess_vision/vision/piece_templates.py")
    for path in (source / "scripts").glob("*.py"):
        copy_file(path)
    for name in PUBLIC_TESTS:
        copy_file(source / "tests" / name)
    for directory in ("docs", "third_party", ".github"):
        for path in (source / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and (path.name == "AUTHORS" or path.suffix.lower() in {
                ".py", ".md", ".txt", ".json", ".svg", ".zip", ".yml", ".yaml",
            }):
                copy_file(path)

    # Regenerate the book from the source catalog instead of redistributing an unchecked file.
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from chess_vision.engine.opening_book import compile_polyglot_book
    compile_polyglot_book(str(destination / "data/openings.bin"))
    templates = destination / "data/templates"
    templates.mkdir(parents=True)
    (templates / "README.md").write_text(
        "# Referencias visuales\n\nEsta distribución usa las máscaras cburnett verificadas "
        "incluidas en el código. No contiene capturas privadas ni la base Neo. "
        "Consulta docs/PIEZAS_Y_RECONOCIMIENTO.md para calibrar otros diseños.\n", encoding="utf-8",
    )
    files = sorted(p for p in destination.rglob("*") if p.is_file())
    manifest = {
        "visual_assets": "verified cburnett only; no private screenshots or Neo database",
        "stockfish": "matching source archive included; binary installed separately",
        "private_visual_regression_modules_not_distributed": list(PRIVATE_TESTS),
        "files_sha256": {p.relative_to(destination).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in files},
    }
    (destination / "PUBLICATION_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    archive = Path(shutil.make_archive(str(destination), "zip", root_dir=destination))
    return destination, archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Carpeta nueva; nunca se sobrescribe una existente")
    args = parser.parse_args()
    source = Path(__file__).resolve().parents[1]
    output = args.output or source / "publicacion/chess-vision-assistant"
    folder, archive = prepare_publication(source, output)
    print(f"Carpeta preparada: {folder}\nZIP de código fuente: {archive}")
    print("Revisa estos archivos y publica desde esta carpeta nueva, no desde la copia de trabajo.")


if __name__ == "__main__":
    main()
