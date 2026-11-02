"""Generate publication-only silhouette templates from the verified SVG sources."""

from pathlib import Path
import base64
import hashlib
import json

import cv2
import numpy as np
from PySide6.QtCore import QByteArray
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def render_mask(svg: bytes) -> np.ndarray:
    renderer = QSvgRenderer(QByteArray(svg))
    if not renderer.isValid():
        raise ValueError("Invalid SVG source")
    image = QImage(128, 128, QImage.Format.Format_RGBA8888)
    image.fill(0)
    painter = QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    rgba = np.frombuffer(image.bits(), np.uint8).reshape(128, 128, 4)
    return cv2.resize((rgba[:, :, 3] > 127).astype(np.uint8), (32, 32),
                      interpolation=cv2.INTER_NEAREST).astype(bool)


def generate() -> None:
    root = Path(__file__).resolve().parents[2]
    assets = Path(__file__).resolve().parent
    manifest = json.loads((assets / "SOURCES.json").read_text(encoding="utf-8"))
    masks = {}
    hashes = {}
    for side in "wb":
        for kind in "PNBRQK":
            filename = f"{side}{kind}.svg"
            source = (assets / filename).read_bytes()
            digest = hashlib.sha256(source).hexdigest()
            if digest != manifest["files"][filename]["sha256"]:
                raise ValueError(f"Changed SVG source: {filename}")
            symbol = kind if side == "w" else kind.lower()
            masks[symbol] = base64.b64encode(np.packbits(render_mask(source)).tobytes()).decode("ascii")
            hashes[symbol] = digest
    header = '''"""Publication templates derived only from verified cburnett SVG artwork.

Artwork copyright Colin M. L. Burnett, GPL-2.0-or-later; this derivative
is distributed under GPL-3.0-or-later. See third_party/chess_pieces/.
Generated with third_party/chess_pieces/generate_templates.py.
No Neo artwork, reference samples or private screenshots are included.
"""

import base64
from functools import lru_cache

import cv2
import numpy as np

'''
    body = '''

def get_template_mask(symbol: str) -> np.ndarray:
    value = _PACKED_MASKS.get(symbol)
    if value is None:
        return np.zeros((32, 32), dtype=bool)
    return np.unpackbits(np.frombuffer(base64.b64decode(value), np.uint8)).reshape(32, 32).astype(bool)


def get_neo_template_mask(symbol: str) -> np.ndarray:
    """Neo references are intentionally absent from the public distribution."""
    return np.zeros((32, 32), dtype=bool)


@lru_cache(maxsize=24)
def get_normalized_template_mask(symbol: str, set_name: str = "cburnett") -> np.ndarray:
    raw = get_neo_template_mask(symbol) if set_name == "neo" else get_template_mask(symbol)
    ys, xs = np.where(raw)
    if not len(ys):
        return np.zeros((32, 32), dtype=bool)
    cropped = raw[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8)
    return cv2.resize(cropped, (32, 32), interpolation=cv2.INTER_NEAREST).astype(bool)


def get_template_masks(symbol: str) -> list[np.ndarray]:
    return [get_normalized_template_mask(symbol)]
'''
    text = header + f'SOURCE_COMMIT = {manifest["commit"]!r}\n'
    text += f'SOURCE_SHA256 = {hashes!r}\n'
    text += '_PACKED_MASKS = {\n'
    text += ''.join(f'    {symbol!r}: {value!r},\n' for symbol, value in masks.items())
    text += '}\n' + body
    target = root / "scripts" / "public_piece_templates.py"
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"Generated {target}: {len(masks)} verified cburnett masks")


if __name__ == "__main__":
    generate()
