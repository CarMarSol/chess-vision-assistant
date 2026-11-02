"""Regenera las referencias: python -m scripts.calibrate_neo_references."""

import hashlib
import json
from pathlib import Path

import chess
import cv2
import numpy as np

from chess_vision.vision.piece_references import extract_reference_features


def calibrate():
    root = Path(__file__).resolve().parents[1]
    source = root / "tests" / "fixtures" / "neo_user_initial.png"
    image = cv2.imread(str(source))
    if image is None:
        raise FileNotFoundError(source)
    features, symbols, samples = [], [], []
    # Rectángulo comprobado en la captura original; las 32 piezas están en posición inicial.
    for square, piece in sorted(chess.Board().piece_map().items()):
        col, row = chess.square_file(square), 7 - chess.square_rank(square)
        x0, x1 = round(4 + col * 547 / 8), round(4 + (col + 1) * 547 / 8)
        y0, y1 = round(15 + row * 548 / 8), round(15 + (row + 1) * 548 / 8)
        crop = image[y0:y1, x0:x1]
        # A menor resolución cambian el suavizado de los bordes y las líneas interiores.
        for size in (None, 48, 32):
            sample = crop if size is None else cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
            feature = extract_reference_features(sample)
            if feature is None:
                raise ValueError(f"Referencia ilegible en {chess.square_name(square)}")
            features.append(feature)
            symbols.append(piece.symbol())
            samples.append({"square": chess.square_name(square), "symbol": piece.symbol(),
                            "crop_xyxy": [x0, y0, x1, y1], "sample_size": size})
    assert len(features) == 96 and set(symbols) == set("PNBRQKpnbrqk")
    target = root / "data" / "templates" / "chesscom_neo_references"
    np.savez_compressed(target.with_suffix(".npz"), symbols=np.array(symbols),
                        silhouettes=np.array([f[0] for f in features]),
                        details=np.array([f[1] for f in features]),
                        tones=np.array([f[2] for f in features]),
                        aspects=np.array([f[3] for f in features]),
                        heights=np.array([f[4] for f in features]))
    metadata = {
        "set": "Chess.com Neo", "version": 1,
        "source": "tests/fixtures/neo_user_initial.png",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "descriptions": {
            "P/p": "Peón: cabeza redonda, cuello estrecho y cuerpo corto con base ensanchada.",
            "N/n": "Caballo: perfil asimétrico con hocico, orejas y cuello curvado.",
            "B/b": "Alfil: mitra puntiaguda con corte diagonal, cuerpo estrecho y base ovalada.",
            "R/r": "Torre: almenas rectangulares, columna recta y base ancha.",
            "Q/q": "Dama: corona abierta con varias puntas y remates redondos.",
            "K/k": "Rey: cruz central sobre una corona ancha y cuerpo alto.",
        },
        "color": "Mayúsculas: blancas claras con borde gris. Minúsculas: negras grises con borde oscuro.",
        "samples": samples,
    }
    target.with_suffix(".json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Guardadas {len(features)} referencias de las 12 clases en {target.with_suffix('.npz')}")


if __name__ == "__main__":
    calibrate()
