"""
Diálogo y módulo de simulación de partidas de ajedrez en vivo.
Permite reproducir posiciones célebres y tácticas sin necesidad de navegador externo.
"""

from __future__ import annotations
from chess_vision.i18n import tr
from typing import Optional, List, Dict
import chess
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QTextEdit, QWidget, QGroupBox, QSplitter
)
from chess_vision.ui.board_view import BoardView
from chess_vision.ui.theme import Theme

PRESET_POSITIONS: Dict[str, str] = {
    "Posición Inicial Estándar": chess.STARTING_FEN,
    "Mate de la Ópera (Paul Morphy)": "4kb1r/p2rqppp/5n2/1B2p1B1/4P3/1Q6/PPP2PPP/2KR4 w k - 0 1",
    "Inmortal de Kasparov (vs Topalov)": "b1r1r1k1/1q1n1p1p/p2bp1p1/1p6/3P1P2/P1NQ1NP1/1P5P/1B1RR1K1 w - - 0 24",
    "Sacrificio Clásico de Alfil en h7": "r1bq1rk1/ppp2ppp/2n1pn2/3p4/2PP4/2NBPN2/PP3PPP/R1BQK2R w KQ - 0 8",
    "Táctica de Coronación en Final": "8/4P3/8/2k5/8/8/5K2/8 w - - 0 1",
    "Defensa Siciliana (Variante Najdorf)": "rnbqkb1r/1p2pppp/p2p1n2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
    "Gambito de Dama Aceptado": "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq c3 0 2"
}


class SimulationDialog(QDialog):
    """
    Entorno de prueba y simulación interactiva para verificar visión,
    sincronización y Stockfish sin software externo.
    """
    position_injected = Signal(str)  # emite FEN para el tablero activo

    def __init__(self, parent: Optional[QWidget] = None, theme: str = "dark"):
        super().__init__(parent)
        self._theme = theme
        self.setWindowTitle(tr("Simulador de Partidas y Pruebas Tácticas"))
        self.resize(720, 520)

        t = Theme.get_tokens(theme)
        self.setStyleSheet(f"""
            {Theme.get_application_stylesheet(theme)}
            QDialog {{
                background-color: {t["bg_dialog"]};
                color: {t["text_primary"]};
            }}
        """)

        self._board = chess.Board()

        main_layout = QHBoxLayout(self)

        # 1. Tablero interactivo a la izquierda
        self.board_view = BoardView(self)
        self.board_view.set_app_theme(theme)
        self.board_view.set_board(self._board)
        main_layout.addWidget(self.board_view, stretch=2)

        # 2. Panel de control a la derecha
        ctrl_panel = QWidget()
        ctrl_layout = QVBoxLayout(ctrl_panel)
        ctrl_layout.setSpacing(10)

        # Selector de posición preconfigurada
        ctrl_layout.addWidget(QLabel(tr("Cargar Posición Predefinida:")))
        self.cmb_presets = QComboBox()
        for name, fen in PRESET_POSITIONS.items():
            self.cmb_presets.addItem(tr(name), fen)
        self.cmb_presets.currentIndexChanged.connect(self._on_preset_selected)
        ctrl_layout.addWidget(self.cmb_presets)

        # Entrada FEN manual
        ctrl_layout.addWidget(QLabel(tr("FEN Actual:")))
        self.txt_fen = QLineEdit(self._board.fen())
        ctrl_layout.addWidget(self.txt_fen)

        btn_load_fen = QPushButton(tr("Cargar FEN"))
        btn_load_fen.clicked.connect(self._load_custom_fen)
        ctrl_layout.addWidget(btn_load_fen)

        # Jugadas legales disponibles
        ctrl_layout.addWidget(QLabel(tr("Ejecutar Jugada en Tablero:")))
        self.cmb_moves = QComboBox()
        self._update_legal_moves_combo()
        ctrl_layout.addWidget(self.cmb_moves)

        row_btns = QHBoxLayout()
        self.btn_play_move = QPushButton(tr("Hacer Jugada"))
        self.btn_play_move.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_play_move.setStyleSheet(Theme.get_button_style("secondary", self._theme))
        self.btn_play_move.clicked.connect(self._play_selected_move)
        row_btns.addWidget(self.btn_play_move)

        self.btn_undo = QPushButton(tr("Deshacer"))
        self.btn_undo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_undo.setStyleSheet(Theme.get_button_style("neutral", self._theme))
        self.btn_undo.clicked.connect(self._undo_move)
        row_btns.addWidget(self.btn_undo)
        ctrl_layout.addLayout(row_btns)

        # Botón para inyectar al asistente
        self.btn_inject = QPushButton(tr("Inyectar Posición a Chess Vision"))
        self.btn_inject.setObjectName("btnInject")
        self.btn_inject.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_inject.setStyleSheet(Theme.get_button_style("primary", self._theme))
        self.btn_inject.clicked.connect(self._inject_to_assistant)
        ctrl_layout.addWidget(self.btn_inject)

        ctrl_layout.addStretch()

        # Botón Cerrar
        btn_close = QPushButton(tr("Cerrar"))
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(Theme.get_button_style("neutral", self._theme))
        btn_close.clicked.connect(self.close)
        ctrl_layout.addWidget(btn_close)

        main_layout.addWidget(ctrl_panel, stretch=1)

    def _update_legal_moves_combo(self) -> None:
        """Actualiza la lista desplegable con las jugadas legales en formato SAN."""
        self.cmb_moves.clear()
        moves = list(self._board.legal_moves)
        for mv in moves:
            san = self._board.san(mv)
            self.cmb_moves.addItem(f"{san} ({mv.uci()})", userData=mv)

    def _on_preset_selected(self, index: int | str) -> None:
        fen = PRESET_POSITIONS.get(index) if isinstance(index, str) else self.cmb_presets.itemData(index)
        if fen:
            self._set_fen_internal(fen)

    def _load_custom_fen(self) -> None:
        fen = self.txt_fen.text().strip()
        self._set_fen_internal(fen)

    def _set_fen_internal(self, fen: str) -> None:
        try:
            self._board = chess.Board(fen)
            self.board_view.set_board(self._board)
            self.txt_fen.setText(self._board.fen())
            self._update_legal_moves_combo()
        except ValueError:
            pass

    def _play_selected_move(self) -> None:
        idx = self.cmb_moves.currentIndex()
        if idx >= 0:
            mv = self.cmb_moves.itemData(idx)
            if mv and mv in self._board.legal_moves:
                self._board.push(mv)
                self.board_view.set_board(self._board)
                self.txt_fen.setText(self._board.fen())
                self._update_legal_moves_combo()

    def _undo_move(self) -> None:
        if self._board.move_stack:
            self._board.pop()
            self.board_view.set_board(self._board)
            self.txt_fen.setText(self._board.fen())
            self._update_legal_moves_combo()

    def _inject_to_assistant(self) -> None:
        self.position_injected.emit(self._board.fen())
