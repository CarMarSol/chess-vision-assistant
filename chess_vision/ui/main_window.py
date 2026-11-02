"""
Ventana Principal de Chess Vision Assistant.
Soporta de 1 a 4 tableros en cuadrícula dinámica, captura en tiempo real,
gestión de Stockfish y visualización Multi-PV interactiva.
"""

from __future__ import annotations
from chess_vision.i18n import LANGUAGES, set_language, tr, board_name
import os
from typing import List, Dict, Optional
import chess
import numpy as np

from PySide6.QtCore import Qt, QTimer, Slot, Signal
from PySide6.QtGui import QIcon, QFont, QColor, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QToolBar, QStatusBar, QMessageBox,
    QFrame, QSizePolicy
)

from chess_vision.config import AppConfig, BoardConfig
from chess_vision.capture.screen_capture import ScreenCapture
from chess_vision.capture.region_selector import RegionSelectorWindow
from chess_vision.vision.board_detector import BoardDetector
from chess_vision.vision.piece_classifier import PieceClassifier
from chess_vision.vision.orientation import OrientationDetector
from chess_vision.engine.stockfish_manager import StockfishManager
from chess_vision.engine.evaluator import PositionAnalysis
from chess_vision.engine.accuracy_tracker import AccuracyTracker, AccuracySummary
from chess_vision.game.sync_manager import SyncManager
from chess_vision.ui.board_view import BoardView
from chess_vision.ui.eval_panel import EvalPanel
from chess_vision.ui.board_config_dialog import BoardConfigDialog
from chess_vision.ui.test_simulation_dialog import SimulationDialog
from chess_vision.ui.screen_board_overlay import ScreenBoardOverlay
from chess_vision.ui.initial_setup_dialog import InitialSetupDialog
from chess_vision.ui.theme import Theme


