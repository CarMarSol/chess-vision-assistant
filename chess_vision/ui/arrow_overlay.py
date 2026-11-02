"""
Overlay de flechas tácticas de ajedrez para PySide6.
Dibuja flechas semitransparentes de grosor y color diferenciados para las 3 mejores jugadas.
"""

from __future__ import annotations
import math
from typing import List, Tuple, Optional
import chess
from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPolygonF, QPainterPath

from chess_vision.engine.evaluator import CandidateMove
from chess_vision.vision.board_detector import BoardDetector


class ArrowOverlay:
    """
    Dibuja flechas semitransparentes sobre el tablero de ajedrez para los movimientos candidatos.
    """

    COLOR_ADAPTIVE = QColor(57, 255, 20, 235)        # #39FF14 Verde Neón Fosforito (Recomendado)
    COLOR_ADAPTIVE_OUTLINE = QColor(10, 35, 10, 210) # Contorno sutil oscuro para contraste

    DEFAULT_COLORS = {
        1: QColor(38, 194, 163, 220),   # #26C2A3 - Verde / Cian brillante (Mejor jugada)
        2: QColor(27, 143, 216, 200),   # #1B8FD8 - Azul (Alternativa 1)
        3: QColor(255, 165, 0, 185),    # #FFA500 - Naranja / Ámbar (Alternativa 2)
        4: QColor(160, 100, 220, 175),  # #A064DC - Púrpura suave (Alternativa 3)
    }

    @classmethod
    def get_square_center(
        cls,
        square_name: str,
        board_rect: QRectF,
        orientation: str = "white"
    ) -> QPointF:
        """Calcula el centro geométrico de una casilla en píxeles."""
        row, col = BoardDetector.get_grid_coords_for_square(square_name, orientation)
        cell_w = board_rect.width() / 8.0
        cell_h = board_rect.height() / 8.0

        cx = board_rect.left() + (col + 0.5) * cell_w
        cy = board_rect.top() + (row + 0.5) * cell_h
        return QPointF(cx, cy)

    @classmethod
    def draw_candidate_arrows(
        cls,
        painter: QPainter,
        candidate_moves: List[CandidateMove],
        board_rect: QRectF,
        orientation: str = "white"
    ) -> None:
        """
        Dibuja las flechas de los movimientos candidatos.
        Si existe una jugada recomendada adaptativa (is_adaptive_pick == True),
        se dibuja en color verde fosforito neón (#39FF14) con contorno de contraste
        en la capa superior visible.
        """
        if not candidate_moves:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Separar candidata adaptativa de las estándar para orden de renderizado
        adaptive_cand = next((c for c in candidate_moves if getattr(c, "is_adaptive_pick", False)), None)
        other_cands = [c for c in candidate_moves if not getattr(c, "is_adaptive_pick", False)]

        # Dibujar candidatos normales de atrás hacia adelante (3, 2, 1)
        moves_to_draw = other_cands[:3]
        for candidate in reversed(moves_to_draw):
            cls._render_single_candidate(painter, candidate, board_rect, orientation, is_adaptive=False)

        # Dibujar la jugada adaptativa al final (capa superior absoluta en color neón)
        if adaptive_cand is not None:
            cls._render_single_candidate(painter, adaptive_cand, board_rect, orientation, is_adaptive=True)

        painter.restore()

    @classmethod
    def _render_single_candidate(
        cls,
        painter: QPainter,
        candidate: CandidateMove,
        board_rect: QRectF,
        orientation: str,
        is_adaptive: bool
    ) -> None:
        """Renderiza una flecha individual con su jerarquía, color y contorno."""
        rank = candidate.rank
        move = candidate.move

        if is_adaptive:
            color = cls.COLOR_ADAPTIVE
        else:
            custom_hex = getattr(candidate.classification, "badge_color", None)
            if custom_hex:
                base_color = QColor(custom_hex)
                alpha = 230 if rank == 1 else (195 if rank == 2 else 170)
                color = QColor(base_color.red(), base_color.green(), base_color.blue(), alpha)
            else:
                color = cls.DEFAULT_COLORS.get(rank, QColor(200, 200, 200, 180))

        # Grosor proporcional al tamaño del tablero y jerarquía del movimiento
        base_thickness = max(4.0, board_rect.width() / 45.0)
        if is_adaptive:
            thickness = base_thickness * 1.35
        else:
            thickness = base_thickness * (1.3 if rank == 1 else (1.0 if rank == 2 else 0.8))

        from_sq = chess.square_name(move.from_square)
        to_sq = chess.square_name(move.to_square)

        p1 = cls.get_square_center(from_sq, board_rect, orientation)
        p2 = cls.get_square_center(to_sq, board_rect, orientation)

        # Verificar si es un movimiento de caballo (Knight)
        from_file = chess.square_file(move.from_square)
        from_rank = chess.square_rank(move.from_square)
        to_file = chess.square_file(move.to_square)
        to_rank = chess.square_rank(move.to_square)

        dx = abs(from_file - to_file)
        dy = abs(from_rank - to_rank)
        is_knight_move = (dx == 1 and dy == 2) or (dx == 2 and dy == 1)

        if is_knight_move:
            cls._draw_knight_arrow(
                painter, p1, p2, thickness, color,
                from_file, from_rank, to_file, to_rank,
                board_rect, orientation, is_adaptive=is_adaptive
            )
        else:
            cls._draw_straight_arrow(painter, p1, p2, thickness, color, is_adaptive=is_adaptive)

    @classmethod
    def _draw_straight_arrow(
        cls,
        painter: QPainter,
        p1: QPointF,
        p2: QPointF,
        thickness: float,
        color: QColor,
        is_adaptive: bool = False
    ) -> None:
        """Dibuja una flecha recta aerodinámica desde p1 hasta p2."""
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if length < 10.0:
            return

        ux = dx / length
        uy = dy / length

        # Tamaño de la cabeza de la flecha
        head_length = max(14.0, thickness * 2.4)
        head_width = max(16.0, thickness * 2.8)

        # Punto donde termina la línea y comienza la base de la cabeza
        shaft_end = QPointF(p2.x() - ux * (head_length * 0.75), p2.y() - uy * (head_length * 0.75))

        # Si es flecha adaptativa, dibujar primero contorno oscuro para máximo contraste
        if is_adaptive:
            outline_pen = QPen(
                cls.COLOR_ADAPTIVE_OUTLINE, thickness + 3.0,
                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
            )
            painter.setPen(outline_pen)
            painter.drawLine(p1, shaft_end)
            cls._draw_arrow_head(painter, p2, ux, uy, head_length + 2.5, head_width + 3.5, cls.COLOR_ADAPTIVE_OUTLINE)

        # Dibujar fuste de la flecha
        pen = QPen(color, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(p1, shaft_end)

        # Dibujar punta triangular nítida
        cls._draw_arrow_head(painter, p2, ux, uy, head_length, head_width, color)

    @classmethod
    def _draw_knight_arrow(
        cls,
        painter: QPainter,
        p1: QPointF,
        p2: QPointF,
        thickness: float,
        color: QColor,
        f1: int, r1: int, f2: int, r2: int,
        board_rect: QRectF,
        orientation: str,
        is_adaptive: bool = False
    ) -> None:
        """
        Dibuja una flecha en forma de L para el movimiento del caballo.
        El codo de la L se orienta a lo largo del eje dominante.
        """
        cell_w = board_rect.width() / 8.0
        cell_h = board_rect.height() / 8.0

        # Si el desplazamiento vertical es 2 y horizontal es 1
        if abs(r2 - r1) == 2:
            elbow_sq = chess.square_name(chess.square(f1, r2))
        else:
            elbow_sq = chess.square_name(chess.square(f2, r1))

        elbow_pt = cls.get_square_center(elbow_sq, board_rect, orientation)

        # Vector de la última sección (de elbow_pt a p2)
        dx = p2.x() - elbow_pt.x()
        dy = p2.y() - elbow_pt.y()
        seg_len = math.hypot(dx, dy)
        if seg_len < 5.0:
            return

        ux = dx / seg_len
        uy = dy / seg_len

        head_length = max(14.0, thickness * 2.4)
        head_width = max(16.0, thickness * 2.8)

        shaft_end = QPointF(p2.x() - ux * (head_length * 0.75), p2.y() - uy * (head_length * 0.75))

        # Trazar línea en L
        path = QPainterPath()
        path.moveTo(p1)
        path.lineTo(elbow_pt)
        path.lineTo(shaft_end)

        # Contorno sutil si es adaptativa
        if is_adaptive:
            outline_pen = QPen(
                cls.COLOR_ADAPTIVE_OUTLINE, thickness + 3.0,
                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
            )
            painter.setPen(outline_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            cls._draw_arrow_head(painter, p2, ux, uy, head_length + 2.5, head_width + 3.5, cls.COLOR_ADAPTIVE_OUTLINE)

        pen = QPen(color, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # Cabeza en el destino
        cls._draw_arrow_head(painter, p2, ux, uy, head_length, head_width, color)

    @classmethod
    def _draw_arrow_head(
        cls,
        painter: QPainter,
        tip: QPointF,
        ux: float,
        uy: float,
        length: float,
        width: float,
        color: QColor
    ) -> None:
        """Dibuja el polígono de la punta de la flecha con sombreado suave."""
        # Vector perpendicular
        px = -uy
        py = ux

        base_center = QPointF(tip.x() - ux * length, tip.y() - uy * length)
        left = QPointF(base_center.x() + px * (width / 2.0), base_center.y() + py * (width / 2.0))
        right = QPointF(base_center.x() - px * (width / 2.0), base_center.y() - py * (width / 2.0))

        # Punta indentada para acabado aerodinámico moderno
        notch = QPointF(base_center.x() + ux * (length * 0.25), base_center.y() + uy * (length * 0.25))

        polygon = QPolygonF([tip, left, notch, right])

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPolygon(polygon)
