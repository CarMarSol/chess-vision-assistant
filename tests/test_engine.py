"""
Pruebas automatizadas del motor Stockfish, evaluación Multi-PV y clasificación de jugadas.
"""

import pytest
import chess
from chess_vision.engine.stockfish_manager import StockfishManager
from chess_vision.engine.evaluator import Evaluator, CandidateMove
from chess_vision.engine.classifier import MoveClassifier
from chess_vision.engine.accuracy_tracker import AccuracyTracker, AccuracySummary
from chess_vision.config import get_default_stockfish_path


@pytest.fixture(scope="module")
def stockfish_mgr():
    """Fixture que provee una instancia de StockfishManager para las pruebas."""
    path = get_default_stockfish_path()
    mgr = StockfishManager(engine_path=path, threads=2, hash_mb=32)
    yield mgr
    mgr.quit()


def test_stockfish_initialization(stockfish_mgr):
    """Verifica que el motor local de Stockfish arranca correctamente."""
    assert stockfish_mgr._engine is not None
    assert "Stockfish" in stockfish_mgr._engine.id.get("name", "")


def test_multipv_evaluation(stockfish_mgr):
    """Verifica el análisis Multi-PV de exactamente 3 líneas de juego."""
    board = chess.Board()
    analysis = stockfish_mgr.analyze_sync(board, depth=10, time_limit=0.3, multipv=3)

    assert analysis is not None
    assert len(analysis.top_moves) == 3

    # Comprobar candidatos
    m1 = analysis.top_moves[0]
    m2 = analysis.top_moves[1]
    m3 = analysis.top_moves[2]

    assert m1.rank == 1
    assert m2.rank == 2
    assert m3.rank == 3

    assert m1.san in ["e4", "d4", "Nf3", "c4"]
    assert m1.classification.category in ["best", "great", "brilliant", "book"]
    assert 0.0 <= m1.win_rate <= 100.0


def test_mate_evaluation(stockfish_mgr):
    """Verifica que Stockfish detecta mate forzado y clasifica adecuadamente."""
    # Posición de Mate del Loco: 1. f3 e5 2. g4 Qh4#
    board = chess.Board("rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3")
    assert board.is_checkmate()

    # Posición de mate en 1: blancas juegan Qh7#
    board_mate_in_1 = chess.Board("r1bqkb1r/pppp1ppp/2n5/4p3/2B1n3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 0 4")
    analysis = stockfish_mgr.analyze_sync(board_mate_in_1, depth=8, time_limit=0.2, multipv=3)

    best = analysis.best_move
    assert best is not None
    assert best.san == "Qxf7#"
    assert best.mate_in == 1


def test_win_rate_sigmoid():
    """Verifica que la fórmula de Win Rate sigmoidal produce probabilidades correctas."""
    # 0 centipeones = 50% de probabilidad
    assert pytest.approx(MoveClassifier.cp_to_win_rate(0), abs=0.5) == 50.0

    # +300 cp = ventaja clara (> 75%)
    assert MoveClassifier.cp_to_win_rate(300) > 75.0

    # -300 cp = desventaja clara (< 25%)
    assert MoveClassifier.cp_to_win_rate(-300) < 25.0

    # Mate a favor = 100%
    assert MoveClassifier.cp_to_win_rate(None, mate_in=2) == 100.0

    # Mate en contra = 0%
    assert MoveClassifier.cp_to_win_rate(None, mate_in=-2) == 0.0


def test_move_classification_categories():
    """Verifica las categorías de clasificación de jugadas."""
    board = chess.Board()
    move = chess.Move.from_uci("e2e4")

    # Mejor jugada (rank 1)
    c_best = MoveClassifier.classify_move(board, move, rank=1, score_cp=35, mate_in=None, best_score_cp=35, best_mate_in=None)
    assert c_best.category == "best"
    assert c_best.delta_cp == 0.0

    # Imprecisión (delta 80 cp)
    c_inacc = MoveClassifier.classify_move(board, move, rank=2, score_cp=-45, mate_in=None, best_score_cp=35, best_mate_in=None)
    assert c_inacc.category == "inaccuracy"

    # Error grave / Blunder (delta 350 cp)
    c_blunder = MoveClassifier.classify_move(board, move, rank=3, score_cp=-320, mate_in=None, best_score_cp=35, best_mate_in=None)
    assert c_blunder.category == "blunder"
    assert c_blunder.symbol == "??"


