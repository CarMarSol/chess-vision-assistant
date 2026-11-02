"""
Pruebas de simulación de Elo y modulación de estilos de juego.
"""

import pytest
import chess
from chess_vision.engine.styles import EloManager, StyleEvaluator, ChessStyle


def test_elo_options_high_level():
    """Para Elo >= 1320, se activan opciones nativas de Stockfish UCI_LimitStrength."""
    opts_2200 = EloManager.get_engine_options(2200)
    assert opts_2200["UCI_LimitStrength"] is True
    assert opts_2200["UCI_Elo"] == 2200

    opts_1500 = EloManager.get_engine_options(1500)
    assert opts_1500["UCI_LimitStrength"] is True
    assert opts_1500["UCI_Elo"] == 1500


def test_elo_options_low_level():
    """Para Elo < 1320, se limita la profundidad y se usa el límite base."""
    opts_800 = EloManager.get_engine_options(800)
    assert opts_800["UCI_LimitStrength"] is True
    assert opts_800["UCI_Elo"] == 1320

    depth_800 = EloManager.adjust_search_depth_for_low_elo(800, base_depth=14)
    assert depth_800 <= 3

    depth_1200 = EloManager.adjust_search_depth_for_low_elo(1200, base_depth=14)
    assert depth_1200 <= 6

    depth_2000 = EloManager.adjust_search_depth_for_low_elo(2000, base_depth=14)
    assert depth_2000 == 14


def test_style_bonus_aggressive():
    """El estilo agresivo premia jugadas con jaques y capturas."""
    board = chess.Board()
    move_e4 = chess.Move.from_uci("e2e4")
    bonus = StyleEvaluator.score_bonus_for_style(board, move_e4, ChessStyle.AGGRESSIVE)
    assert bonus > 0.0  # avance hacia el campo rival

    # Posición con jaque disponible
    board_check = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/5Q2/PPPP1PPP/RNB1KBNR w KQkq - 0 1")
    move_check = chess.Move.from_uci("f3f7")
    bonus_check = StyleEvaluator.score_bonus_for_style(board_check, move_check, ChessStyle.AGGRESSIVE)
    assert bonus_check >= 50.0  # jaque + captura


def test_style_bonus_positional():
    """El estilo posicional premia el control del centro."""
    board = chess.Board()
    move_d4 = chess.Move.from_uci("d2d4")
    bonus = StyleEvaluator.score_bonus_for_style(board, move_d4, ChessStyle.POSITIONAL)
    assert bonus >= 30.0  # casilla central d4


def test_style_margin_filter_safe():
    """Verifica que el estilo sólo modula dentro del margen seguro (50-70 cp) y descarta pérdidas mayores."""
    board = chess.Board()
    cand1 = {"move": chess.Move.from_uci("e2e4"), "score_cp": 50, "mate_in": None}
    cand2 = {"move": chess.Move.from_uci("d2d4"), "score_cp": 20, "mate_in": None}  # pérdida 30 cp <= 65 cp
    cand3 = {"move": chess.Move.from_uci("h2h4"), "score_cp": -70, "mate_in": None} # pérdida 120 cp > 65 cp

    candidates = [dict(cand1), dict(cand2), dict(cand3)]
    ranked, obj_best = StyleEvaluator.filter_and_rank_by_style(
        board, candidates, style=ChessStyle.POSITIONAL, max_margin_cp=65.0
    )

    assert obj_best["move"] == chess.Move.from_uci("e2e4")
    # cand2 (d4 centro) tiene bonus +30cp -> adjusted_cp = 20 + 30 = 50
    item_d4 = next(c for c in ranked if c["move"] == chess.Move.from_uci("d2d4"))
    assert item_d4["is_style_eligible"] is True
    # cand3 (h4) pierde 120 cp -> no es elegible
    item_h4 = next(c for c in ranked if c["move"] == chess.Move.from_uci("h2h4"))
    assert item_h4["is_style_eligible"] is False
