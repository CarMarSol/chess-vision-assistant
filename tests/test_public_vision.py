"""Recognize the licensed pieces without relying on private Neo references."""

import chess
import numpy as np
import pytest
from PySide6.QtCore import QByteArray, QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

from chess_vision.ui.pieces_svg import SVG_PIECES
from chess_vision.vision import piece_references, piece_templates
from chess_vision.vision.piece_classifier import PieceClassifier
from scripts import public_piece_templates


@pytest.mark.parametrize("symbol", list("PNBRQKpnbrqk"))
@pytest.mark.parametrize("background", ["#EEEED2", "#769656"])
def test_public_recognition_with_licensed_artwork(symbol, background, monkeypatch):
    monkeypatch.setattr(piece_references, "_load_references", lambda: None)
    monkeypatch.setattr(piece_templates, "get_template_masks", public_piece_templates.get_template_masks)
    image = QImage(80, 80, QImage.Format.Format_ARGB32)
    image.fill(QColor(background))
    painter = QPainter(image)
    renderer = QSvgRenderer(QByteArray(SVG_PIECES[symbol].encode("utf-8")))
    renderer.render(painter, QRectF(0, 0, 80, 80))
    painter.end()
    pixels = np.frombuffer(image.bits(), np.uint8).reshape(80, 80, 4)[:, :, :3].copy()
    expected = chess.Piece.from_symbol(symbol)
    assert PieceClassifier.recognize_square(pixels) == expected
    for square in ("a4", "c8"):
        piece_type, _ = PieceClassifier.classify_piece_type_with_confidence(pixels, expected.color, square)
        assert piece_type == expected.piece_type