def test_opening_book_detection():
    """Verifica que el libro de aperturas reconozca líneas principales y clasifique como 'book'."""
    from chess_vision.engine.opening_book import get_opening_book

    book = get_opening_book()
    board = chess.Board()

    # 1. e4 es jugada de libro
    e4 = chess.Move.from_uci("e2e4")
    is_book, desc = book.is_book_move(board, e4)
    assert is_book is True
    assert desc is not None

    # Jugada absurda 1. a3 no está en las líneas principales
    h4 = chess.Move.from_uci("h2h4")
    is_book_h4, _ = book.is_book_move(board, h4)
    assert is_book_h4 is False


def test_accuracy_tracker_calculation():
    """
    Verifica el cálculo de precisión CAPS:
    - La mejor jugada y jugada de libro otorgan 100% de precisión.
    - Un blunder grave (-300 centipeones) da una precisión baja (~30-50%).
    - Los promedios acumulados y últimas jugadas para blancas y negras se calculan fielmente.
    - El reseteo restaura el estado inicial.
    """
    tracker = AccuracyTracker()

    # 1. Mejor jugada de Blancas -> 100%
    acc_white_1 = tracker.record_move(chess.WHITE, is_best=True)
    assert acc_white_1 == 100.0
    assert tracker.white_accuracy == 100.0
    assert tracker.white_last_acc == 100.0
    assert tracker.white_moves_count == 1

    # 2. Error grave de Negras (-300 cp respecto a evaluación neutral de 0 cp)
    acc_black_1 = tracker.record_move(chess.BLACK, best_score_cp=0, score_cp=-300)
    assert 30.0 <= acc_black_1 <= 50.0
    assert tracker.black_accuracy == pytest.approx(acc_black_1, abs=0.1)
    assert tracker.black_last_acc == pytest.approx(acc_black_1, abs=0.1)
    assert tracker.black_moves_count == 1

    # 3. Segunda jugada de Blancas: precisión manual 80% (imprecisión)
    acc_white_2 = tracker.record_move(chess.WHITE, accuracy=80.0)
    assert acc_white_2 == 80.0
    assert tracker.white_moves_count == 2
    assert tracker.white_last_acc == 80.0
    assert tracker.white_accuracy == pytest.approx(90.0, abs=0.1)  # (100 + 80) / 2

    # 4. Segunda jugada de Negras: mejor jugada 100%
    acc_black_2 = tracker.record_move(chess.BLACK, is_best=True)
    assert acc_black_2 == 100.0
    assert tracker.black_moves_count == 2
    assert tracker.black_last_acc == 100.0
    expected_black_avg = (acc_black_1 + 100.0) / 2.0
    assert tracker.black_accuracy == pytest.approx(expected_black_avg, abs=0.1)

    # 5. Comprobar resumen AccuracySummary
    summary = tracker.get_summary()
    assert summary.white_moves == 2
    assert summary.black_moves == 2
    assert summary.white_accuracy == pytest.approx(90.0, abs=0.1)
    assert summary.white_last_accuracy == 80.0
    assert summary.black_last_accuracy == 100.0

    # 6. Comprobar reset()
    tracker.reset()
    assert tracker.white_moves_count == 0
    assert tracker.black_moves_count == 0
    assert tracker.white_accuracy == 100.0
    assert tracker.black_accuracy == 100.0
    assert tracker.white_last_acc is None
    assert tracker.black_last_acc is None

    # 7. Jugada de libro desde tablero
    board = chess.Board()
    acc_book = tracker.record_move_from_board(board, chess.Move.from_uci("e2e4"))
    assert acc_book == 100.0
    assert tracker.white_moves_count == 1


