"""
Suite de pruebas de aceptación para modos de visualización de tableros
(Tablero independiente vs Indicaciones superpuestas / Overlay).
"""

import os
import pytest
import chess

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from chess_vision.config import AppConfig, BoardConfig
from chess_vision.ui.main_window import MainWindow, SingleBoardWidget
from chess_vision.ui.screen_board_overlay import ScreenBoardOverlay
from chess_vision.ui.board_config_dialog import BoardConfigDialog
from chess_vision.ui.initial_setup_dialog import InitialSetupDialog
from chess_vision.engine.evaluator import CandidateMove, PositionAnalysis
from chess_vision.engine.classifier import MoveClassification


@pytest.fixture(scope="session")
def qapp():
    """Garantiza una única instancia de QApplication para la suite de pruebas."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_board_config_display_mode():
    """Test 1: Configuración de display_mode en BoardConfig (default, serialización y deserialización)."""
    cfg = BoardConfig()
    # Por defecto debe ser 'independent'
    assert cfg.display_mode == "independent"

    # Serialización to_dict
    cfg.display_mode = "overlay"
    data = cfg.to_dict()
    assert "display_mode" in data
    assert data["display_mode"] == "overlay"

    # Deserialización from_dict
    reconstructed = BoardConfig.from_dict(data)
    assert reconstructed.display_mode == "overlay"

    # Fallback seguro cuando no existe la clave en json antiguo
    old_data = {"id": "board_legacy", "name": "Antiguo"}
    legacy_cfg = BoardConfig.from_dict(old_data)
    assert legacy_cfg.display_mode == "independent"


def test_screen_board_overlay_properties(qapp):
    """Test 2: ScreenBoardOverlay propiedades de ventana, anti-captura, geometría y renderizado."""
    overlay = ScreenBoardOverlay()

    # Flags de ventana requeridas
    flags = overlay.windowFlags()
    assert bool(flags & Qt.WindowType.FramelessWindowHint)
    assert bool(flags & Qt.WindowType.WindowStaysOnTopHint)
    assert bool(flags & Qt.WindowType.Tool)

    # Atributos de transparencia y clicks del ratón
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    # Posicionamiento y geometría
    region = (120, 80, 480, 480)
    overlay.update_geometry(region)
    assert overlay.geometry().x() == 120
    assert overlay.geometry().y() == 80
    assert overlay.geometry().width() == 480
    assert overlay.geometry().height() == 480

    # Candidatos y trazado de flechas
    cand = CandidateMove(
        rank=1,
        move=chess.Move.from_uci("e2e4"),
        san="e4",
        uci="e2e4",
        score_cp=40,
        win_rate=54.0,
        classification=MoveClassification(
            category="best", label="Mejor jugada", symbol="★", badge_color="#26C2A3",
            delta_cp=0.0, win_rate_loss=0.0, description=""
        )
    )
    overlay.set_candidate_moves([cand])
    assert len(overlay._candidate_moves) == 1
    assert overlay.is_overlay_visible() is True

    # Comprobar que no falla el pintado
    overlay.repaint()

    # Limpiar flechas
    overlay.clear_arrows()
    assert len(overlay._candidate_moves) == 0

    # Alternar visibilidad del overlay
    overlay.set_overlay_visible(False)
    assert overlay.is_overlay_visible() is False

    overlay.close()


def test_single_board_widget_mode_switching(qapp):
    """Test 3: Conmutación de modo en SingleBoardWidget (independent a overlay y viceversa)."""
    cfg = BoardConfig(id="board_1", display_mode="independent", region=(100, 100, 400, 400))
    bw = SingleBoardWidget(cfg)
    bw.show()

    # Estado inicial: independiente
    assert bw.config.display_mode == "independent"
    assert not bw.board_view.isHidden()
    assert bw.overlay_window.isHidden()
    assert bw.compact_overlay_panel.isHidden()
    assert "Overlay: Desactivado" in bw.btn_switch_mode.text()

    # Conmutar a modo 'overlay' (tablero interno permanece SIEMPRE visible)
    bw.set_display_mode("overlay")
    assert bw.config.display_mode == "overlay"
    assert not bw.board_view.isHidden()
    assert bw.compact_overlay_panel.isHidden()
    assert not bw.overlay_window.isHidden()
    assert "Overlay: Activado" in bw.btn_switch_mode.text()

    # Conmutar de vuelta a 'independent'
    bw.set_display_mode("independent")
    assert bw.config.display_mode == "independent"
    assert not bw.board_view.isHidden()
    assert bw.compact_overlay_panel.isHidden()
    assert bw.overlay_window.isHidden()
    assert "Overlay: Desactivado" in bw.btn_switch_mode.text()

    bw.overlay_window.close()
    bw.close()


def test_two_boards_simultaneous_acceptance(qapp):
    """
    Test 4 (PRUEBA PRINCIPAL DE ACEPTACIÓN):
    Configurar dos tableros:
    - Tablero 1: superpuesto (overlay).
    - Tablero 2: independiente (independent).
    - Verificar que el Tablero 1 proyecta en ScreenBoardOverlay Y AL MISMO TIEMPO mantiene visible su board_view interno con las mismas jugadas.
    - Verificar que el Tablero 2 muestra indicaciones sobre su board_view interno.
    - Verificar que ambos tableros mantienen sus partidas, instancias de motor Stockfish independientes y ejecutan su seguimiento simultáneamente.
    """
    app_cfg = AppConfig(active_board_count=2)
    app_cfg.boards[0].id = "board_1"
    app_cfg.boards[0].name = "Tablero Alpha (Overlay)"
    app_cfg.boards[0].display_mode = "overlay"
    app_cfg.boards[0].region = (50, 50, 400, 400)

    app_cfg.boards[1].id = "board_2"
    app_cfg.boards[1].name = "Tablero Beta (Independiente)"
    app_cfg.boards[1].display_mode = "independent"
    app_cfg.boards[1].region = (500, 50, 400, 400)

    win = MainWindow(config=app_cfg)
    win.show()

    # Verificar que MainWindow activó 2 tableros
    assert win.config.active_board_count == 2
    assert len(win.stockfish_engines) == 2
    assert "board_1" in win.stockfish_engines
    assert "board_2" in win.stockfish_engines

    bw1 = win._board_widgets["board_1"]
    bw2 = win._board_widgets["board_2"]

    # Verificar instancias dedicadas independientes de Stockfish
    assert bw1.stockfish_mgr is not None
    assert bw2.stockfish_mgr is not None
    assert bw1.stockfish_mgr is not bw2.stockfish_mgr

    # 1. Verificar visibilidades según su modo (el tablero interno SIEMPRE es visible)
    assert bw1.config.display_mode == "overlay"
    assert not bw1.board_view.isHidden()
    assert not bw1.overlay_window.isHidden()

    assert bw2.config.display_mode == "independent"
    assert not bw2.board_view.isHidden()
    assert bw2.overlay_window.isHidden()

    # 2. Generar análisis independiente para el Tablero 1 (Overlay)
    cand_t1 = CandidateMove(
        rank=1, move=chess.Move.from_uci("e2e4"), san="e4", uci="e2e4",
        score_cp=35, win_rate=53.5
    )
    analysis1 = PositionAnalysis(
        fen=chess.STARTING_FEN,
        turn=chess.WHITE,
        top_moves=[cand_t1],
        best_move=cand_t1
    )
    bw1._on_analysis_received("board_1", analysis1)

    # Comprobar que Tablero 1 envió las indicaciones simultáneamente a ScreenBoardOverlay Y a board_view
    assert len(bw1.overlay_window._candidate_moves) == 1
    assert bw1.overlay_window._candidate_moves[0].uci == "e2e4"
    assert len(bw1.board_view._candidate_moves) == 1
    assert bw1.board_view._candidate_moves[0].uci == "e2e4"

    # 3. Generar análisis independiente para el Tablero 2 (Independiente)
    cand_t2 = CandidateMove(
        rank=1, move=chess.Move.from_uci("d2d4"), san="d4", uci="d2d4",
        score_cp=28, win_rate=52.8
    )
    analysis2 = PositionAnalysis(
        fen=chess.STARTING_FEN,
        turn=chess.WHITE,
        top_moves=[cand_t2],
        best_move=cand_t2
    )
    bw2._on_analysis_received("board_2", analysis2)

    # Comprobar que Tablero 2 envió las indicaciones a su board_view interno y su overlay está vacío
    assert len(bw2.board_view._candidate_moves) == 1
    assert bw2.board_view._candidate_moves[0].uci == "d2d4"
    assert len(bw2.overlay_window._candidate_moves) == 0

    # 4. Verificar que mantienen partidas independientes y ejecutan simultáneamente
    bw1.sync_mgr.push_move(chess.Move.from_uci("e2e4"))
    bw2.sync_mgr.push_move(chess.Move.from_uci("g1f3"))

    assert bw1.sync_mgr.board.piece_at(chess.E4) == chess.Piece(chess.PAWN, chess.WHITE)
    assert bw1.sync_mgr.board.piece_at(chess.F3) is None

    assert bw2.sync_mgr.board.piece_at(chess.F3) == chess.Piece(chess.KNIGHT, chess.WHITE)
    assert bw2.sync_mgr.board.piece_at(chess.E4) is None

    # Ambos temporizadores de seguimiento están activos
    assert bw1.scan_timer.isActive()
    assert bw2.scan_timer.isActive()

    win.close()


def test_initial_setup_dialog(qapp):
    """Test 5: InitialSetupDialog inicializa los tableros, permite alternar modos y regiones, y aplica la configuración."""
    app_cfg = AppConfig(active_board_count=1)
    dlg = InitialSetupDialog(app_cfg)
    dlg.show()

    # Verificar estado inicial: 1 tablero activo visible en UI
    assert dlg.cmb_count.currentIndex() == 0
    assert dlg._board_groups["board_1"]["group_box"].isVisible()
    assert not dlg._board_groups["board_2"]["group_box"].isVisible()

    # Seleccionar 2 tableros
    dlg.cmb_count.setCurrentIndex(1)
    assert dlg._board_groups["board_1"]["group_box"].isVisible()
    assert dlg._board_groups["board_2"]["group_box"].isVisible()
    assert not dlg._board_groups["board_3"]["group_box"].isVisible()

    # Modificar configuraciones: Tablero 1 como overlay, Tablero 2 como independent
    dlg._board_groups["board_1"]["rb_overlay"].setChecked(True)
    dlg.set_board_region("board_1", (10, 20, 300, 300))

    dlg._board_groups["board_2"]["rb_independent"].setChecked(True)
    dlg.set_board_region("board_2", (400, 20, 300, 300))

    # Aplicar e iniciar seguimiento
    dlg._apply_and_start()

    assert app_cfg.active_board_count == 2
    assert app_cfg.boards[0].display_mode == "overlay"
    assert app_cfg.boards[0].region == (10, 20, 300, 300)
    assert app_cfg.boards[1].display_mode == "independent"
    assert app_cfg.boards[1].region == (400, 20, 300, 300)

    dlg.close()


def test_board_config_dialog_display_mode(qapp):
    """Verifica que BoardConfigDialog permite seleccionar y guardar el modo de visualización."""
    cfg = BoardConfig(id="b_test", name="Tablero Prueba", display_mode="independent")
    dlg = BoardConfigDialog(cfg)

    assert hasattr(dlg, "cmb_display_mode")
    assert dlg.cmb_display_mode.currentIndex() == 0

    # Cambiar a modo superpuesto
    dlg.cmb_display_mode.setCurrentIndex(1)
    dlg._save_and_accept()

    assert cfg.display_mode == "overlay"