class SingleBoardWidget(QFrame):
    """
    Widget integral para un tablero individual:
    incluye cabecera, vista del tablero, panel de evaluación y lógica de captura/sincronización.
    """
    region_request = Signal(str)  # emite board_id

    def __init__(
        self,
        board_config: BoardConfig,
        stockfish_manager: Optional[StockfishManager] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.config = board_config
        self.stockfish_mgr = stockfish_manager

        self.sync_mgr = SyncManager()
        self.accuracy_tracker = AccuracyTracker()
        self._prev_frame: Optional[np.ndarray] = None
        self._prev_squares: Dict[str, np.ndarray] = {}
        self._current_analysis: Optional[PositionAnalysis] = None

        # Control de versiones y persistencia de edición manual
        self.board_version: int = 0
        self.is_manual_paused: bool = False

        # Debounce temporal de confirmación (2 frames)
        self._pending_move: Optional[chess.Move] = None
        self._pending_chain: Optional[List[chess.Move]] = None
        self._pending_move_count: int = 0
        self._orientation_locked: bool = (self.config.orientation in ("white", "black"))
        self._desync_frames: int = 0

        # Superposición transparente para pantalla
        self.overlay_window = ScreenBoardOverlay()
        if self.config.region:
            self.overlay_window.update_geometry(self.config.region)
        self.overlay_window.set_orientation("white" if self.config.orientation != "black" else "black")

        self.setObjectName("SingleBoardCard")
        self._theme: str = "dark"
        self._sync_status_text: str = tr("● Listo")
        self._sync_status_type: str = "ready"
        self.setStyleSheet(Theme.get_single_board_card_style(self._theme))

        self._build_ui()
        self._connect_signals()
        self.set_display_mode(getattr(self.config, "display_mode", "independent"))
        self.set_theme("dark")

        # Temporizador de escaneo en tiempo real
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.scan_step)
        if self.config.auto_scan and self.config.region:
            self.scan_timer.start(self.config.scan_interval_ms)

    def set_sync_status(self, text: str, status_type: str = "ready") -> None:
        """Actualiza el texto y la píldora de sincronización con estilo coherente al tema."""
        self._sync_status_text = text
        self._sync_status_type = status_type
        self.lbl_sync_status.setText(text)
        self.lbl_sync_status.setStyleSheet(Theme.get_sync_badge_style(status_type, self._theme))

    def set_theme(self, theme_name: str) -> None:
        """Aplica el tema claro u oscuro a la tarjeta, botones, etiquetas y subcomponentes."""
        self._theme = theme_name
        t = Theme.get_tokens(theme_name)
        self.setStyleSheet(Theme.get_single_board_card_style(theme_name))
        self.lbl_title.setStyleSheet(f"color: {t['text_primary']}; font-weight: bold; font-size: 13px;")

        # Botones y acciones interactivas
        self.btn_select_region.setStyleSheet(Theme.get_button_style("primary", theme_name))
        self.btn_rescan_screen.setStyleSheet(Theme.get_button_style("secondary", theme_name))
        self.btn_cfg.setStyleSheet(Theme.get_button_style("config", theme_name))
        self.btn_resync.setStyleSheet(Theme.get_button_style("resync", theme_name))

        is_ov = (getattr(self.config, "display_mode", "independent") == "overlay")
        self.btn_switch_mode.setStyleSheet(Theme.get_button_style("overlay_active" if is_ov else "overlay_inactive", theme_name))
        self.btn_flip.setStyleSheet(Theme.get_button_style("neutral", theme_name))
        self.btn_reset.setStyleSheet(Theme.get_button_style("neutral", theme_name))
        self.btn_pause_scan.setStyleSheet(Theme.get_button_style("neutral", theme_name))

        # Píldora de estado de sincronización
        self.set_sync_status(self._sync_status_text, self._sync_status_type)

        # Tablero y panel de evaluación
        self.board_view.set_app_theme(theme_name)
        self.eval_panel.set_theme(theme_name)

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # 1. Cabecera del tablero
        header = QHBoxLayout()
        header.setSpacing(6)

        self.lbl_title = QLabel(board_name(self.config.name))
        self.lbl_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header.addWidget(self.lbl_title)

        self.lbl_sync_status = QLabel(tr("● Listo"))
        header.addWidget(self.lbl_sync_status)

        header.addStretch()

        # Selector visible de perspectiva / color con el que juega el usuario
        self.cmb_perspective = QComboBox()
        self.cmb_perspective.addItems([tr("⟳ Auto"), tr("♙ Blancas abajo"), tr("♟ Negras abajo")])
        self.cmb_perspective.setToolTip(tr("Selector de perspectiva: Auto-detectar, o fijar Blancas / Negras abajo"))
        self.cmb_perspective.setCursor(Qt.CursorShape.PointingHandCursor)
        if self.config.orientation == "white":
            self.cmb_perspective.setCurrentIndex(1)
        elif self.config.orientation == "black":
            self.cmb_perspective.setCurrentIndex(2)
        else:
            self.cmb_perspective.setCurrentIndex(0)
        self.cmb_perspective.currentIndexChanged.connect(self._on_perspective_changed)
        header.addWidget(self.cmb_perspective)

        # Botón Prominente de Elo y Ajustes (Claro y directo para el usuario)
        self.btn_cfg = QPushButton(tr('⚙ Ajustes · Elo: {value0}', value0=self.config.elo))
        self.btn_cfg.setToolTip(tr("Hacer clic para cambiar Nivel de Elo (700-2800), Estilo de juego y Esfuerzo de Stockfish"))
        self.btn_cfg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cfg.clicked.connect(self._open_config_dialog)
        header.addWidget(self.btn_cfg)

        # Botón Seleccionar Región
        self.btn_select_region = QPushButton(tr("✂ Recortar"))
        self.btn_select_region.setToolTip(tr("Seleccionar región de pantalla con recortes"))
        self.btn_select_region.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_select_region.clicked.connect(lambda: self.region_request.emit(self.config.id))
        header.addWidget(self.btn_select_region)

        # Botón Escanear Pantalla (Auto-recuperación visual FEN)
        self.btn_rescan_screen = QPushButton(tr("🔍 Escanear Pantalla"))
        self.btn_rescan_screen.setToolTip(tr("Escanear las 64 fichas de la pantalla física y reconstruir la posición FEN exacta"))
        self.btn_rescan_screen.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_rescan_screen.clicked.connect(self.scan_board_from_screen)
        header.addWidget(self.btn_rescan_screen)

        # Botón Sincronizar Tablero
        self.btn_resync = QPushButton(tr("🔄 Sincronizar"))
        self.btn_resync.setToolTip(tr("Forzar re-sincronización y comprobación completa del tablero actual"))
        self.btn_resync.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_resync.clicked.connect(self.resync_board)
        header.addWidget(self.btn_resync)

        # Botón Invertir Orientación
        self.btn_flip = QPushButton(tr("⟳ Girar"))
        self.btn_flip.setToolTip(tr("Invertir orientación del tablero (Blancas/Negras)"))
        self.btn_flip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_flip.clicked.connect(self._toggle_orientation)
        header.addWidget(self.btn_flip)

        # Botón Reiniciar
        self.btn_reset = QPushButton(tr("↺ Reiniciar"))
        self.btn_reset.setToolTip(tr("Reiniciar a posición inicial y recalibrar"))
        self.btn_reset.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_board)
        header.addWidget(self.btn_reset)

        # Conmutador unificado de modo Overlay ("independent" vs "overlay")
        is_ov = (getattr(self.config, "display_mode", "independent") == "overlay")
        self.btn_switch_mode = QPushButton(tr("👁 Overlay: Activado") if is_ov else tr("👁 Overlay: Desactivado"))
        self.btn_switch_mode.setToolTip(tr("Activar o desactivar superposición de flechas directamente sobre la pantalla"))
        self.btn_switch_mode.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_switch_mode.clicked.connect(self._on_switch_mode_clicked)
        header.addWidget(self.btn_switch_mode)

        # Botón pausar/reanudar escaneo continuo
        self.btn_pause_scan = QPushButton(tr("⏸ Pausar"))
        self.btn_pause_scan.setToolTip(tr("Pausar o reanudar el escaneo continuo en pantalla"))
        self.btn_pause_scan.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_pause_scan.clicked.connect(self._on_toggle_scan_clicked)
        header.addWidget(self.btn_pause_scan)

        # Botón auxiliar de overlay (mantenido por compatibilidad)
        self.btn_toggle_overlay = QPushButton(tr("👁 Overlay"), self)
        self.btn_toggle_overlay.setVisible(False)
        self.btn_toggle_overlay.clicked.connect(self._on_toggle_overlay_clicked)
        header.addWidget(self.btn_toggle_overlay)

        main_layout.addLayout(header)

        # 2. Área Central: Tablero + Panel de Evaluación / Vista Compacta Overlay
        body_layout = QHBoxLayout()
        body_layout.setSpacing(8)

        self.board_view = BoardView(self)
        self.board_view.set_orientation("white" if self.config.orientation != "black" else "black")
        self.board_view.set_show_arrows(self.config.show_arrows)
        self.board_view.set_theme(getattr(self.config, "board_theme", "green"))
        body_layout.addWidget(self.board_view, stretch=3)

        # Panel compacto overlay desactivado: el tablero interno permanece SIEMPRE VISIBLE
        self.compact_overlay_panel = QFrame(self)
        self.compact_overlay_panel.hide()

        self.eval_panel = EvalPanel(self)
        self.eval_panel.setVisible(self.config.show_eval_bar)
        body_layout.addWidget(self.eval_panel, stretch=2)

        main_layout.addLayout(body_layout)

    def _connect_signals(self) -> None:
        self.sync_mgr.move_played.connect(self._on_move_played)
        self.sync_mgr.board_reset.connect(self._on_board_reset)
        self.sync_mgr.desync_detected.connect(self._on_desync)
        if self.stockfish_mgr:
            self.stockfish_mgr.analysis_ready.connect(self._on_analysis_received)
        self.board_view.board_edited.connect(self._on_manual_board_edit)

    def set_stockfish_manager(self, stockfish_manager: StockfishManager) -> None:
        """Asigna una instancia dedicada de Stockfish a este tablero."""
        if self.stockfish_mgr:
            try:
                self.stockfish_mgr.analysis_ready.disconnect(self._on_analysis_received)
            except Exception:
                pass
        self.stockfish_mgr = stockfish_manager
        if self.stockfish_mgr:
            self.stockfish_mgr.analysis_ready.connect(self._on_analysis_received)
            self.trigger_analysis()

    def _on_perspective_changed(self, index: int) -> None:
        """Maneja el selector de perspectiva/color del usuario."""
        if index == 1:
            self.config.orientation = "white"
            self.board_view.set_orientation("white")
            self.overlay_window.set_orientation("white")
            self._orientation_locked = True
        elif index == 2:
            self.config.orientation = "black"
            self.board_view.set_orientation("black")
            self.overlay_window.set_orientation("black")
            self._orientation_locked = True
        else:
            self.config.orientation = "auto"
            self._orientation_locked = False

        self._prev_frame = None
        self._prev_squares.clear()
        self._pending_move = None
        self._pending_move_count = 0
        self.trigger_analysis()

    def _on_manual_board_edit(self, fen: str) -> None:
        """Maneja la edición manual desde el menú contextual del tablero."""
        self.board_version += 1
        self.is_manual_paused = True
        self.scan_timer.stop()
        self.sync_mgr.set_fen(fen)
        self.accuracy_tracker.reset()
        self.eval_panel.reset_accuracy()
        self._prev_frame = None
        self._prev_squares.clear()
        self._pending_move = None
        self._pending_move_count = 0
        self.overlay_window.clear_arrows()
        self.board_view.set_candidate_moves([])
        self.set_sync_status(tr("● Edición manual (Pausado)"), "paused")
        self._current_analysis = None
        self.trigger_analysis()

    def set_region(self, region: Tuple[int, int, int, int]) -> None:
        """Asigna la región de pantalla para la captura de este tablero e inicia de inmediato."""
        self.config.region = region
        self._prev_frame = None
        self._prev_squares.clear()
        self.is_manual_paused = False
        self.board_version += 1

        self.overlay_window.update_geometry(region)
        self.overlay_window.set_orientation(self.board_view._orientation)
        if getattr(self.config, "display_mode", "independent") == "overlay":
            if self._current_analysis:
                self.overlay_window.set_candidate_moves(self._current_analysis.top_moves)
            self.overlay_window.show()

        # Captura el fotograma inicial inmediatamente sin esperas
        frame = ScreenCapture.capture_region(region)
        if frame is not None:
            current_squares = BoardDetector.extract_squares(
                image=frame,
                orientation=self.board_view._orientation,
                margin_pct=self.config.margin_pct,
                inset_pct=self.config.cell_inset_pct
            )

            # Detectar orientación inicial si está en 'auto' y no bloqueada
            if not self._orientation_locked and self.config.orientation == "auto":
                detected_ori = OrientationDetector.detect_from_square_images(current_squares)
                self.board_view.set_orientation(detected_ori)
                self.overlay_window.set_orientation(detected_ori)
                self.cmb_perspective.blockSignals(True)
                self.cmb_perspective.setCurrentIndex(1 if detected_ori == "white" else 2)
                self.cmb_perspective.blockSignals(False)
                current_squares = BoardDetector.extract_squares(
                    image=frame,
                    orientation=detected_ori,
                    margin_pct=self.config.margin_pct,
                    inset_pct=self.config.cell_inset_pct
                )

            self._prev_squares = current_squares

            # Verificar si las casillas centrales están vacías o si la partida ya empezó
            if PieceClassifier.are_center_ranks_empty(current_squares):
                # Partida en posición inicial: reset formal del tablero y mapa mental con 32 piezas
                self.sync_mgr.reset()
                surviving_count = len(self.sync_mgr.mental_map.get_surviving_pieces())
                self.set_sync_status(tr('● EN VIVO · Tablero mental activo ({value0} piezas)', value0=surviving_count), "ready")
            else:
                # Partida ya iniciada con casillas centrales ocupadas: escanear pantalla e inicializar mapa mental
                self.scan_board_from_screen()
        else:
            # En ausencia de fotograma (modo offscreen o test), asegurar inicialización formal de las 32 piezas
            self.sync_mgr.reset()
            surviving_count = len(self.sync_mgr.mental_map.get_surviving_pieces())
            self.set_sync_status(tr('● EN VIVO · Tablero mental activo ({value0} piezas)', value0=surviving_count), "ready")

        # Iniciar temporizador a alta frecuencia (80 ms) para respuesta instantánea
        scan_interval = min(self.config.scan_interval_ms, 80) if self.config.scan_interval_ms > 0 else 80
        self.scan_timer.start(scan_interval)

        # Disparar análisis asíncrono de inmediato
        self.trigger_analysis()

    def _toggle_orientation(self) -> None:
        new_ori = "black" if self.board_view._orientation == "white" else "white"
        self.config.orientation = new_ori
        self._orientation_locked = True
        self.board_view.set_orientation(new_ori)
        self.overlay_window.set_orientation(new_ori)
        self.cmb_perspective.blockSignals(True)
        self.cmb_perspective.setCurrentIndex(1 if new_ori == "white" else 2)
        self.cmb_perspective.blockSignals(False)
        self._prev_frame = None
        self._prev_squares.clear()
        self._pending_move = None
        self._pending_move_count = 0
        self.trigger_analysis()

    def _open_config_dialog(self) -> None:
        dlg = BoardConfigDialog(self.config, self, theme=self._theme)
        if dlg.exec():
            self.lbl_title.setText(board_name(self.config.name))
            self.btn_cfg.setText(tr('⚙ Ajustes · Elo: {value0}', value0=self.config.elo))
            self.board_view.set_show_arrows(self.config.show_arrows)
            self.board_view.set_theme(getattr(self.config, "board_theme", "green"))
            self.eval_panel.setVisible(self.config.show_eval_bar)
            if self.config.orientation in ("white", "black"):
                self.board_view.set_orientation(self.config.orientation)
                self.overlay_window.set_orientation(self.config.orientation)

            self.set_display_mode(getattr(self.config, "display_mode", "independent"))

            if self.config.auto_scan and self.config.region:
                self.scan_timer.start(self.config.scan_interval_ms)
            else:
                self.scan_timer.stop()

            # Forzar re-análisis con nuevos parámetros
            self.trigger_analysis()

    def reset_board(self) -> None:
        self.sync_mgr.reset()
        self.accuracy_tracker.reset()
        self.eval_panel.reset_accuracy()
        self._prev_frame = None
        self._prev_squares.clear()
        self.overlay_window.clear_arrows()
        self.board_view.set_candidate_moves([])
        self.set_sync_status(tr("● Listo"), "ready")
        self.trigger_analysis()

    def set_display_mode(self, mode: str) -> None:
        """Conmuta fluidamente entre 'independent' y 'overlay' manteniendo el tablero interno siempre visible y sincronizado."""
        if mode not in ("independent", "overlay"):
            mode = "independent"
        self.config.display_mode = mode

        # El tablero interno permanece SIEMPRE VISIBLE en ambos modos
        self.board_view.show()
        if hasattr(self, "compact_overlay_panel"):
            self.compact_overlay_panel.hide()

        if mode == "overlay":
            self.btn_switch_mode.setText(tr("👁 Overlay: Activado"))
            self.btn_switch_mode.setStyleSheet(Theme.get_button_style("overlay_active", self._theme))
            self.btn_toggle_overlay.setVisible(False)
            self.btn_pause_scan.setVisible(True)
            self.overlay_window.set_overlay_visible(True)
            if self.config.region:
                self.overlay_window.update_geometry(self.config.region)
                self.overlay_window.set_orientation(self.board_view._orientation)
                if self._current_analysis:
                    self.overlay_window.set_candidate_moves(self._current_analysis.top_moves)
                self.overlay_window.show()
            if self._current_analysis:
                self.board_view.set_candidate_moves(self._current_analysis.top_moves)
        else:
            self.btn_switch_mode.setText(tr("👁 Overlay: Desactivado"))
            self.btn_switch_mode.setStyleSheet(Theme.get_button_style("overlay_inactive", self._theme))
            self.btn_toggle_overlay.setVisible(False)
            self.btn_pause_scan.setVisible(False)
            self.overlay_window.set_overlay_visible(False)
            self.overlay_window.clear_arrows()
            self.overlay_window.hide()
            if self._current_analysis:
                self.board_view.set_candidate_moves(self._current_analysis.top_moves)

    def _on_switch_mode_clicked(self) -> None:
        target = "overlay" if getattr(self.config, "display_mode", "independent") == "independent" else "independent"
        self.set_display_mode(target)

    def _on_toggle_scan_clicked(self) -> None:
        if self.scan_timer.isActive():
            self.scan_timer.stop()
            self.btn_pause_scan.setText(tr("▶ Reanudar"))
            self.set_sync_status(tr("● Escaneo en pausa"), "paused")
        else:
            interval = min(self.config.scan_interval_ms, 80) if self.config.scan_interval_ms > 0 else 80
            self.scan_timer.start(interval)
            self.btn_pause_scan.setText(tr("⏸ Pausar"))
            self.set_sync_status(tr("● EN VIVO (Sincronizado)"), "ready")

    def _on_toggle_overlay_clicked(self) -> None:
        target = "independent" if getattr(self.config, "display_mode", "independent") == "overlay" else "overlay"
        self.set_display_mode(target)

    def set_custom_fen(self, fen: str) -> None:
        if self.sync_mgr.set_fen(fen):
            self.accuracy_tracker.reset()
            self.eval_panel.reset_accuracy()
            self.board_view.set_board(self.sync_mgr.board)
            self._prev_frame = None
            self._prev_squares.clear()
            self.trigger_analysis()

    def _on_move_played(self, move: chess.Move, san: str) -> None:
        # Evaluar y registrar la precisión del movimiento realizado
        board_before = self.sync_mgr.board.copy()
        if board_before.move_stack:
            board_before.pop()
        self.accuracy_tracker.record_move_from_board(
            board_before=board_before,
            move=move,
            previous_analysis=self._current_analysis
        )
        self.eval_panel.update_accuracy(self.accuracy_tracker.get_summary())

        self.board_view.set_board(self.sync_mgr.board)
        # Persistencia suave de flechas: NO borrar las flechas a vacío mientras Stockfish calcula;
        # se reemplazan de inmediato cuando llegue _on_analysis_received evitando el parpadeo.
        # Garantía del mapa mental: identificar la pieza trasladada con certeza absoluta
        piece_name = self.sync_mgr.mental_map.get_piece_name_at(move.to_square)
        piece_label = f" ({tr(piece_name)})" if piece_name else ""
        self.set_sync_status(tr('● Jugada: {value0}{value1}', value0=san, value1=piece_label), "ready")
        self.trigger_analysis()

    def _on_board_reset(self) -> None:
        self.accuracy_tracker.reset()
        self.eval_panel.reset_accuracy()
        self.board_view.set_board(self.sync_mgr.board)

    def _on_desync(self, msg: str) -> None:
        self.set_sync_status(tr("⚠ Desincronizado"), "desync")

    def scan_step(self) -> None:
        """Paso de captura continua con reconciliación física directa y debounce temporal."""
        if not self.config.region or self.is_manual_paused:
            return

        # 1. Capturar región (~1ms vía QScreen o MSS)
        frame = ScreenCapture.capture_region(self.config.region)
        if frame is None:
            return

        # 2. Extraer casillas según la orientación actual
        current_squares = BoardDetector.extract_squares(
            image=frame,
            orientation=self.board_view._orientation,
            margin_pct=self.config.margin_pct,
            inset_pct=self.config.cell_inset_pct
        )

        # Si aún no tenemos casillas previas guardadas
        if not self._prev_squares:
            self._prev_squares = current_squares

            # Detectar orientación inicial si está en 'auto' y no bloqueada por el usuario
            if not self._orientation_locked and self.config.orientation == "auto":
                detected_ori = OrientationDetector.detect_from_square_images(current_squares)
                self.board_view.set_orientation(detected_ori)
                self.overlay_window.set_orientation(detected_ori)
                self.cmb_perspective.blockSignals(True)
                self.cmb_perspective.setCurrentIndex(1 if detected_ori == "white" else 2)
                self.cmb_perspective.blockSignals(False)
                current_squares = BoardDetector.extract_squares(
                    image=frame,
                    orientation=detected_ori,
                    margin_pct=self.config.margin_pct,
                    inset_pct=self.config.cell_inset_pct
                )
                self._prev_squares = current_squares

            # Auto-sincronizar si el usuario recortó cuando ya se habían hecho jugadas (ej. 1. e4 e5)
            if self.sync_mgr.board.fen() == chess.STARTING_FEN:
                if not PieceClassifier.are_center_ranks_empty(current_squares):
                    self.scan_board_from_screen()
                    return

            surviving_count = len(self.sync_mgr.mental_map.get_surviving_pieces())
            self.set_sync_status(tr('● EN VIVO · Tablero mental activo ({value0} piezas)', value0=surviving_count), "ready")
            self.trigger_analysis()
            return

        # Regla de oro del inicio: si el tablero sigue en STARTING_FEN y las filas 3-6 están 100% vacías,
        # la partida aún no ha comenzado (no forzar ningún movimiento).
        if self.sync_mgr.board.fen() == chess.STARTING_FEN:
            if PieceClassifier.are_center_ranks_empty(current_squares):
                self._prev_squares = current_squares
                return

        # 3. Detección visual en tiempo real: diferencias y casillas resaltadas
        diff_map = PieceClassifier.get_square_difference_map(self._prev_squares, current_squares)
        hl_squares = PieceClassifier.get_highlighted_squares(current_squares)
        max_diff = max(diff_map.values(), default=0.0)

        # Si no hay cambio visual perceptible (<0.035) y no hay casillas resaltadas
        if max_diff < 0.035 and not hl_squares:
            return

        from chess_vision.game.move_reconciler import MoveReconciler, ReconcileStatus
        observed = MoveReconciler.build_observations(current_squares, self._prev_squares, hl_squares, diff_map)
        rec_res = MoveReconciler.reconcile(
            self.sync_mgr.board,
            observed,
            hl_squares,
            diff_map,
            mental_map=self.sync_mgr.mental_map
        )

        if rec_res.status == ReconcileStatus.NO_MOVE:
            return

        if rec_res.status == ReconcileStatus.UNCERTAIN:
            # Ambigüedad o movimiento a mitad de animación: mantener flechas suaves sin parpadeo
            self._pending_move = None
            self._pending_chain = None
            self._pending_move_count = 0
            self.set_sync_status(tr("⌛ Posición pendiente de confirmar"), "paused")
            return

        if rec_res.status == ReconcileStatus.CONFIRMED:
            cand_mv = rec_res.move
            is_castling = cand_mv is not None and self.sync_mgr.board.is_castling(cand_mv)
            is_both_hl = False
            if cand_mv:
                f_name = chess.square_name(cand_mv.from_square)
                t_name = chess.square_name(cand_mv.to_square)
                is_both_hl = {f_name, t_name}.issubset(set(hl_squares))

            # Debounce temporal de confirmación (2 fotogramas estables o 2 casillas resaltadas exactas)
            if self._pending_move == cand_mv:
                self._pending_move_count += 1
            else:
                self._pending_move = cand_mv
                self._pending_chain = rec_res.moves_chain
                self._pending_move_count = 1

            if self._pending_move_count >= 2 or is_both_hl or is_castling:
                if rec_res.moves_chain:
                    for m in rec_res.moves_chain:
                        self.sync_mgr.push_move(m)
                    last_m = self.sync_mgr.board.peek() if self.sync_mgr.board.move_stack else None
                    san_str = self.sync_mgr.board.san(last_m) if last_m else ""
                    piece_name = self.sync_mgr.mental_map.get_piece_name_at(last_m.to_square) if last_m else None
                    piece_label = f" ({tr(piece_name)})" if piece_name else ""
                    self.set_sync_status(tr('● Jugada: {value0}{value1}', value0=san_str, value1=piece_label), "ready")
                elif cand_mv:
                    piece_name = self.sync_mgr.mental_map.get_piece_name_at(cand_mv.from_square)
                    piece_label = f" ({tr(piece_name)})" if piece_name else ""
                    san_str = self.sync_mgr.board.san(cand_mv)
                    self.sync_mgr.push_move(cand_mv)
                    self.set_sync_status(tr('● Jugada: {value0}{value1}', value0=san_str, value1=piece_label), "ready")

                self._prev_squares = current_squares
                self._pending_move = None
                self._pending_chain = None
                self._pending_move_count = 0
                self._desync_frames = 0
                self.btn_rescan_screen.setStyleSheet(Theme.get_button_style("secondary", self._theme))
                self.board_view.set_board(self.sync_mgr.board)
                self.trigger_analysis()
            else:
                self.set_sync_status(tr("⌛ Posición pendiente de confirmar"), "paused")
            return

        if rec_res.status == ReconcileStatus.DESYNC:
            self._pending_move = None
            self._pending_chain = None
            self._pending_move_count = 0
            self._desync_frames += 1
            # Mantiene el estado Desincronizado de forma estable sin disparar auto-escaneo en bucle
            # ni re-analizar Stockfish, garantizando flechas estáticas y cero parpadeo.
            self.set_sync_status(tr("⚠ Desincronizado"), "desync")

    def scan_board_from_screen(self) -> None:
        """
        Escanea visualmente las 64 casillas de la pantalla en tiempo real y reconstruye
        la posición FEN exacta directamente, permitiendo auto-recuperarse de cualquier desincronización.
        """
        if not self.config.region:
            self.set_sync_status(tr("⚠ Selecciona región primero"), "paused")
            return

        frame = ScreenCapture.capture_region(self.config.region)
        if frame is None:
            self.set_sync_status(tr("⚠ Error al capturar pantalla"), "desync")
            return

        fen, confidence = BoardDetector.scan_full_board_fen(
            image=frame,
            orientation=self.board_view._orientation,
            margin_pct=self.config.margin_pct,
            inset_pct=self.config.cell_inset_pct,
            mental_map=self.sync_mgr.mental_map
        )

        try:
            test_board = chess.Board(fen)
            if not test_board.is_valid():
                alt_turn = "b" if test_board.turn == chess.WHITE else "w"
                fen_parts = fen.split()
                if len(fen_parts) == 6:
                    fen_parts[1] = alt_turn
                    candidate_fen = " ".join(fen_parts)
                    cand_board = chess.Board(candidate_fen)
                    if cand_board.is_valid():
                        fen = candidate_fen
                        test_board = cand_board

            if test_board.is_valid() and confidence >= 0.80:
                self.is_manual_paused = False
                self.board_version += 1
                self.sync_mgr.set_fen(fen)
                self.board_view.set_board(self.sync_mgr.board)
                self._prev_frame = frame.copy()
                self._prev_squares = BoardDetector.extract_squares(
                    image=frame,
                    orientation=self.board_view._orientation,
                    margin_pct=self.config.margin_pct,
                    inset_pct=self.config.cell_inset_pct
                )
                self._pending_move = None
                self._pending_chain = None
                self._pending_move_count = 0
                self._desync_frames = 0
                if self.config.auto_scan and not self.scan_timer.isActive():
                    scan_interval = min(self.config.scan_interval_ms, 80) if self.config.scan_interval_ms > 0 else 80
                    self.scan_timer.start(scan_interval)

                self.btn_rescan_screen.setStyleSheet(Theme.get_button_style("secondary", self._theme))
                surv_count = len(self.sync_mgr.mental_map.get_surviving_pieces())
                self.set_sync_status(tr('● EN VIVO · Tablero mental activo ({value0} piezas)', value0=surv_count), "ready")
                self.trigger_analysis()
                return
        except Exception:
            pass

        # Si el escaneo fue dudoso, aun así mantener el sistema vivo y receptivo a nuevos movimientos
        self.is_manual_paused = False
        self._prev_frame = frame.copy()
        self._prev_squares = BoardDetector.extract_squares(
            image=frame,
            orientation=self.board_view._orientation,
            margin_pct=self.config.margin_pct,
            inset_pct=self.config.cell_inset_pct
        )
        self._pending_move = None
        self._pending_chain = None
        self._pending_move_count = 0
        self._desync_frames = 0
        if self.config.auto_scan and not self.scan_timer.isActive():
            scan_interval = min(self.config.scan_interval_ms, 80) if self.config.scan_interval_ms > 0 else 80
            self.scan_timer.start(scan_interval)

        self.set_sync_status(tr("⚠ Escaneo dudoso - Ajusta la posición si es necesario"), "paused")

    def resync_board(self) -> None:
        """Fuerza una re-sincronización dinámica analizando el fotograma actual completo."""
        self.is_manual_paused = False
        self.board_version += 1
        self._pending_move = None
        self._pending_chain = None
        self._pending_move_count = 0
        if self.config.auto_scan and self.config.region:
            scan_interval = min(self.config.scan_interval_ms, 80) if self.config.scan_interval_ms > 0 else 80
            self.scan_timer.start(scan_interval)

        if not self.config.region:
            return
        frame = ScreenCapture.capture_region(self.config.region)
        if frame is None:
            return
        current_squares = BoardDetector.extract_squares(
            image=frame,
            orientation=self.board_view._orientation,
            margin_pct=self.config.margin_pct,
            inset_pct=self.config.cell_inset_pct
        )
        advances = 0
        for _ in range(30):
            hl = PieceClassifier.get_highlighted_squares(current_squares)
            mv = self._find_physically_completed_move(current_squares, hl_squares=hl)
            if not mv:
                mvs = self._catch_up_missed_plies(current_squares, hl_squares=hl)
                if mvs:
                    for m in mvs:
                        self.sync_mgr.push_move(m)
                    advances += len(mvs)
                    continue
            if mv:
                self.sync_mgr.push_move(mv)
                advances += 1
            else:
                break

        if advances == 0:
            # Si no se pudo avanzar incrementalmente, recurrir a auto-recuperación visual completa
            self.scan_board_from_screen()
            return

        self._prev_squares = current_squares
        self.board_view.set_board(self.sync_mgr.board)
        if advances > 0:
            self.set_sync_status(tr('● EN VIVO (Sincronizado +{value0})', value0=advances), "ready")
        else:
            self.set_sync_status(tr("● EN VIVO (Sincronizado)"), "ready")
        self.trigger_analysis()

    def _catch_up_missed_plies(
        self,
        current_squares: Dict[str, np.ndarray],
        hl_squares: Optional[List[str]] = None,
        diff_map: Optional[Dict[str, float]] = None
    ) -> Optional[List[chess.Move]]:
        """
        Reconcilia automáticamente la posición si se perdió 1 semijugada (ply) previa
        debido a lag del navegador, animaciones rápidas o pre-moves.
        Busca si una jugada legal del turno actual (m1) seguida de una respuesta legal (m2)
        explica perfectamente las casillas actualmente resaltadas y la ocupación física.
        """
        hl_set = set(hl_squares) if hl_squares else set()
        if len(hl_set) < 2 and (not diff_map or max(diff_map.values(), default=0.0) < 0.05):
            return None

        candidates: List[Tuple[float, List[chess.Move]]] = []
        for m1 in list(self.sync_mgr.board.legal_moves):
            f1_name = chess.square_name(m1.from_square)
            t1_name = chess.square_name(m1.to_square)
            img_f1 = current_squares.get(f1_name)
            img_t1 = current_squares.get(t1_name)

            self.sync_mgr.board.push(m1)
            try:
                for m2 in self.sync_mgr.board.legal_moves:
                    f2_name = chess.square_name(m2.from_square)
                    t2_name = chess.square_name(m2.to_square)

                    is_m2_hl = {f2_name, t2_name}.issubset(hl_set) if hl_set else False
                    img_f2 = current_squares.get(f2_name)
                    img_t2 = current_squares.get(t2_name)

                    if img_f2 is None or img_t2 is None:
                        continue

                    # m2 físicamente: origen vacío y destino ocupado
                    if PieceClassifier.is_square_empty(img_f2) and PieceClassifier.is_square_occupied(img_t2):
                        # m1 físicamente: origen de m1 debe estar vacío (salvo que m2 haya entrado a él)
                        f1_ok = (f1_name == t2_name) or (img_f1 is not None and PieceClassifier.is_square_empty(img_f1))
                        # destino de m1 debe estar ocupado (salvo que m2 sea la pieza que salió de él)
                        t1_ok = (t1_name == f2_name) or (img_t1 is not None and PieceClassifier.is_square_occupied(img_t1))

                        if f1_ok and t1_ok:
                            score = 10.0
                            if is_m2_hl:
                                score += 20.0
                            if PieceClassifier.get_piece_color(img_t2) == self.sync_mgr.board.turn:
                                score += 10.0
                            if diff_map:
                                score += diff_map.get(f2_name, 0.0) + diff_map.get(t2_name, 0.0)
                            candidates.append((score, [m1, m2]))
            finally:
                self.sync_mgr.board.pop()

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]

        return None

    def _reconcile_highlighted_move(
        self,
        from_sq: str,
        to_sq: str,
        current_squares: Dict[str, np.ndarray],
        diff_map: Optional[Dict[str, float]] = None
    ) -> Optional[List[chess.Move]]:
        """
        Reconcilia automáticamente la posición cuando la jugada física resaltada (from_sq -> to_sq)
        no es legal directamente en el turno actual (ej. el rival jugó rápido y se perdió 1 ply por lag).
        Busca jugadas intermedias legales y físicamente consistentes con el tablero real.
        """
        raw_mv = chess.Move.from_uci(f"{from_sq}{to_sq}")
        cand_moves = [raw_mv]
        if (from_sq[1] == '7' and to_sq[1] == '8') or (from_sq[1] == '2' and to_sq[1] == '1'):
            cand_moves.insert(0, chess.Move(raw_mv.from_square, raw_mv.to_square, promotion=chess.QUEEN))

        # 1. Búsqueda de 1 semijugada previa del turno actual (ej. rival movió m1, habilitando from_sq -> to_sq)
        candidates_1ply: List[Tuple[float, List[chess.Move]]] = []
        for m1 in list(self.sync_mgr.board.legal_moves):
            f1_name = chess.square_name(m1.from_square)
            t1_name = chess.square_name(m1.to_square)
            img_f1 = current_squares.get(f1_name)
            img_t1 = current_squares.get(t1_name)

            self.sync_mgr.board.push(m1)
            try:
                for target_mv in cand_moves:
                    if target_mv in self.sync_mgr.board.legal_moves:
                        # Verificación física:
                        # Origen de m1 debe estar vacío ahora (salvo que target_mv haya entrado en él)
                        f1_empty = (f1_name == to_sq) or (img_f1 is not None and PieceClassifier.is_square_empty(img_f1))
                        # Destino de m1 debe estar ocupado ahora (salvo que target_mv saliera de él o lo capturara)
                        t1_occ = (t1_name == from_sq) or (t1_name == to_sq) or (img_t1 is not None and PieceClassifier.is_square_occupied(img_t1))

                        if f1_empty and t1_occ:
                            score = 20.0
                            if diff_map:
                                score += (diff_map.get(f1_name, 0.0) + diff_map.get(t1_name, 0.0))
                            if t1_name != from_sq and t1_name != to_sq and img_t1 is not None:
                                col_t1 = PieceClassifier.get_piece_color(img_t1)
                                if col_t1 == (not self.sync_mgr.board.turn):
                                    score += 10.0
                            candidates_1ply.append((score, [m1, target_mv]))
            finally:
                self.sync_mgr.board.pop()

        if candidates_1ply:
            candidates_1ply.sort(key=lambda x: x[0], reverse=True)
            return candidates_1ply[0][1]

        # 2. Búsqueda de 2 semijugadas previas (m1 -> m2 -> target_mv)
        candidates_2ply: List[Tuple[float, List[chess.Move]]] = []
        for m1 in list(self.sync_mgr.board.legal_moves):
            f1_name = chess.square_name(m1.from_square)
            t1_name = chess.square_name(m1.to_square)
            img_f1 = current_squares.get(f1_name)

            self.sync_mgr.board.push(m1)
            try:
                for m2 in list(self.sync_mgr.board.legal_moves):
                    f2_name = chess.square_name(m2.from_square)
                    t2_name = chess.square_name(m2.to_square)
                    img_f2 = current_squares.get(f2_name)
                    img_t2 = current_squares.get(t2_name)

                    self.sync_mgr.board.push(m2)
                    try:
                        for target_mv in cand_moves:
                            if target_mv in self.sync_mgr.board.legal_moves:
                                f2_empty = (f2_name == to_sq) or (img_f2 is not None and PieceClassifier.is_square_empty(img_f2))
                                t2_occ = (t2_name == from_sq) or (t2_name == to_sq) or (img_t2 is not None and PieceClassifier.is_square_occupied(img_t2))
                                if f2_empty and t2_occ:
                                    score = 10.0
                                    candidates_2ply.append((score, [m1, m2, target_mv]))
                    finally:
                        self.sync_mgr.board.pop()
            finally:
                self.sync_mgr.board.pop()

        if candidates_2ply:
            candidates_2ply.sort(key=lambda x: x[0], reverse=True)
            return candidates_2ply[0][1]

        return None

    def _reconstruct_fen_from_squares(
        self,
        current_squares: Dict[str, np.ndarray],
        turn: Optional[chess.Color] = None
    ) -> Optional[str]:
        """
        Reconstruye la posición FEN física completa examinando las 64 casillas del tablero.
        Valida integridad de reyes y legalidad de reglas oficiales.
        """
        files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        ranks = ['8', '7', '6', '5', '4', '3', '2', '1']

        fen_rows = []
        white_kings = 0
        black_kings = 0

        for r in ranks:
            empty_cnt = 0
            row_str = ''
            for f in files:
                sq = f + r
                sq_img = current_squares.get(sq)
                if sq_img is None or not PieceClassifier.is_square_occupied(sq_img):
                    empty_cnt += 1
                else:
                    col = PieceClassifier.get_piece_color(sq_img)
                    if col is None:
                        empty_cnt += 1
                        continue
                    pt = PieceClassifier.classify_piece_type(sq_img, col)
                    if pt == chess.KING:
                        if col == chess.WHITE:
                            white_kings += 1
                        else:
                            black_kings += 1

                    if empty_cnt > 0:
                        row_str += str(empty_cnt)
                        empty_cnt = 0
                    sym = chess.piece_symbol(pt).upper() if col == chess.WHITE else chess.piece_symbol(pt).lower()
                    row_str += sym
            if empty_cnt > 0:
                row_str += str(empty_cnt)
            fen_rows.append(row_str)

        # Si no se detectó el rey negro pero hay casillas reales típicas en fila 8
        if black_kings == 0:
            for king_cand in ['g8', 'e8', 'c8', 'f8', 'h8']:
                sq_img = current_squares.get(king_cand)
                if sq_img is not None and PieceClassifier.is_square_occupied(sq_img):
                    if PieceClassifier.get_piece_color(sq_img) == chess.BLACK:
                        black_kings = 1
                        break

        if white_kings != 1 or black_kings != 1:
            return None

        # Turno: si hay 2 casillas resaltadas, el bando que está en to_sq acaba de mover, luego turno es el contrario
        turn_char = 'w' if (turn == chess.WHITE or (turn is None and self.sync_mgr.board.turn == chess.WHITE)) else 'b'
        hl = PieceClassifier.get_highlighted_squares(current_squares)
        if len(hl) == 2:
            occ_sqs = [s for s in hl if PieceClassifier.is_square_occupied(current_squares.get(s))]
            if len(occ_sqs) == 1:
                moved_col = PieceClassifier.get_piece_color(current_squares.get(occ_sqs[0]))
                if moved_col == chess.WHITE:
                    turn_char = 'b'
                elif moved_col == chess.BLACK:
                    turn_char = 'w'

        fen_str = f"{'/'.join(fen_rows)} {turn_char} - - 0 1"
        try:
            test_board = chess.Board(fen_str)
            if test_board.is_valid():
                return fen_str
        except Exception:
            pass

        return None

    def _auto_sync_initial_moves(self, current_squares: Dict[str, np.ndarray]) -> None:
        """
        Avanza automáticamente el tablero si el usuario recorta cuando ya se han jugado
        movimientos, resolviendo dinámicamente cualquier apertura legal (Pirc, Barnes, etc.).
        """
        if PieceClassifier.are_center_ranks_empty(current_squares):
            return

        for _ in range(30):
            found_move = self._find_physically_completed_move(current_squares)
            if found_move:
                self.sync_mgr.push_move(found_move)
            else:
                break

    def _find_physically_completed_move(
        self,
        current_squares: Dict[str, np.ndarray],
        hl_squares: Optional[List[str]] = None,
        diff_map: Optional[Dict[str, float]] = None
    ) -> Optional[chess.Move]:
        """
        Evalúa si alguna de las jugadas legales actuales se ha materializado físicamente en el tablero:
        - Enroques: rey y torre movidos a sus casillas finales correspondientes.
        - En passant: peón en casilla destino y peón capturado desaparecido.
        - Movimiento normal / captura: casilla de origen vacía y casilla de destino ocupada con pieza del color del turno.
        Desambigua candidatos comprobando que from_sq quedó vacío y utilizando resaltados, diff_map y tipo de pieza.
        """
        turn = self.sync_mgr.board.turn
        hl_set = set(hl_squares) if hl_squares else set()

        # 1. Enroques primero (movimientos compuestos)
        for legal_mv in self.sync_mgr.board.legal_moves:
            if self.sync_mgr.board.is_castling(legal_mv):
                from_sq = chess.square_name(legal_mv.from_square)
                to_sq = chess.square_name(legal_mv.to_square)
                r_from, r_to = self.sync_mgr._get_castling_rook_squares(legal_mv)
                img_from = current_squares.get(from_sq)
                img_to = current_squares.get(to_sq)
                img_rfrom = current_squares.get(r_from)
                img_rto = current_squares.get(r_to)
                if img_from is not None and img_to is not None and img_rfrom is not None and img_rto is not None:
                    if (PieceClassifier.is_square_empty(img_from) and
                        PieceClassifier.is_square_empty(img_rfrom) and
                        PieceClassifier.is_square_occupied(img_to) and
                        PieceClassifier.is_square_occupied(img_rto)):
                        if (PieceClassifier.get_piece_color(img_to) == turn and
                            PieceClassifier.get_piece_color(img_rto) == turn):
                            return legal_mv

        # 2. En passant
        for legal_mv in self.sync_mgr.board.legal_moves:
            if self.sync_mgr.board.is_en_passant(legal_mv):
                from_sq = chess.square_name(legal_mv.from_square)
                to_sq = chess.square_name(legal_mv.to_square)
                ep_sq = chess.square_name(chess.square(
                    chess.square_file(legal_mv.to_square),
                    chess.square_rank(legal_mv.from_square)
                ))
                img_from = current_squares.get(from_sq)
                img_to = current_squares.get(to_sq)
                img_ep = current_squares.get(ep_sq)
                if img_from is not None and img_to is not None and img_ep is not None:
                    if (PieceClassifier.is_square_empty(img_from) and
                        PieceClassifier.is_square_empty(img_ep) and
                        PieceClassifier.is_square_occupied(img_to)):
                        if PieceClassifier.get_piece_color(img_to) == turn:
                            return legal_mv

        # 3. Movimientos normales y capturas
        candidates: List[Tuple[float, chess.Move]] = []
        for legal_mv in self.sync_mgr.board.legal_moves:
            if self.sync_mgr.board.is_castling(legal_mv) or self.sync_mgr.board.is_en_passant(legal_mv):
                continue
            from_sq = chess.square_name(legal_mv.from_square)
            to_sq = chess.square_name(legal_mv.to_square)
            img_from = current_squares.get(from_sq)
            img_to = current_squares.get(to_sq)
            if img_from is not None and img_to is not None:
                # Comprobación de integridad física: origen vacío y destino ocupado
                if PieceClassifier.is_square_empty(img_from) and PieceClassifier.is_square_occupied(img_to):
                    col = PieceClassifier.get_piece_color(img_to)
                    is_in_hl = (from_sq in hl_set and to_sq in hl_set)
                    if col == turn or is_in_hl:
                        score = 0.0
                        if col == turn:
                            score += 10.0
                        if diff_map:
                            score += diff_map.get(from_sq, 0.0) + diff_map.get(to_sq, 0.0)

                        # Puntuación por resaltados amarillos/verdes de Chess.com
                        if from_sq in hl_set or PieceClassifier.is_square_highlighted(img_from):
                            score += 10.0
                        if to_sq in hl_set or PieceClassifier.is_square_highlighted(img_to):
                            score += 10.0

                        # Bonificación por correspondencia del tipo de pieza
                        moving_pt = self.sync_mgr.board.piece_type_at(legal_mv.from_square)
                        if moving_pt and PieceClassifier.classify_piece_type(img_to, turn) == moving_pt:
                            score += 3.0

                        if legal_mv.promotion == chess.QUEEN:
                            score += 1.0

                        candidates.append((score, legal_mv))

        if not candidates:
            return None

        # Si hay 2 casillas resaltadas, priorizar estrictamente las jugadas entre esas 2 casillas
        if len(hl_set) >= 2:
            hl_cand = [c for c in candidates if {chess.square_name(c[1].from_square), chess.square_name(c[1].to_square)}.issubset(hl_set)]
            if hl_cand:
                candidates = hl_cand

        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def _detect_legal_move(
        self,
        changed: List[str],
        current_squares: Dict[str, np.ndarray],
        diff_map: Optional[Dict[str, float]] = None,
        hl_squares: Optional[List[str]] = None
    ) -> Optional[chess.Move]:
        """
        Verifica si el conjunto de casillas cambiadas y/o resaltadas cumple con las leyes de ajedrez
        y la verificación física de ocupación (origen vacío y destino ocupado por pieza del turno actual).
        Resuelve desambiguaciones (como Nf6 vs Qf6 o capturas) con máxima precisión.
        """
        changed_set = set(sq.lower() for sq in changed)
        hl_set = set(hl_squares) if hl_squares else set()
        turn = self.sync_mgr.board.turn

        if len(changed_set) > 8 and len(hl_set) < 2:
            return None

        # 1. Enroques (4 casillas)
        if len(changed_set) >= 3 or len(hl_set) >= 2:
            for legal_mv in self.sync_mgr.board.legal_moves:
                if self.sync_mgr.board.is_castling(legal_mv):
                    from_sq = chess.square_name(legal_mv.from_square)
                    to_sq = chess.square_name(legal_mv.to_square)
                    r_from, r_to = self.sync_mgr._get_castling_rook_squares(legal_mv)
                    castling_set = {from_sq, to_sq, r_from, r_to}
                    if castling_set.issubset(changed_set) or len(changed_set.intersection(castling_set)) >= 3 or castling_set.issubset(hl_set):
                        img_from = current_squares.get(from_sq)
                        img_rfrom = current_squares.get(r_from)
                        img_to = current_squares.get(to_sq)
                        img_rto = current_squares.get(r_to)
                        if (PieceClassifier.is_square_empty(img_from) and
                            PieceClassifier.is_square_empty(img_rfrom) and
                            PieceClassifier.is_square_occupied(img_to) and
                            PieceClassifier.is_square_occupied(img_rto)):
                            if (PieceClassifier.get_piece_color(img_to) == turn and
                                PieceClassifier.get_piece_color(img_rto) == turn):
                                return legal_mv

        # 2. En passant (3 casillas)
        if len(changed_set) >= 3 or len(hl_set) >= 2:
            for legal_mv in self.sync_mgr.board.legal_moves:
                if self.sync_mgr.board.is_en_passant(legal_mv):
                    from_sq = chess.square_name(legal_mv.from_square)
                    to_sq = chess.square_name(legal_mv.to_square)
                    ep_sq = chess.square_name(chess.square(
                        chess.square_file(legal_mv.to_square),
                        chess.square_rank(legal_mv.from_square)
                    ))
                    ep_set = {from_sq, to_sq, ep_sq}
                    if ep_set.issubset(changed_set) or len(changed_set.intersection(ep_set)) >= 2 or {from_sq, to_sq}.issubset(hl_set):
                        img_from = current_squares.get(from_sq)
                        img_ep = current_squares.get(ep_sq)
                        img_to = current_squares.get(to_sq)
                        if (PieceClassifier.is_square_empty(img_from) and
                            PieceClassifier.is_square_empty(img_ep) and
                            PieceClassifier.is_square_occupied(img_to)):
                            if PieceClassifier.get_piece_color(img_to) == turn:
                                return legal_mv

        # 3. Movimiento normal o captura
        candidate_moves: List[Tuple[float, chess.Move]] = []
        for legal_mv in self.sync_mgr.board.legal_moves:
            from_sq = chess.square_name(legal_mv.from_square)
            to_sq = chess.square_name(legal_mv.to_square)

            # Debe haber coincidencia en casillas cambiadas o resaltadas
            is_in_hl = {from_sq, to_sq}.issubset(hl_set) if hl_set else False
            is_in_changed = {from_sq, to_sq}.issubset(changed_set)
            # is_partial solo se evalúa si NO hay 2 casillas resaltadas
            is_partial = (len(hl_set) < 2) and (from_sq in changed_set or to_sq in changed_set) and (len(changed_set) <= 4)

            if is_in_hl or is_in_changed or is_partial:
                from_img = current_squares.get(from_sq)
                to_img = current_squares.get(to_sq)

                # Casilla origen DEBE estar físicamente vacía ahora
                if not PieceClassifier.is_square_empty(from_img):
                    continue

                # Casilla destino DEBE estar físicamente ocupada ahora
                if not PieceClassifier.is_square_occupied(to_img):
                    continue

                # Color de la pieza en destino debe corresponder al turno (o estar explícitamente resaltado en origen y destino)
                dest_col = PieceClassifier.get_piece_color(to_img)
                if dest_col == turn:
                    score = 10.0
                elif is_in_hl:
                    score = 4.0
                else:
                    continue

                if diff_map:
                    score += (diff_map.get(from_sq, 0.0) + diff_map.get(to_sq, 0.0))

                # Bonificación fuerte por casillas resaltadas en Chess.com / Lichess
                if from_sq in hl_set or PieceClassifier.is_square_highlighted(from_img):
                    score += 10.0
                if to_sq in hl_set or PieceClassifier.is_square_highlighted(to_img):
                    score += 10.0

                # Bonificación de tipo de pieza
                moving_pt = self.sync_mgr.board.piece_type_at(legal_mv.from_square)
                if moving_pt and PieceClassifier.classify_piece_type(to_img, turn) == moving_pt:
                    score += 3.0

                if legal_mv.promotion == chess.QUEEN:
                    score += 1.0

                candidate_moves.append((score, legal_mv))

        if candidate_moves:
            candidate_moves.sort(key=lambda x: x[0], reverse=True)
            return candidate_moves[0][1]

        return None

    def trigger_analysis(self) -> None:
        """Solicita el análisis asíncrono a Stockfish para la posición actual."""
        if not self.stockfish_mgr:
            return
        depth, time_limit = self.config.get_effort_depth_and_time()
        turn = self.sync_mgr.board.turn
        current_acc = self.accuracy_tracker.white_accuracy if turn == chess.WHITE else self.accuracy_tracker.black_accuracy

        self.stockfish_mgr.request_analysis_async(
            board_id=self.config.id,
            board=self.sync_mgr.board,
            depth=depth,
            time_limit=time_limit,
            multipv=4,
            style=self.config.style,
            elo=self.config.elo,
            target_accuracy=getattr(self.config, "target_accuracy", 80),
            current_accuracy=current_acc,
            enable_adaptive=getattr(self.config, "enable_target_accuracy", True),
            adaptive_tolerance=getattr(self.config, "target_accuracy_tolerance", 5),
            enable_subtle_loss=getattr(self.config, "enable_subtle_loss", False),
            subtle_loss_move=getattr(self.config, "subtle_loss_move", 20),
            subtle_loss_severity=getattr(self.config, "subtle_loss_severity", "moderate")
        )

    def _on_analysis_received(self, board_id: str, analysis: PositionAnalysis) -> None:
        if board_id != self.config.id:
            return

        self._current_analysis = analysis

        # Paridad 100% exacta: ambas vistas reciben siempre las mismas jugadas candidatas
        self.board_view.set_candidate_moves(analysis.top_moves)
        if self.overlay_window.is_overlay_visible():
            self.overlay_window.set_candidate_moves(analysis.top_moves)

        # Ajustar jugada pendiente con evaluación del motor y refrescar precisión
        self.accuracy_tracker.record_analysis(analysis)
        self.eval_panel.update_accuracy(self.accuracy_tracker.get_summary())
        self.eval_panel.update_analysis(analysis)