def test_adaptive_recommender_convergence():
    """
    Verifica el comportamiento del recomendador adaptativo por precisión objetivo:
    - Precisión alta (> objetivo + tolerancia) -> recomienda jugada secundaria sólida (Rank >= 2).
    - Precisión baja (< objetivo - tolerancia) -> recomienda mejor jugada (Rank 1).
    - Precisión en rango -> variabilidad ponderada.
    """
    from chess_vision.engine.adaptive_recommender import AdaptiveRecommender

    board = chess.Board()

    # Crear candidatos sintéticos
    c1 = CandidateMove(
        rank=1, move=chess.Move.from_uci("e2e4"), san="e4", uci="e2e4",
        score_cp=40, win_rate=54.5,
        classification=MoveClassifier.classify_move(board, chess.Move.from_uci("e2e4"), rank=1, score_cp=40, mate_in=None, best_score_cp=40, best_mate_in=None)
    )
    c2 = CandidateMove(
        rank=2, move=chess.Move.from_uci("d2d4"), san="d4", uci="d2d4",
        score_cp=15, win_rate=52.0,
        classification=MoveClassifier.classify_move(board, chess.Move.from_uci("d2d4"), rank=2, score_cp=15, mate_in=None, best_score_cp=40, best_mate_in=None)
    )
    c3 = CandidateMove(
        rank=3, move=chess.Move.from_uci("g1f3"), san="Nf3", uci="g1f3",
        score_cp=0, win_rate=50.0,
        classification=MoveClassifier.classify_move(board, chess.Move.from_uci("g1f3"), rank=3, score_cp=0, mate_in=None, best_score_cp=40, best_mate_in=None)
    )

    candidates = [c1, c2, c3]

    # 1. Precisión actual alta (95%) con objetivo 80% (tol 5)
    pick_high = AdaptiveRecommender.select_adaptive_move(
        candidates=candidates,
        current_accuracy=95.0,
        target_accuracy=80,
        tolerance=5,
        elo=2200
    )
    assert pick_high is not None
    assert pick_high.is_adaptive_pick is True
    assert pick_high.rank >= 2  # Recomienda jugada secundaria para descender suavemente
    assert "80%" in pick_high.adaptive_reason

    # 2. Precisión actual baja (62%) con objetivo 80% (tol 5)
    pick_low = AdaptiveRecommender.select_adaptive_move(
        candidates=candidates,
        current_accuracy=62.0,
        target_accuracy=80,
        tolerance=5,
        elo=2200
    )
    assert pick_low is not None
    assert pick_low.is_adaptive_pick is True
    assert pick_low.rank == 1  # Recomienda Rank 1 para elevar precisión

    # 3. Precisión en rango (79% con objetivo 80%)
    pick_range = AdaptiveRecommender.select_adaptive_move(
        candidates=candidates,
        current_accuracy=79.0,
        target_accuracy=80,
        tolerance=5,
        elo=2200
    )
    assert pick_range is not None
    assert pick_range.is_adaptive_pick is True


def test_adaptive_recommender_safety_fallback():
    """
    Verifica que si la precisión actual es alta pero todas las jugadas secundarias
    son blunders graves, el sistema no se suicida y preserva la mejor jugada (Rank 1).
    """
    from chess_vision.engine.adaptive_recommender import AdaptiveRecommender

    board = chess.Board()
    c1 = CandidateMove(
        rank=1, move=chess.Move.from_uci("e2e4"), san="e4", uci="e2e4",
        score_cp=100, win_rate=65.0,
        classification=MoveClassifier.classify_move(board, chess.Move.from_uci("e2e4"), rank=1, score_cp=100, mate_in=None, best_score_cp=100, best_mate_in=None)
    )
    # Candidato 2 y 3 pierden la dama o mate (-500 centipeones)
    c2 = CandidateMove(
        rank=2, move=chess.Move.from_uci("f2f3"), san="f3", uci="f2f3",
        score_cp=-450, win_rate=5.0,
        classification=MoveClassifier.classify_move(board, chess.Move.from_uci("f2f3"), rank=2, score_cp=-450, mate_in=None, best_score_cp=100, best_mate_in=None)
    )

    pick = AdaptiveRecommender.select_adaptive_move(
        candidates=[c1, c2],
        current_accuracy=98.0,
        target_accuracy=80,
        tolerance=5,
        elo=2200
    )
    assert pick is not None
    assert pick.rank == 1  # Fallback a rank 1 para evitar blunder catastrófico
    assert pick.is_adaptive_pick is True


def test_arrow_overlay_neon_color():
    """Verifica que ArrowOverlay define y usa el color fosforito neón #39FF14."""
    from chess_vision.ui.arrow_overlay import ArrowOverlay
    from PySide6.QtGui import QColor

    assert ArrowOverlay.COLOR_ADAPTIVE == QColor(57, 255, 20, 235)
    # #39FF14 en RGB es (57, 255, 20)
    assert ArrowOverlay.COLOR_ADAPTIVE.red() == 57
    assert ArrowOverlay.COLOR_ADAPTIVE.green() == 255
    assert ArrowOverlay.COLOR_ADAPTIVE.blue() == 20


