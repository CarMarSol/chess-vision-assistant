"""
Pruebas de la interfaz gráfica PySide6 en modo offscreen.
Verifica que las ventanas, paneles de evaluación y tablero se instancian correctamente.
"""

import os
import pytest
import chess

# Forzar modo offscreen en Qt para entornos sin display o pruebas automatizadas
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication
from chess_vision.config import AppConfig, BoardConfig
from chess_vision.ui.main_window import MainWindow, SingleBoardWidget
from chess_vision.ui.board_view import BoardView
from chess_vision.ui.eval_panel import EvalPanel
from chess_vision.ui.test_simulation_dialog import SimulationDialog
from chess_vision.engine.evaluator import CandidateMove, PositionAnalysis
from chess_vision.engine.classifier import MoveClassification


@pytest.fixture(scope="session")
def qapp():
    """Garantiza una única instancia de QApplication para la suite de pruebas."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def initial_board_capture(qapp, monkeypatch):
    import numpy as np
    from PySide6.QtGui import QImage
    from chess_vision.capture.screen_capture import ScreenCapture

    source = BoardView()
    source.resize(400, 400)
    source.set_board(chess.Board())
    image = QImage(400, 400, QImage.Format.Format_BGR888)
    source.render(image)
    frame = np.frombuffer(image.bits(), dtype=np.uint8).reshape(400, 400, 3).copy()
    monkeypatch.setattr(ScreenCapture, "capture_region", lambda region: frame)
    yield frame
    source.close()


def test_board_view_rendering(qapp):
    """Verifica que BoardView procesa el tablero y no lanza excepciones al pintar."""
    bv = BoardView()
    board = chess.Board()
    bv.set_board(board)
    assert bv._board.fen() == chess.STARTING_FEN

    # Probar candidatos
    cand1 = CandidateMove(
        rank=1,
        move=chess.Move.from_uci("e2e4"),
        san="e4",
        uci="e2e4",
        score_cp=35,
        win_rate=53.5,
        classification=MoveClassification(
            category="best", label="Mejor jugada", symbol="★", badge_color="#81B64C",
            delta_cp=0.0, win_rate_loss=0.0, description=""
        )
    )
    bv.set_candidate_moves([cand1])
    assert len(bv._candidate_moves) == 1

    # Invertir orientación
    bv.toggle_orientation()
    assert bv._orientation == "black"


def test_board_view_themes(qapp):
    """Verifica el cambio dinámico de temas visuales de tablero."""
    bv = BoardView()
    for theme in ["green", "wood", "blue", "mono"]:
        bv.set_theme(theme)
        assert bv._theme_name == theme


def test_board_view_manual_editing(qapp):
    """Verifica la edición manual de casillas y cambio de turno."""
    bv = BoardView()
    edited_fens = []
    bv.board_edited.connect(lambda fen: edited_fens.append(fen))

    # Colocar Dama Blanca en e4
    sq_e4 = chess.E4
    bv._set_square_piece(sq_e4, chess.QUEEN, chess.WHITE)
    assert bv._board.piece_at(sq_e4) == chess.Piece(chess.QUEEN, chess.WHITE)
    assert len(edited_fens) == 1

    # Vaciar casilla e4
    bv._set_square_piece(sq_e4, None, None)
    assert bv._board.piece_at(sq_e4) is None
    assert len(edited_fens) == 2

    # Cambiar turno
    initial_turn = bv._board.turn
    bv._toggle_turn()
    assert bv._board.turn != initial_turn
    assert len(edited_fens) == 3


def test_eval_panel_update(qapp):
    """Verifica la actualización de la barra de evaluación y tarjetas."""
    panel = EvalPanel()
    board = chess.Board()

    c1 = CandidateMove(
        rank=1, move=chess.Move.from_uci("e2e4"), san="e4", uci="e2e4",
        score_cp=40, win_rate=54.0
    )
    c2 = CandidateMove(
        rank=2, move=chess.Move.from_uci("d2d4"), san="d4", uci="d2d4",
        score_cp=25, win_rate=52.0
    )
    c3 = CandidateMove(
        rank=3, move=chess.Move.from_uci("g1f3"), san="Nf3", uci="g1f3",
        score_cp=20, win_rate=51.5
    )

    analysis = PositionAnalysis(
        fen=board.fen(),
        turn=chess.WHITE,
        top_moves=[c1, c2, c3],
        best_move=c1,
        alternative_1=c2,
        alternative_2=c3,
        evaluation_bar_score=0.40
    )

    panel.update_analysis(analysis)
    assert panel.card_1.lbl_san.text() == "e4"
    assert panel.card_2.lbl_san.text() == "d4"
    assert panel.card_3.lbl_san.text() == "Nf3"


def test_simulation_dialog_presets(qapp):
    """Verifica que el diálogo de simulación carga las posiciones célebres."""
    dlg = SimulationDialog()
    assert dlg._board is not None

    # Cambiar preset
    dlg._on_preset_selected("Mate de la Ópera (Paul Morphy)")
    assert "4kb1r" in dlg._board.fen()


def test_main_window_instantiation(qapp):
    """Verifica que la MainWindow inicializa con 1 a 4 tableros configurables."""
    cfg = AppConfig(active_board_count=2)
    win = MainWindow(config=cfg)
    win.show()

    assert win.config.active_board_count == 2
    assert len(win._board_widgets) == 4
    assert not win._board_widgets["board_1"].isHidden()
    assert not win._board_widgets["board_2"].isHidden()
    assert win._board_widgets["board_3"].isHidden()

    win.close()


def test_auto_sync_initial_moves(qapp):
    """Verifica que si se inicia con 1. e4 e5 ya jugado en pantalla, se sincroniza automáticamente."""
    import numpy as np
    cfg = AppConfig(active_board_count=1)
    win = MainWindow(config=cfg)
    bw = win._board_widgets["board_1"]

    # Generar recortes sintéticos simulando 1. e4 e5 en pantalla
    empty_sq = np.ones((50, 50, 3), dtype=np.uint8) * 200
    occ_white = np.ones((50, 50, 3), dtype=np.uint8) * 120
    occ_white[15:35, 15:35] = 240  # peón blanco
    occ_black = np.ones((50, 50, 3), dtype=np.uint8) * 120
    occ_black[15:35, 15:35] = 20   # peón negro

    squares = {
        "e2": empty_sq,
        "e4": occ_white,
        "e7": empty_sq,
        "e5": occ_black
    }

    bw._auto_sync_initial_moves(squares)
    # Debe haber avanzado e2e4 y e7e5
    assert bw.sync_mgr.board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)
    assert bw.sync_mgr.board.piece_at(chess.E5) == chess.Piece(chess.PAWN, chess.BLACK)
    assert bw.sync_mgr.board.turn == chess.WHITE  # Turno vuelve a blancas tras 1...e5

    win.close()


def test_set_region_immediate_live(qapp, initial_board_capture):
    """Verifica que set_region activa EN VIVO inmediatamente sin bloqueos de calibración."""
    cfg = AppConfig(active_board_count=1)
    win = MainWindow(config=cfg)
    bw = win._board_widgets["board_1"]

    # Simular asignación de región
    bw.set_region((100, 100, 400, 400))

    assert "EN VIVO" in bw.lbl_sync_status.text()
    assert bw.scan_timer.isActive()
    assert bw.scan_timer.interval() <= 80

    win.close()


def test_set_region_mental_board_active_32_pieces(qapp, initial_board_capture):
    """
    Verifica que al seleccionar pantalla antes de empezar la partida (set_region):
    1. Se crea e inicializa formalmente el Tablero Mental (PieceMentalMap) con 32 piezas.
    2. El estado muestra '● EN VIVO · Tablero mental activo (32 piezas)'.
    3. Cada pieza viva tiene su identidad original (caballos, alfiles, reyes, etc.).
    """
    cfg = AppConfig(active_board_count=1)
    win = MainWindow(config=cfg)
    bw = win._board_widgets["board_1"]

    # Simular recorte de pantalla antes de empezar la partida
    bw.set_region((50, 50, 450, 450))

    status_text = bw.lbl_sync_status.text()
    assert "EN VIVO" in status_text
    assert "Tablero mental activo (32 piezas)" in status_text

    # Comprobar estado del mapa mental
    mental_map = bw.sync_mgr.mental_map
    surviving = mental_map.get_surviving_pieces()
    assert len(surviving) == 32
    assert mental_map.get_status_summary() == "32 piezas activas"

    # Verificar identidades iniciales garantizadas
    assert mental_map.piece_type_at(chess.E1) == chess.KING
    assert mental_map.piece_type_at(chess.D1) == chess.QUEEN
    assert mental_map.piece_type_at(chess.G1) == chess.KNIGHT
    assert mental_map.get_piece_name_at(chess.G1) == "Caballo"
    assert mental_map.get_piece_name_at(chess.E2) == "Peón"
    assert mental_map.get_piece_name_at(chess.C1) == "Alfil"

    win.close()


def test_ui_move_display_guaranteed_by_mental_map(qapp):
    """
    Verifica que al ejecutar movimientos, la interfaz gráfica actualiza la píldora de estado
    mostrando la jugada con el nombre de la pieza garantizado por el mapa mental (ej. '● Jugada: Nf3 (Caballo)').
    """
    board_cfg = BoardConfig(id="b_moves", name="Tablero Movimientos Test")
    bw = SingleBoardWidget(board_config=board_cfg)

    # 1. e4 (Peón)
    bw.sync_mgr.push_move(chess.Move.from_uci("e2e4"))
    assert bw.lbl_sync_status.text() == "● Jugada: e4 (Peón)"

    # 1... e5 (Peón)
    bw.sync_mgr.push_move(chess.Move.from_uci("e7e5"))
    assert bw.lbl_sync_status.text() == "● Jugada: e5 (Peón)"

    # 2. Nf3 (Caballo)
    bw.sync_mgr.push_move(chess.Move.from_uci("g1f3"))
    assert bw.lbl_sync_status.text() == "● Jugada: Nf3 (Caballo)"

    # 2... Nc6 (Caballo)
    bw.sync_mgr.push_move(chess.Move.from_uci("b8c6"))
    assert bw.lbl_sync_status.text() == "● Jugada: Nc6 (Caballo)"

    # 3. Bc4 (Alfil)
    bw.sync_mgr.push_move(chess.Move.from_uci("f1c4"))
    assert bw.lbl_sync_status.text() == "● Jugada: Bc4 (Alfil)"

    bw.overlay_window.close()
    bw.close()


def test_arrow_persistence_on_move_played(qapp):
    """
    Verifica que al jugarse un movimiento (_on_move_played), las flechas candidatas
    NO se borran a lista vacía, permaneciendo constantes y suaves en pantalla
    mientras Stockfish calcula, evitando el parpadeo molesto.
    """
    from chess_vision.engine.evaluator import CandidateMove

    board_cfg = BoardConfig(id="b_arrows", name="Tablero Flechas Test", display_mode="overlay")
    bw = SingleBoardWidget(board_config=board_cfg)

    mv = chess.Move.from_uci("e2e4")
    cand = CandidateMove(
        rank=1,
        move=mv,
        san="e4",
        uci="e2e4",
        score_cp=40,
        depth=12
    )
    bw.board_view.set_candidate_moves([cand])
    bw.overlay_window.set_candidate_moves([cand])
    assert len(bw.board_view._candidate_moves) == 1
    assert len(bw.overlay_window._candidate_moves) == 1

    # Simular jugada recibida
    mv = chess.Move.from_uci("e2e4")
    bw.sync_mgr.board.push(mv)
    bw._on_move_played(mv, "e4")

    # Las flechas NO deben borrarse a vacío (cero parpadeos)
    assert len(bw.board_view._candidate_moves) == 1
    assert len(bw.overlay_window._candidate_moves) == 1

    bw.overlay_window.close()
    bw.close()


def test_scan_step_desync_does_not_loop_scan_board_from_screen(qapp, monkeypatch):
    """
    Verifica que ante desincronización visual (ReconcileStatus.DESYNC), scan_step NO
    dispara en bucle scan_board_from_screen() cada 3 fotogramas.
    El estado se mantiene estable como '⚠ Desincronizado' sin tintineos ni sobreescritura.
    """
    import numpy as np
    from unittest.mock import MagicMock
    from chess_vision.game.move_reconciler import MoveReconciler, ReconcileResult, ReconcileStatus
    from chess_vision.capture.screen_capture import ScreenCapture
    from chess_vision.vision.piece_classifier import PieceClassifier

    board_cfg = BoardConfig(id="b_no_loop", name="Test No Loop", region=(0, 0, 400, 400))
    bw = SingleBoardWidget(board_config=board_cfg)

    # Situar la partida en juego activo (1. e4 e5)
    bw.sync_mgr.board.push_san("e4")
    bw.sync_mgr.board.push_san("e5")

    # Mock de captura para retornar un fotograma sintético
    fake_frame = np.ones((400, 400, 3), dtype=np.uint8) * 150
    monkeypatch.setattr(ScreenCapture, "capture_region", lambda r: fake_frame)
    monkeypatch.setattr(PieceClassifier, "get_square_difference_map", lambda s1, s2: {"e4": 0.15})

    # Forzar Reconciler a devolver siempre DESYNC (animación, mano del ratón o discordancia temporal)
    desync_res = ReconcileResult(status=ReconcileStatus.DESYNC)
    monkeypatch.setattr(MoveReconciler, "reconcile", lambda *args, **kwargs: desync_res)

    # Espiar scan_board_from_screen y trigger_analysis
    scan_spy = MagicMock()
    trigger_spy = MagicMock()
    bw.scan_board_from_screen = scan_spy
    bw.trigger_analysis = trigger_spy

    # Inicializar estado previo de casillas
    bw._prev_squares = {"a1": np.zeros((40, 40, 3), dtype=np.uint8)}

    # Ejecutar 12 pasos continuos de scan_step (equivalente a ~1 segundo a 80ms)
    for _ in range(12):
        bw.scan_step()

    # scan_board_from_screen() NUNCA debe llamarse automáticamente en bucle
    assert scan_spy.call_count == 0, f"scan_board_from_screen no debe llamarse en bucle, llamadas: {scan_spy.call_count}"
    # trigger_analysis() tampoco debe dispararse en bucle
    assert trigger_spy.call_count == 0

    # El estado permanece sólidamente en '⚠ Desincronizado' sin alternar con '● Sincronizado automáticamente'
    assert "Desincronizado" in bw.lbl_sync_status.text()

    bw.overlay_window.close()
    bw.close()


def test_candidate_arrows_remain_strictly_static_on_screen(qapp, monkeypatch):
    """
    Verifica que las flechas de recomendación permanecen completamente estáticas y firmes
    en pantalla durante el escaneo continuo mientras no se confirme una jugada legal real.
    No se borran, no cambian y no parpadean.
    """
    import numpy as np
    from chess_vision.engine.evaluator import CandidateMove
    from chess_vision.game.move_reconciler import MoveReconciler, ReconcileResult, ReconcileStatus
    from chess_vision.capture.screen_capture import ScreenCapture

    board_cfg = BoardConfig(id="b_static_arrows", name="Test Static Arrows", region=(0, 0, 400, 400), display_mode="overlay")
    bw = SingleBoardWidget(board_config=board_cfg)

    # 1. Configurar flechas candidatas iniciales
    initial_cands = [
        CandidateMove(rank=1, move=chess.Move.from_uci("g1f3"), san="Nf3", uci="g1f3", score_cp=35, depth=15),
        CandidateMove(rank=2, move=chess.Move.from_uci("b1c3"), san="Nc3", uci="b1c3", score_cp=25, depth=15)
    ]
    bw.board_view.set_candidate_moves(initial_cands)
    bw.overlay_window.set_candidate_moves(initial_cands)

    # 2. Simular fotogramas en vivo con ScreenCapture
    fake_frame = np.ones((400, 400, 3), dtype=np.uint8) * 180
    monkeypatch.setattr(ScreenCapture, "capture_region", lambda r: fake_frame)
    bw._prev_squares = {"a1": np.zeros((40, 40, 3), dtype=np.uint8)}

    # Caso A: Frame sin movimiento (NO_MOVE)
    monkeypatch.setattr(MoveReconciler, "reconcile", lambda *args, **kwargs: ReconcileResult(status=ReconcileStatus.NO_MOVE))
    for _ in range(5):
        bw.scan_step()
        assert bw.board_view._candidate_moves == initial_cands
        assert bw.overlay_window._candidate_moves == initial_cands

    # Caso B: Frame con animación / incertidumbre (UNCERTAIN)
    monkeypatch.setattr(MoveReconciler, "reconcile", lambda *args, **kwargs: ReconcileResult(status=ReconcileStatus.UNCERTAIN))
    for _ in range(5):
        bw.scan_step()
        assert bw.board_view._candidate_moves == initial_cands
        assert bw.overlay_window._candidate_moves == initial_cands

    # Caso C: Frame con desincronización (DESYNC)
    monkeypatch.setattr(MoveReconciler, "reconcile", lambda *args, **kwargs: ReconcileResult(status=ReconcileStatus.DESYNC))
    for _ in range(5):
        bw.scan_step()
        assert bw.board_view._candidate_moves == initial_cands
        assert bw.overlay_window._candidate_moves == initial_cands

    # Las flechas siguen exactamente idénticas e inamovibles (cero parpadeo)
    assert len(bw.board_view._candidate_moves) == 2
    assert bw.board_view._candidate_moves[0].uci == "g1f3"
    assert bw.board_view._candidate_moves[1].uci == "b1c3"

    bw.overlay_window.close()
    bw.close()


def test_screen_scan_does_not_apply_uncertain_king_assignment(qapp, monkeypatch):
    from unittest.mock import MagicMock
    import numpy as np
    from chess_vision.capture.screen_capture import ScreenCapture
    from chess_vision.vision.board_detector import BoardDetector

    widget = SingleBoardWidget(BoardConfig(region=(0, 0, 400, 400), auto_scan=False))
    widget.trigger_analysis = MagicMock()
    widget.sync_mgr.push_move(chess.Move.from_uci("e2e4"))
    previous = widget.sync_mgr.board.fen()
    widget.trigger_analysis.reset_mock()
    monkeypatch.setattr(ScreenCapture, "capture_region", lambda region: np.zeros((400, 400, 3), np.uint8))
    monkeypatch.setattr(BoardDetector, "scan_full_board_fen", lambda **kwargs: (chess.STARTING_FEN, 0.0))
    try:
        widget.scan_board_from_screen()
        assert widget.sync_mgr.board.fen() == previous
        widget.trigger_analysis.assert_not_called()
    finally:
        widget.scan_timer.stop()
        widget.overlay_window.close()
        widget.close()


def test_confirmed_castling_is_applied_in_the_first_frame_without_highlights(qapp, monkeypatch):
    from unittest.mock import MagicMock
    import numpy as np
    from chess_vision.capture.screen_capture import ScreenCapture
    from chess_vision.game.move_reconciler import MoveReconciler, ReconcileResult, ReconcileStatus
    from chess_vision.vision.piece_classifier import PieceClassifier

    widget = SingleBoardWidget(BoardConfig(region=(0, 0, 400, 400), auto_scan=False))
    widget.trigger_analysis = MagicMock()
    widget.sync_mgr.set_fen("r3k2r/8/8/8/8/8/8/R3K2R b KQkq - 0 1")
    frame = np.zeros((400, 400, 3), np.uint8)
    widget._prev_squares = {"e8": frame[:40, :40]}
    monkeypatch.setattr(ScreenCapture, "capture_region", lambda region: frame)
    monkeypatch.setattr(PieceClassifier, "get_square_difference_map", lambda *args: {"e8": 0.20})
    monkeypatch.setattr(PieceClassifier, "get_highlighted_squares", lambda squares: [])
    monkeypatch.setattr(MoveReconciler, "reconcile", lambda *args, **kwargs: ReconcileResult(
        status=ReconcileStatus.CONFIRMED, move=chess.Move.from_uci("e8c8")))
    try:
        widget.scan_step()
        assert widget.sync_mgr.board.piece_at(chess.C8) == chess.Piece(chess.KING, chess.BLACK)
        assert widget.sync_mgr.board.piece_at(chess.D8) == chess.Piece(chess.ROOK, chess.BLACK)
        assert widget.sync_mgr.mental_map.piece_at(chess.C8) == chess.Piece(chess.KING, chess.BLACK)
        assert len(widget.sync_mgr.board.move_stack) == 1
    finally:
        widget.scan_timer.stop()
        widget.overlay_window.close()
        widget.close()
