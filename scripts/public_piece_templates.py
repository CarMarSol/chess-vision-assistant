"""Publication templates derived only from verified cburnett SVG artwork.

Artwork copyright Colin M. L. Burnett, GPL-2.0-or-later; this derivative
is distributed under GPL-3.0-or-later. See third_party/chess_pieces/.
Generated with third_party/chess_pieces/generate_templates.py.
No Neo artwork, reference samples or private screenshots are included.
"""

import base64
from functools import lru_cache

import cv2
import numpy as np

SOURCE_COMMIT = '5b44d719ec5913dd62aa965f4b8d21e60a00c2c1'
SOURCE_SHA256 = {'P': 'a8bd79f344ea69a577cdd7b11cbab7bbebfc157cce01c6d29b8f2edf1c44068e', 'N': '43d8bed9cd40836335072a20f52d30237e6e2cbe304ffb13e258fa1d576c156a', 'B': '8bf4f38cc170686775f81158934301942b07e3f1162e76c6305e76d66aaa0910', 'R': '05746153e11de3ff4a43d6725f704e226e5d5b49c6ff170ed598d3e9883f2cd5', 'Q': '9c0a960b360e08cea48eedab54e852107145de289b81a82fe27942045e2ab665', 'K': '09837f1f99dae2d05c2a0bfb5ce0fb9f37a95b124de44f428a08ae18d7b7c557', 'p': '93e11e46deceff0768211a28df3e39c6d3427aa172bdb5e3928b025bd2858587', 'n': '72e1565fbc9024015dcb6ee28d918c876523119f6f552c0a40d3118c13a67e13', 'b': '48ff9dba84dae861b1a81ac58f4647e05cee8a827acad1618bf11beaedcce60d', 'r': '5928b86919ae815f5d35dea8a25f5a84c3f8839468a137e429d42f618185cbcd', 'q': '2d0162d1fe776ac5a4d307d4f6e5960804273edc0d3743f1c97a158f5a64c4b1', 'k': '2dc3caba39a67a707ebc27f4e41b727dd5252f4f49da695fc15cc2589dd92a47'}
_PACKED_MASKS = {
    'P': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHAAAAD4AAAB/AAAAfwAAAH8AAAB/AAAA/4AAAP+AAAH/gAAB/8AAAf+AAAD/gAAA/wAAAf+AAAP/wAAD/+AAB//wAAf/8AAP//gAD//4AA//+AAP//gAD//4AAAAAAAAAAAAAAAAA=',
    'N': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAYwAAAHcAAAA/4AAAP/gAAH/+AAD//wAA//+AAf//gAP//8AD///AB///4Af//+AH/v/gD/z/4A/4/+AP4f/wB+P/8ADH//AAD//wAA//8AAf//AAH//wAB//8AAf//AAAAAAAAAAAAAAAAA=',
    'B': 'AAAAAAAAAAAAAAAAAAAAAAABwAAAA+AAAAPgAAABwAAAA+AAAA/wAAAf+AAAH/wAAD/+AAA//gAAP/4AAD/+AAA//gAAP/wAAB/8AAAf+AAAH/wAAD/8AAA//AAAH/wAAAfwAAP//8AH///wD///+AAAAAAAAAAAAAAAAAAAAAA=',
    'R': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOPngADz54AA//+AAP//gAD//4AAf/8AAD/+AAA//gAAP/4AAD/+AAA//gAAP/4AAD/+AAA//gAAP/4AAD/+AAB//wAA//8AAP//AAH//8AD///gA///4AP//8AAAAAAAAAAAAAAAAA=',
    'Q': 'AAAAAAAAAAAAAAAAAAAAAAAhwAAAc8cAAPHPABxwhxgeIII8HDGGPAwxxhgGMc4wBjnOcAc5zmADv97gA7//4AP//+AD///gA///4AP//8AB///AAP//gAD//wAAf/8AAP//gAH//4AB//+AAf//gAA//gAAAAAAAAAAAAAAAAA=',
    'K': 'AAAAAAAAAAAAAAAAAAAAAAAAgAAAAIAAAAPAAAAAgAAAAIAAAAPAAAAD4AAB4+eAA/v/4Af///AP///wD///+A////gP///wB///8Af//+AD///AAP//gAD//wAA//8AAP//AAD//wAA//8AAH/+AAAP+AAAAAAAAAAAAAAAAAA=',
    'p': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHAAAAD4AAAB/AAAAfwAAAH8AAAB/AAAA/4AAAP+AAAH/gAAB/8AAAf+AAAD/gAAA/wAAAf+AAAP/wAAD/+AAB//wAAf/8AAP//gAD//4AA//+AAP//gAD//4AAAAAAAAAAAAAAAAA=',
    'n': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAYwAAAHcAAAA/4AAAP/gAAH/+AAD//wAA//+AAf//gAP//8AD///AB///4Af//+AH/v/gD/z/4A/4/+AP4f/wB+P/8ADH//AAD//wAA//8AAf//AAH//wAB//8AAf//AAAAAAAAAAAAAAAAA=',
    'b': 'AAAAAAAAAAAAAAAAAAAAAAABwAAAA+AAAAPgAAABwAAAA+AAAA/wAAAf+AAAH/wAAD/+AAA//gAAP/4AAD/+AAA//gAAP/wAAB/8AAAf+AAAH/wAAD/8AAA//AAAH/wAAAfwAAP//8AH///wD///+AAAAAAAAAAAAAAAAAAAAAA=',
    'r': 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAOPngADz54AA//+AAP//gAD//4AAf/8AAD/+AAA//gAAP/4AAD/+AAA//gAAP/4AAD/+AAA//gAAP/4AAD/+AAB//wAA//8AAP//AAH//8AD///gA///4AP//8AAAAAAAAAAAAAAAAA=',
    'q': 'AAAAAAAAAAAAAAAAAAAAAAABwAAAcccAAPPPABxxxxgeYIY8HjGGPAwxxhgGMc4wBjnOcAc5znAHv97gA7/+4AP//+AD///gA///4AP//8AB///AAP//gAD//wAAf/8AAP//gAH//4AB//+AAf//gAB//wAAA+AAAAAAAAAAAAA=',
    'k': 'AAAAAAAAAAAAAAAAAAAAAAAAgAAAAIAAAAPAAAAAgAAAAIAAAAPAAAAD4AAB4+eAA/v/4Af///AP///wD///+A////gP///wB///8Af//+AD///AAP//gAD//wAA//8AAP//AAD//wAA//8AAH/+AAAP8AAAAAAAAAAAAAAAAAA=',
}


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
