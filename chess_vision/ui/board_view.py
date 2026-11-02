"""
Vista interactiva del tablero de ajedrez en PySide6.
Renderiza el tablero 8x8 con soporte para múltiples temas visuales,
piezas vectoriales, coordenadas, resaltado de jugadas, flechas tácticas
y un editor/corrector visual contextual de casillas con clic derecho.
"""

from __future__ import annotations
from chess_vision.i18n import tr
from typing import Optional, List, Tuple, Dict
import chess
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QAction, QGuiApplication
from PySide6.QtWidgets import QWidget, QSizePolicy, QMenu

from chess_vision.vision.board_detector import BoardDetector
from chess_vision.ui.pieces_svg import PieceRenderer
from chess_vision.ui.arrow_overlay import ArrowOverlay
from chess_vision.engine.evaluator import CandidateMove
from chess_vision.ui.theme import Theme


class BoardView(QWidget):
    """
    Componente gráfico principal de visualización y edición del tablero de ajedrez.
    """
    square_clicked = Signal(str)  # emite 'e4', etc.
    board_edited = Signal(str)    # emite FEN tras edición manual

    # Paletas de temas para el tablero (Casilla clara, Casilla oscura)
    THEMES: Dict[str, Tuple[QColor, QColor, str]] = {
        "green": (QColor(238, 238, 210), QColor(118, 150, 86), "Verde Chess.com"),
        "wood": (QColor(240, 217, 181), QColor(181, 136, 99), "Madera Lichess"),
        "blue": (QColor(222, 227, 230), QColor(140, 162, 173), "Azul Clásico"),
        "mono": (QColor(224, 224, 224), QColor(90, 98, 104), "Monocromo")
    }

    COLOR_LAST_MOVE = QColor(246, 246, 105, 120)  # Amarillo suave
    COLOR_CHECK = QColor(235, 75, 75, 140)       # Rojo jaque

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(280, 280)

        self._board = chess.Board()
        self._orientation: str = "white"  # "white" o "black"
        self._theme_name: str = "green"
        self._candidate_moves: List[CandidateMove] = []
        self._show_arrows: bool = True
        self._last_move: Optional[chess.Move] = None
        self._app_theme: str = "dark"

    def set_app_theme(self, theme_name: str) -> None:
        """Establece el tema global de la aplicación (dark o light) para fondos y coordenadas."""
        self._app_theme = theme_name
        self.update()

    def set_board(self, board: chess.Board) -> None:
        """Actualiza el estado del tablero a renderizar."""
        self._board = board.copy()
        if board.move_stack:
            self._last_move = board.peek()
        else:
            self._last_move = None
        self.update()

    def set_orientation(self, orientation: str) -> None:
        """Establece 'white' o 'black'."""
        self._orientation = orientation.lower()
        self.update()

    def toggle_orientation(self) -> None:
        self._orientation = "black" if self._orientation == "white" else "white"
        self.update()

    def set_theme(self, theme_name: str) -> None:
        """Establece el tema visual del tablero ('green', 'wood', 'blue', 'mono')."""
        if theme_name in self.THEMES:
            self._theme_name = theme_name
            self.update()

    def set_candidate_moves(self, moves: List[CandidateMove]) -> None:
        """Actualiza las flechas de los mejores movimientos."""
        self._candidate_moves = moves
        self.update()

    def set_show_arrows(self, show: bool) -> None:
        self._show_arrows = show
        self.update()

    def _get_board_rect(self) -> QRectF:
        """Calcula el área cuadrada óptima centrada dentro del widget con margen para coordenadas."""
        w = self.width()
        h = self.height()
        margin = 18.0  # margen para letras y números de coordenadas
        available_size = min(w, h) - (margin * 2.0)
        size = max(100.0, available_size)

        left = (w - size) / 2.0
        top = (h - size) / 2.0
        return QRectF(left, top, size, size)

    def _get_square_at_pos(self, pos: QPointF) -> Optional[Tuple[str, int]]:
        """Determina qué casilla (nombre algebraico y square_index) corresponde a una coordenada."""
        board_rect = self._get_board_rect()
        if not board_rect.contains(pos):
            return None

        cell_w = board_rect.width() / 8.0
        cell_h = board_rect.height() / 8.0

        col = int((pos.x() - board_rect.left()) / cell_w)
        row = int((pos.y() - board_rect.top()) / cell_h)

        col = max(0, min(7, col))
        row = max(0, min(7, row))

        sq_name = BoardDetector.get_square_name(row, col, self._orientation)
        sq_chess = chess.parse_square(sq_name)
        return sq_name, sq_chess

    def contextMenuEvent(self, event) -> None:
        """Menú contextual con editor manual de casillas, piezas y FEN."""
        sq_info = self._get_square_at_pos(event.pos())
        if not sq_info:
            return

        sq_name, sq_chess = sq_info
        current_piece = self._board.piece_at(sq_chess)

        menu = QMenu(self)
        t = Theme.get_tokens(self._app_theme)
        is_dark = (str(self._app_theme).lower() != Theme.LIGHT)
        sel_bg = "#2563eb"
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {t["bg_surface"]};
                color: {t["text_primary"]};
                border: 1px solid {t["border_default"]};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 5px 22px 5px 12px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {sel_bg};
                color: #ffffff;
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {t["border_subtle"]};
                margin: 4px 6px;
            }}
        """)

        # Título de la casilla
        piece_desc = current_piece.symbol() if current_piece else tr("Vacía")
        title_action = menu.addAction(tr('Casilla {value0} ({value1})', value0=sq_name, value1=piece_desc))
        title_action.setEnabled(False)
        menu.addSeparator()

        # 1. Submenú Piezas Blancas
        white_menu = menu.addMenu(tr("⚪ Piezas Blancas"))
        white_pieces = [
            ("♔ Rey", chess.KING, chess.WHITE),
            ("♕ Dama", chess.QUEEN, chess.WHITE),
            ("♖ Torre", chess.ROOK, chess.WHITE),
            ("♗ Alfil", chess.BISHOP, chess.WHITE),
            ("♘ Caballo", chess.KNIGHT, chess.WHITE),
            ("♙ Peón", chess.PAWN, chess.WHITE),
        ]
        for name, p_type, color in white_pieces:
            symbol, label = name.split(" ", 1)
            act = white_menu.addAction(f"{symbol} {tr(label)}")
            act.triggered.connect(lambda chk=False, pt=p_type, c=color: self._set_square_piece(sq_chess, pt, c))

        # 2. Submenú Piezas Negras
        black_menu = menu.addMenu(tr("⚫ Piezas Negras"))
        black_pieces = [
            ("♚ Rey", chess.KING, chess.BLACK),
            ("♛ Dama", chess.QUEEN, chess.BLACK),
            ("♜ Torre", chess.ROOK, chess.BLACK),
            ("♝ Alfil", chess.BISHOP, chess.BLACK),
            ("♞ Caballo", chess.KNIGHT, chess.BLACK),
            ("♟ Peón", chess.PAWN, chess.BLACK),
        ]
        for name, p_type, color in black_pieces:
            symbol, label = name.split(" ", 1)
            act = black_menu.addAction(f"{symbol} {tr(label)}")
            act.triggered.connect(lambda chk=False, pt=p_type, c=color: self._set_square_piece(sq_chess, pt, c))

        # 3. Vaciar casilla
        act_clear = menu.addAction(tr("🗑 Vaciar casilla"))
        act_clear.triggered.connect(lambda: self._set_square_piece(sq_chess, None, None))

        menu.addSeparator()

        # 4. Alternar turno
        turn_str = tr("Negras") if self._board.turn == chess.WHITE else tr("Blancas")
        act_turn = menu.addAction(tr('🔄 Cambiar turno a {value0}', value0=turn_str))
        act_turn.triggered.connect(self._toggle_turn)

        menu.addSeparator()

        # 5. Copiar / Pegar FEN
        act_copy_fen = menu.addAction(tr("📋 Copiar FEN"))
        act_copy_fen.triggered.connect(self._copy_fen)

        act_paste_fen = menu.addAction(tr("📥 Pegar FEN"))
        act_paste_fen.triggered.connect(self._paste_fen)

        # 6. Reiniciar tablero
        act_reset = menu.addAction(tr("↺ Posición Inicial"))
        act_reset.triggered.connect(self._reset_position)

        menu.exec(event.globalPos())

    def _set_square_piece(self, square: int, piece_type: Optional[chess.PieceType], color: Optional[chess.Color]) -> None:
        """Modifica manualmente la pieza de una casilla."""
        if piece_type is None or color is None:
            self._board.remove_piece_at(square)
        else:
            self._board.set_piece_at(square, chess.Piece(piece_type, color))

        self.update()
        self.board_edited.emit(self._board.fen())

    def _toggle_turn(self) -> None:
        """Alterna el turno del bando activo."""
        self._board.turn = not self._board.turn
        self.update()
        self.board_edited.emit(self._board.fen())

    def _copy_fen(self) -> None:
        """Copia el FEN actual al portapapeles de Windows."""
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self._board.fen())

    def _paste_fen(self) -> None:
        """Pega y valida el FEN desde el portapapeles."""
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            text = clipboard.text().strip()
            try:
                new_board = chess.Board(text)
                self._board = new_board
                self.update()
                self.board_edited.emit(self._board.fen())
            except ValueError:
                pass

    def _reset_position(self) -> None:
        """Restaura la posición inicial."""
        self._board.reset()
        self.update()
        self.board_edited.emit(self._board.fen())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        t = Theme.get_tokens(self._app_theme)

        # Fondo del widget adaptado al tema
        painter.fillRect(self.rect(), QColor(t["board_view_bg"]))

        board_rect = self._get_board_rect()
        cell_w = board_rect.width() / 8.0
        cell_h = board_rect.height() / 8.0

        # Obtener colores del tema activo
        light_color, dark_color, _ = self.THEMES.get(self._theme_name, self.THEMES["green"])

        # 1. Dibujar casillas 8x8
        for row in range(8):
            for col in range(8):
                is_light = (row + col) % 2 == 0
                cell_color = light_color if is_light else dark_color

                cx = board_rect.left() + col * cell_w
                cy = board_rect.top() + row * cell_h
                cell_rect = QRectF(cx, cy, cell_w, cell_h)

                painter.fillRect(cell_rect, cell_color)

                # Resaltado de última jugada
                sq_name = BoardDetector.get_square_name(row, col, self._orientation)
                sq_chess = chess.parse_square(sq_name)

                if self._last_move:
                    if sq_chess in (self._last_move.from_square, self._last_move.to_square):
                        painter.fillRect(cell_rect, self.COLOR_LAST_MOVE)

                # Resaltado de Rey en Jaque
                if self._board.is_check():
                    king_sq = self._board.king(self._board.turn)
                    if king_sq == sq_chess:
                        painter.fillRect(cell_rect, self.COLOR_CHECK)

        # 2. Dibujar Coordenadas Algebraicas (a-h y 1-8)
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        label_col = QColor(t["board_coord"])
        painter.setPen(label_col)

        for i in range(8):
            # Letras a-h en el borde inferior
            file_char = BoardDetector.FILES[i] if self._orientation == "white" else BoardDetector.FILES[7 - i]
            cx = board_rect.left() + i * cell_w
            cy = board_rect.bottom() + 2
            painter.drawText(QRectF(cx, cy, cell_w, 16), Qt.AlignmentFlag.AlignCenter, file_char)

            # Números 1-8 en el borde izquierdo
            rank_char = BoardDetector.RANKS[7 - i] if self._orientation == "white" else BoardDetector.RANKS[i]
            rx = board_rect.left() - 16
            ry = board_rect.top() + i * cell_h
            painter.drawText(QRectF(rx, ry, 14, cell_h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, rank_char)

        # 3. Dibujar Piezas
        for row in range(8):
            for col in range(8):
                sq_name = BoardDetector.get_square_name(row, col, self._orientation)
                sq_chess = chess.parse_square(sq_name)
                piece = self._board.piece_at(sq_chess)

                if piece:
                    cx = board_rect.left() + col * cell_w
                    cy = board_rect.top() + row * cell_h
                    piece_rect = QRectF(cx, cy, cell_w, cell_h)
                    PieceRenderer.draw_piece(painter, piece.symbol(), piece_rect)

        # 4. Dibujar Flechas de candidatos (Multi-PV)
        if self._show_arrows and self._candidate_moves:
            ArrowOverlay.draw_candidate_arrows(
                painter=painter,
                candidate_moves=self._candidate_moves,
                board_rect=board_rect,
                orientation=self._orientation
            )

        # Borde exterior refinado
        pen = QPen(QColor(t["border_default"]), 1.5)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(board_rect)
