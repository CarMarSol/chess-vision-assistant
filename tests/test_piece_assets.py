"""Provenance and regeneration checks for the publishable chess artwork."""

import hashlib
import json
from pathlib import Path

import numpy as np

from chess_vision.ui.pieces_svg import SVG_PIECES
from scripts import public_piece_templates
from third_party.chess_pieces.generate_templates import render_mask


def test_public_artwork_matches_pinned_sources_and_templates():
    assets = Path(__file__).resolve().parents[1] / "third_party" / "chess_pieces"
    manifest = json.loads((assets / "SOURCES.json").read_text(encoding="utf-8"))
    assert set(SVG_PIECES) == set("PNBRQKpnbrqk")
    for symbol in "PNBRQKpnbrqk":
        filename = ("w" if symbol.isupper() else "b") + symbol.upper() + ".svg"
        source = (assets / filename).read_bytes()
        assert hashlib.sha256(source).hexdigest() == manifest["files"][filename]["sha256"]
        assert SVG_PIECES[symbol].encode("utf-8") == source
        mask = public_piece_templates.get_template_mask(symbol)
        assert np.array_equal(mask, render_mask(source))
        assert mask.shape == (32, 32) and mask.dtype == bool and np.any(mask)
        assert np.any(public_piece_templates.get_normalized_template_mask(symbol))
        assert not np.any(public_piece_templates.get_neo_template_mask(symbol))
        assert len(public_piece_templates.get_template_masks(symbol)) == 1
    assert not np.any(public_piece_templates.get_template_mask("?"))