class MainWindow(QMainWindow):
    """
    Ventana principal de la suite Chess Vision Assistant.
    """

    def __init__(self, config: Optional[AppConfig] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.config = config or AppConfig.load()
        set_language(self.config.language)
        self.setWindowTitle(tr("Chess Vision Assistant - Análisis y Visión en Tiempo Real"))
        self.resize(1200, 780)
        self.setMinimumSize(850, 550)

        # Gestor de Stockfish primario (compatibilidad y statusbar)
        self.stockfish_mgr = StockfishManager(
            engine_path=self.config.stockfish_path,
            threads=self.config.threads_per_board,
            hash_mb=self.config.hash_per_board_mb,
            parent=self
        )

        # Diccionario de procesos Stockfish dedicados por tablero activo: board_id -> StockfishManager
        self.stockfish_engines: Dict[str, StockfishManager] = {
            self.config.boards[0].id: self.stockfish_mgr
        }

        self._region_selector: Optional[RegionSelectorWindow] = None
        self._target_board_id_for_region: Optional[str] = None
        self._board_widgets: Dict[str, SingleBoardWidget] = {}

        self._build_toolbar()
        self._build_ui_grid()
        self._build_statusbar()
        self._apply_theme(getattr(self.config, "theme", "dark") or "dark")

    def _toggle_theme(self) -> None:
        """Conmuta dinámicamente entre Modo Oscuro y Modo Claro guardando la preferencia."""
        new_theme = "light" if self.config.theme == "dark" else "dark"
        self.config.theme = new_theme
        self.config.save()
        self._apply_theme(new_theme)

    def _apply_theme(self, theme_name: str) -> None:
        """Aplica la hoja de estilos global y propaga el tema a todos los subwidgets."""
        self.config.theme = theme_name
        self.setStyleSheet(Theme.get_application_stylesheet(theme_name))

        if hasattr(self, "btn_theme_toggle"):
            if theme_name == "dark":
                self.btn_theme_toggle.setText(tr("☀️ Modo Claro"))
                self.btn_theme_toggle.setToolTip(tr("Cambiar a Modo Claro"))
            else:
                self.btn_theme_toggle.setText(tr("🌙 Modo Oscuro"))
                self.btn_theme_toggle.setToolTip(tr("Cambiar a Modo Oscuro"))
            self.btn_theme_toggle.setStyleSheet(Theme.get_button_style("theme_toggle", theme_name))

        if hasattr(self, "btn_setup"):
            self.btn_setup.setStyleSheet(Theme.get_button_style("primary", theme_name))
        if hasattr(self, "btn_snip"):
            self.btn_snip.setStyleSheet(Theme.get_button_style("secondary", theme_name))
        if hasattr(self, "btn_global_cfg"):
            self.btn_global_cfg.setStyleSheet(Theme.get_button_style("config", theme_name))
        if hasattr(self, "btn_sim"):
            self.btn_sim.setStyleSheet(Theme.get_button_style("neutral", theme_name))
        if hasattr(self, "btn_refresh"):
            self.btn_refresh.setStyleSheet(Theme.get_button_style("neutral", theme_name))

        for bw in self._board_widgets.values():
            bw.set_theme(theme_name)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar(tr("Barra de Herramientas"), self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Selector de número de tableros
        lbl_boards = QLabel(tr("  Tableros Activos: "))
        lbl_boards.setStyleSheet("font-weight: bold; font-size: 12px;")
        toolbar.addWidget(lbl_boards)

        self.cmb_board_count = QComboBox()
        self.cmb_board_count.addItems([tr("1 Tablero"), tr("2 Tableros"), tr("3 Tableros"), tr("4 Tableros")])
        self.cmb_board_count.setCurrentIndex(self.config.active_board_count - 1)
        self.cmb_board_count.currentIndexChanged.connect(self._on_board_count_changed)
        self.cmb_board_count.setCursor(Qt.CursorShape.PointingHandCursor)
        toolbar.addWidget(self.cmb_board_count)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel(tr("Idioma")))
        self.cmb_language = QComboBox()
        self.cmb_language.setObjectName("languageSelector")
        for code, name in LANGUAGES.items():
            self.cmb_language.addItem(name, code)
        self.cmb_language.setCurrentIndex(self.cmb_language.findData(self.config.language))
        self.cmb_language.setToolTip(tr("Idioma de la interfaz"))
        self.cmb_language.currentIndexChanged.connect(self._on_language_changed)
        toolbar.addWidget(self.cmb_language)

        toolbar.addSeparator()

        # Botón Asistente de Inicio / Modos
        self.btn_setup = QPushButton(tr("🎯 Asistente de Inicio / Modos"))
        self.btn_setup.setToolTip(tr("Abrir asistente inicial para configurar tableros, modos y regiones"))
        self.btn_setup.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_setup.clicked.connect(self._open_initial_setup_dialog)
        toolbar.addWidget(self.btn_setup)

        toolbar.addSeparator()

        # Botón Snipping Tool
        self.btn_snip = QPushButton(tr("✂ Seleccionar Pantalla"))
        self.btn_snip.setToolTip(tr("Abrir selector estilo Snipping Tool para capturar tablero en pantalla"))
        self.btn_snip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_snip.clicked.connect(self._start_screen_selection_default)
        toolbar.addWidget(self.btn_snip)

        toolbar.addSeparator()

        # Botón Configuración de Elo y Ajustes en Barra Superior
        self.btn_global_cfg = QPushButton(tr("⚙ Configurar Elo y Ajustes"))
        self.btn_global_cfg.setToolTip(tr("Abrir panel de configuración de nivel de Elo (700-2800), Estilo y Motor"))
        self.btn_global_cfg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_global_cfg.clicked.connect(self._open_active_board_config)
        toolbar.addWidget(self.btn_global_cfg)

        toolbar.addSeparator()

        # Botón Simulador de Partidas
        self.btn_sim = QPushButton(tr("♟ Simulador de Partidas"))
        self.btn_sim.setToolTip(tr("Abrir simulador con tácticas célebres para probar sin navegador"))
        self.btn_sim.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_sim.clicked.connect(self._open_simulation_dialog)
        toolbar.addWidget(self.btn_sim)

        toolbar.addSeparator()

        # Botón Forzar Re-análisis
        self.btn_refresh = QPushButton(tr("⟳ Analizar Todo"))
        self.btn_refresh.setToolTip(tr("Forzar re-análisis en todos los tableros activos"))
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self._reanalyze_all)
        toolbar.addWidget(self.btn_refresh)

        # Espaciador expansible para alinear el botón de tema a la derecha
        spacer = QWidget(self)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        current_theme = getattr(self.config, "theme", "dark") or "dark"
        self.btn_theme_toggle = QPushButton(tr("☀️ Modo Claro") if current_theme == "dark" else tr("🌙 Modo Oscuro"))
        self.btn_theme_toggle.setToolTip(tr("Conmutar entre Modo Oscuro y Modo Claro"))
        self.btn_theme_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_theme_toggle.clicked.connect(self._toggle_theme)
        toolbar.addWidget(self.btn_theme_toggle)

    def _on_language_changed(self, index: int) -> None:
        language = self.cmb_language.itemData(index)
        if language not in LANGUAGES or language == self.config.language:
            return
        previous = self.config.language
        self.config.language = language
        if not self.config.save():
            self.config.language = previous
            self.cmb_language.blockSignals(True)
            self.cmb_language.setCurrentIndex(self.cmb_language.findData(previous))
            self.cmb_language.blockSignals(False)
            QMessageBox.warning(self, tr("Idioma"), tr("No se pudo guardar el idioma. Comprueba los permisos de la carpeta de configuración."))
            return
        QMessageBox.information(
            self, tr("Idioma guardado"),
            tr("El idioma se aplicará al reiniciar la aplicación. El seguimiento actual continúa sin cambios.")
        )

    def _build_ui_grid(self) -> None:
        """Construye la cuadrícula adaptable de tableros (1x1, 1x2, 2x2)."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        self.grid_layout = QGridLayout(central_widget)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(8)

        # Crear widgets para hasta 4 tableros
        self._board_widgets.clear()
        for i in range(4):
            cfg = self.config.boards[i]
            bw = SingleBoardWidget(cfg, self.stockfish_mgr, self)
            bw.region_request.connect(self._start_screen_selection_for_board)
            self._board_widgets[cfg.id] = bw

        self._update_grid_layout()

    def _update_grid_layout(self) -> None:
        """Reubica los widgets según el número de tableros seleccionados y gestiona instancias de Stockfish por tablero."""
        for bw in self._board_widgets.values():
            bw.hide()

        for i in reversed(range(self.grid_layout.count())):
            self.grid_layout.takeAt(i)

        count = self.config.active_board_count
        active_ids = [self.config.boards[i].id for i in range(count)]
        all_ids = [b.id for b in self.config.boards]

        total_cpus = os.cpu_count() or 4
        threads_per_engine = max(1, min(self.config.threads_per_board, max(1, total_cpus // count)))
        hash_per_engine = max(16, self.config.hash_per_board_mb // count)

        # 1. Gestionar instancia dedicada de Stockfish por tablero activo
        for idx, b_id in enumerate(active_ids):
            if idx == 0:
                # Tablero principal usa self.stockfish_mgr
                self.stockfish_mgr.set_threads_and_hash(threads_per_engine, hash_per_engine)
                self.stockfish_engines[b_id] = self.stockfish_mgr
                if b_id in self._board_widgets:
                    self._board_widgets[b_id].set_stockfish_manager(self.stockfish_mgr)
            else:
                if b_id not in self.stockfish_engines:
                    engine = StockfishManager(
                        engine_path=self.config.stockfish_path,
                        threads=threads_per_engine,
                        hash_mb=hash_per_engine,
                        parent=self
                    )
                    self.stockfish_engines[b_id] = engine
                    if b_id in self._board_widgets:
                        self._board_widgets[b_id].set_stockfish_manager(engine)
                else:
                    self.stockfish_engines[b_id].set_threads_and_hash(threads_per_engine, hash_per_engine)

        # 2. Detener y liberar instancias de tableros inactivos
        for b_id in all_ids:
            if b_id not in active_ids and b_id in self.stockfish_engines:
                if b_id != self.config.boards[0].id:
                    engine = self.stockfish_engines.pop(b_id)
                    try:
                        engine.quit()
                    except Exception:
                        pass

        # 3. Ocultar y limpiar overlays de tableros inactivos
        for b_id in all_ids:
            if b_id not in active_ids and b_id in self._board_widgets:
                self._board_widgets[b_id].overlay_window.hide()
                self._board_widgets[b_id].overlay_window.clear_arrows()

        if count == 1:
            # 1 Tablero centrado grande
            bw = self._board_widgets[active_ids[0]]
            self.grid_layout.addWidget(bw, 0, 0)
            bw.show()
        elif count == 2:
            # 2 Tableros (1 fila x 2 columnas)
            for col, b_id in enumerate(active_ids):
                bw = self._board_widgets[b_id]
                self.grid_layout.addWidget(bw, 0, col)
                bw.show()
        elif count in (3, 4):
            # 3 o 4 Tableros (cuadrícula 2x2)
            coords = [(0, 0), (0, 1), (1, 0), (1, 1)]
            for idx, b_id in enumerate(active_ids):
                row, col = coords[idx]
                bw = self._board_widgets[b_id]
                self.grid_layout.addWidget(bw, row, col)
                bw.show()

    def _on_board_count_changed(self, index: int) -> None:
        new_count = index + 1
        self.config.active_board_count = new_count
        self.config.save()
        self._update_grid_layout()

    def _build_statusbar(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)
        self.lbl_engine_info = QLabel(tr("Inicializando motor Stockfish..."))
        status.addWidget(self.lbl_engine_info)

        self.stockfish_mgr.engine_status_changed.connect(self._on_engine_status_changed)

    def _on_engine_status_changed(self, is_ready: bool, msg: str) -> None:
        color = "#48bb78" if is_ready else "#f56565"
        self.lbl_engine_info.setText(tr('Motor: {value0}', value0=msg))
        self.lbl_engine_info.setStyleSheet(f"color: {color}; font-weight: bold; padding-left: 8px;")

    def _start_screen_selection_default(self) -> None:
        """Inicia el selector de pantalla para el tablero principal."""
        primary_id = self.config.boards[0].id
        self._start_screen_selection_for_board(primary_id)

    def _start_screen_selection_for_board(self, board_id: str) -> None:
        """Abre la ventana fullscreen Snipping Tool para capturar el tablero."""
        self._target_board_id_for_region = board_id

        if self._region_selector is None:
            self._region_selector = RegionSelectorWindow()
            self._region_selector.region_selected.connect(self._on_region_selected)

        self._region_selector.start_selection()

    def _on_region_selected(self, x: int, y: int, w: int, h: int) -> None:
        b_id = self._target_board_id_for_region or self.config.boards[0].id
        bw = self._board_widgets.get(b_id)
        if bw:
            bw.set_region((x, y, w, h))
            self.config.save()
            self.statusBar().showMessage(tr('Región asignada a {value0}: ({value1}, {value2}, {value3}x{value4})', value0=board_name(bw.config.name), value1=x, value2=y, value3=w, value4=h), 5000)

    def _open_initial_setup_dialog(self) -> None:
        """Abre el asistente de configuración inicial para gestionar tableros y modos."""
        dlg = InitialSetupDialog(self.config, self, theme=self.config.theme)
        dlg.region_requested.connect(self._start_screen_selection_for_board)
        if dlg.exec():
            self.cmb_board_count.blockSignals(True)
            self.cmb_board_count.setCurrentIndex(self.config.active_board_count - 1)
            self.cmb_board_count.blockSignals(False)
            self._update_grid_layout()
            for cfg in self.config.boards:
                bw = self._board_widgets.get(cfg.id)
                if bw:
                    if cfg.region:
                        bw.set_region(cfg.region)
                    bw.set_display_mode(getattr(cfg, "display_mode", "independent"))

    def _open_simulation_dialog(self) -> None:
        dlg = SimulationDialog(self, theme=self.config.theme)
        dlg.position_injected.connect(self._on_sim_position_injected)
        dlg.exec()

    def _open_active_board_config(self) -> None:
        """Abre el diálogo de configuración de Elo para el tablero principal activo."""
        primary_id = self.config.boards[0].id
        bw = self._board_widgets.get(primary_id)
        if bw:
            bw._open_config_dialog()

    def _on_sim_position_injected(self, fen: str) -> None:
        primary_id = self.config.boards[0].id
        bw = self._board_widgets.get(primary_id)
        if bw:
            bw.set_custom_fen(fen)
            self.statusBar().showMessage(tr('Posición FEN inyectada en {value0}', value0=board_name(bw.config.name)), 4000)

    def _reanalyze_all(self) -> None:
        for bw in self._board_widgets.values():
            if bw.isVisible():
                bw.trigger_analysis()

    def closeEvent(self, event) -> None:
        """Cierra de forma segura todos los motores, ventanas de overlay y guarda la configuración."""
        self.config.save()
        for bw in self._board_widgets.values():
            try:
                bw.overlay_window.clear_arrows()
                bw.overlay_window.close()
            except Exception:
                pass
        for b_id, mgr in list(self.stockfish_engines.items()):
            try:
                mgr.quit()
            except Exception:
                pass
        self.stockfish_engines.clear()
        if hasattr(self, "stockfish_mgr") and self.stockfish_mgr:
            try:
                self.stockfish_mgr.quit()
            except Exception:
                pass
        event.accept()
