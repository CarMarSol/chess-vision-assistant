"""
Pruebas del libro de aperturas Polyglot (openings.bin) y clasificación de jugadas teóricas.
"""

import os
import pytest
import chess
from chess_vision.engine.opening_book import OpeningBook, compile_polyglot_book, DEFAULT_BOOK_PATH
from chess_vision.engine.classifier import MoveClassifier


@pytest.fixture(scope="module")
def book():
    """Instancia del libro de aperturas."""
    return OpeningBook.get_default()


def test_book_file_exists(book):
    """Verifica que data/openings.bin se compila y existe en el disco."""
    assert os.path.isfile(DEFAULT_BOOK_PATH)
    assert os.path.getsize(DEFAULT_BOOK_PATH) > 0


def test_initial_position_in_book(book):
    """Verifica que la posición inicial de ajedrez se reconoce en el libro."""
    board = chess.Board()
    assert book.is_book_position(board) is True

    moves = book.get_book_moves(board)
    assert len(moves) >= 3
    uci_moves = [m.uci() for m in moves]
    assert "e2e4" in uci_moves
    assert "d2d4" in uci_moves


def test_sicilian_defense_detection(book):
    """Verifica la detección de la Defensa Siciliana y su nombre."""
    board = chess.Board()
    board.push_san("e4")
    board.push_san("c5")

    name = book.get_opening_name(board)
    assert name == "Defensa Siciliana"

    # Continuaciones teóricas (Nf3, c3, etc.)
    is_book, desc = book.is_book_move(board, chess.Move.from_uci("g1f3"))
    assert is_book is True
    assert desc == "Defensa Siciliana"


def test_book_move_classification():
    """Verifica que una jugada marcada como libro recibe la categoría 'book' y color marrón."""
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")

    cls_meta = MoveClassifier.classify_move(
        board=board,
        move=move,
        rank=1,
        score_cp=35,
        mate_in=None,
        best_score_cp=35,
        best_mate_in=None,
        is_book_move=True,
        book_description="Apertura Española"
    )

    assert cls_meta.category == "book"
    assert cls_meta.label == "Libro"
    assert cls_meta.badge_color == "#A87A51"
    assert "Apertura Española" in cls_meta.description
