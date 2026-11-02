"""
Panel de evaluación táctica y visualizador de los 3 mejores movimientos (Multi-PV).
Incluye barra de evaluación bicolor estilizada y tarjetas informativas con soporte
completo para Modo Oscuro y Modo Claro.
"""

from __future__ import annotations
from chess_vision.i18n import tr
import math
from typing import Optional, List
import chess
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QSizePolicy
)
from chess_vision.engine.evaluator import CandidateMove, PositionAnalysis
from chess_vision.engine.accuracy_tracker import AccuracySummary
from chess_vision.ui.theme import Theme


class EvalBarWidget(QWidget):
    """
    Barra vertical de evaluación estandarizada (Blanco vs Negro).
    Diseño refinado con esquinas redondeadas, indicador numérico de alta legibilidad
    y adaptación a tema claro y oscuro.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedWidth(28)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._score_white_val: float = 0.0  # Centipeones / 100 (-10.0 a +10.0)
        self._display_text: str = "0.0"
        self._is_mate: bool = False
        self._theme: str = "dark"

    def set_theme(self, theme_name: str) -> None:
        """Actualiza el tema de la barra de evaluación."""
        self._theme = theme_name
        self.update()

    def update_evaluation(self, eval_score: float, display_text: str = "0.0", is_mate: bool = False) -> None:
        """
        eval_score: centipeones divididos entre 100 desde perspectiva de blancas (+1.5 = +1.5 blancas).
        """
        self._score_white_val = eval_score
        self._display_text = display_text
        self._is_mate = is_mate
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        w = float(rect.width())
        h = float(rect.height())
        radius = 6.0

        # Calcular porcentaje de blancas (0.0 a 1.0)
        if self._is_mate:
            pct_white = 1.0 if self._score_white_val > 0 else 0.0
        else:
            cp = self._score_white_val * 100.0
            try:
                pct_white = 1.0 / (1.0 + math.exp(-0.004 * cp))
            except OverflowError:
                pct_white = 1.0 if cp > 0 else 0.0

        pct_white = max(0.04, min(0.96, pct_white))
        white_height = int(h * pct_white)
        black_height = int(h - white_height)

        is_dark = (str(self._theme).lower() != Theme.LIGHT)
        col_black_area = QColor(24, 28, 38) if is_dark else QColor(51, 65, 85)
        col_white_area = QColor(248, 250, 252)
        border_col = QColor(51, 65, 85) if is_dark else QColor(203, 213, 225)

        # Máscara con esquinas redondeadas
        clip_path = QPainterPath()
        clip_path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
        painter.setClipPath(clip_path)

        # Mitad superior = Negras
        painter.fillRect(QRectF(0, 0, w, black_height), col_black_area)

        # Mitad inferior = Blancas
        painter.fillRect(QRectF(0, black_height, w, white_height), col_white_area)

        # Desactivar clipping para trazar borde nítido
        painter.setClipping(False)
        pen = QPen(border_col, 1.2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(0.6, 0.6, w - 1.2, h - 1.2), radius, radius)

        # Texto de evaluación
        font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(font)

        if self._score_white_val >= 0:
            # Ventaja blanca: texto en la parte inferior sobre fondo blanco
            painter.setPen(QColor(15, 23, 42))
            text_y = h - 6
            painter.drawText(QRectF(0, text_y - 16, w, 16), Qt.AlignmentFlag.AlignCenter, self._display_text)
        else:
            # Ventaja negra: texto en la parte superior sobre fondo oscuro
            painter.setPen(QColor(248, 250, 252))
            text_y = 6
            painter.drawText(QRectF(0, text_y, w, 16), Qt.AlignmentFlag.AlignCenter, self._display_text)


class MoveCardWidget(QFrame):
    """
    Tarjeta visual interactiva que muestra un movimiento candidato Multi-PV
    con su badge de calidad, puntuación, jugada SAN, win-rate y microinteracción hover.
    """

    def __init__(self, rank: int, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.rank = rank
        self._theme: str = "dark"
        self._candidate: Optional[CandidateMove] = None
        self._turn: chess.Color = chess.WHITE
        self._target_accuracy: Optional[int] = None
        self._is_adaptive: bool = False

        self.setObjectName("MoveCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(4)

        # Fila superior: Rank + SAN + Badge + Score
        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        self.lbl_rank = QLabel(f"#{rank}")
        top_row.addWidget(self.lbl_rank)

        self.lbl_san = QLabel("---")
        top_row.addWidget(self.lbl_san)

        top_row.addStretch()

        self.lbl_badge = QLabel(tr("Mejor jugada"))
        top_row.addWidget(self.lbl_badge)

        self.lbl_score = QLabel("+0.00")
        top_row.addWidget(self.lbl_score)

        layout.addLayout(top_row)

        # Fila inferior: Win Rate + Profundidad + Detalle
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(12)

        self.lbl_winrate = QLabel(tr("Win: 50%"))
        bottom_row.addWidget(self.lbl_winrate)

        self.lbl_depth = QLabel(tr("d: 0"))
        bottom_row.addWidget(self.lbl_depth)

        bottom_row.addStretch()

        self.lbl_desc = QLabel("")
        bottom_row.addWidget(self.lbl_desc)

        layout.addLayout(bottom_row)

        self.set_theme("dark")

    def set_theme(self, theme_name: str) -> None:
        """Aplica el tema seleccionado y refresca todos los componentes."""
        self._theme = theme_name
        t = Theme.get_tokens(theme_name)
        is_dark = (str(theme_name).lower() != Theme.LIGHT)

        # Estilo del contenedor de la tarjeta
        self.setStyleSheet(Theme.get_move_card_style(theme_name, is_adaptive=self._is_adaptive))

        # Tipografía base
        self.lbl_rank.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_san.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self.lbl_score.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_winrate.setFont(QFont("Segoe UI", 8))
        self.lbl_depth.setFont(QFont("Segoe UI", 8))
        self.lbl_desc.setFont(QFont("Segoe UI", 8))

        # Colores de etiquetas según tema
        if not self._is_adaptive:
            self.lbl_rank.setStyleSheet(f"color: {t['text_muted']}; font-weight: bold;")
        else:
            neon_col = "#39ff14" if is_dark else "#15803d"
            self.lbl_rank.setStyleSheet(f"color: {neon_col}; font-weight: bold;")

        self.lbl_san.setStyleSheet(f"color: {t['text_primary']}; font-weight: bold;")
        self.lbl_winrate.setStyleSheet(f"color: {t['text_secondary']};")
        self.lbl_depth.setStyleSheet(f"color: {t['text_secondary']};")
        self.lbl_desc.setStyleSheet(f"color: {t['text_muted']}; font-style: italic;")

        # Si ya hay un candidato asignado, refrescar sus badges y scores
        self._apply_candidate_data()

    def set_candidate(
        self,
        candidate: Optional[CandidateMove],
        turn: chess.Color,
        target_accuracy: Optional[int] = None
    ) -> None:
        """Actualiza el contenido de la tarjeta con los datos del candidato."""
        self._candidate = candidate
        self._turn = turn
        self._target_accuracy = target_accuracy
        self._is_adaptive = bool(candidate and getattr(candidate, "is_adaptive_pick", False))
        self._apply_candidate_data()

    def _apply_candidate_data(self) -> None:
        t = Theme.get_tokens(self._theme)
        is_dark = (str(self._theme).lower() != Theme.LIGHT)

        # Reaplicar stylesheet de la tarjeta (para alternar borde verde si es adaptativa)
        self.setStyleSheet(Theme.get_move_card_style(self._theme, is_adaptive=self._is_adaptive))

        if self._candidate is None:
            self.lbl_san.setText("---")
            self.lbl_score.setText("")
            self.lbl_badge.setText("---")
            badge_bg = "#334155" if is_dark else "#e2e8f0"
            badge_fg = "#94a3b8" if is_dark else "#64748b"
            self.lbl_badge.setStyleSheet(f"background-color: {badge_bg}; color: {badge_fg}; padding: 2px 7px; border-radius: 4px;")
            self.lbl_winrate.setText("")
            self.lbl_depth.setText("")
            self.lbl_desc.setText("")
            return

        candidate = self._candidate
        cls_meta = candidate.classification
        self.lbl_san.setText(f"{candidate.san}")

        if self._is_adaptive:
            tgt_text = f" ({self._target_accuracy}%)" if self._target_accuracy else ""
            badge_text = tr("⚡ Recomendado{value0}", value0=tgt_text)
            bg_col = "#39FF14"
            fg_col = "#052e16"
            self.lbl_rank.setStyleSheet(f"color: {bg_col}; font-weight: bold;")
        else:
            badge_text = f"{cls_meta.symbol} {tr(cls_meta.label)}".strip()
            bg_col = cls_meta.badge_color or ("#10b981" if is_dark else "#059669")
            fg_col = "#ffffff"
            if candidate.is_style_pick:
                badge_text = tr("★ Estilo · {value0}", value0=tr(cls_meta.label)).strip()
                bg_col = "#8b5cf6" if is_dark else "#7c3aed"
            elif candidate.is_objective_best and candidate.rank > 1:
                badge_text = tr("⚙ Motor #1 · {value0}", value0=tr(cls_meta.label)).strip()

        self.lbl_badge.setText(badge_text)
        self.lbl_badge.setStyleSheet(f"""
            background-color: {bg_col};
            color: {fg_col};
            font-size: 10px;
            font-weight: bold;
            padding: 2px 7px;
            border-radius: 4px;
        """)

        # Puntuación
        score_text = candidate.display_score
        self.lbl_score.setText(score_text)
        if "-" in score_text:
            score_col = "#ef4444" if is_dark else "#dc2626"
        elif self._is_adaptive:
            score_col = "#39FF14" if is_dark else "#16a34a"
        else:
            score_col = "#10b981" if is_dark else "#059669"
        self.lbl_score.setStyleSheet(f"color: {score_col}; font-weight: bold; font-size: 11px;")

        self.lbl_winrate.setText(tr('Win: {value0:.1f}%', value0=candidate.win_rate))
        self.lbl_depth.setText(tr('d: {value0}', value0=candidate.depth))

        desc = getattr(candidate, "adaptive_reason", "") or (tr(cls_meta.description)[:32] if cls_meta.description else "")
        self.lbl_desc.setText(desc)


class AccuracyWidget(QFrame):
    """
    Widget visual moderno que muestra la precisión CAPS en tiempo real de Blancas y Negras.
    Diseño en dos filas claras, compatible con modo oscuro y modo claro.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme: str = "dark"
        self._summary: Optional[AccuracySummary] = None
        self.setObjectName("AccuracyWidget")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # 1. Cabecera
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_header = QLabel(tr("🎯 Precisión en Tiempo Real"))
        header_layout.addWidget(self.lbl_header)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 2. Fila de Blancas
        row_white = QHBoxLayout()
        row_white.setSpacing(8)
        self.lbl_white_tag = QLabel(tr("⚪ Blancas"))
        row_white.addWidget(self.lbl_white_tag)

        row_white.addStretch()

        self.lbl_white_acc = QLabel("--")
        row_white.addWidget(self.lbl_white_acc)

        self.lbl_white_last = QLabel(tr("Última: --"))
        row_white.addWidget(self.lbl_white_last)

        layout.addLayout(row_white)

        # 3. Fila de Negras
        row_black = QHBoxLayout()
        row_black.setSpacing(8)
        self.lbl_black_tag = QLabel(tr("⚫ Negras"))
        row_black.addWidget(self.lbl_black_tag)

        row_black.addStretch()

        self.lbl_black_acc = QLabel("--")
        row_black.addWidget(self.lbl_black_acc)

        self.lbl_black_last = QLabel(tr("Última: --"))
        row_black.addWidget(self.lbl_black_last)

        layout.addLayout(row_black)

        self.set_theme("dark")

    def set_theme(self, theme_name: str) -> None:
        """Actualiza el aspecto según el tema activo."""
        self._theme = theme_name
        t = Theme.get_tokens(theme_name)

        self.setStyleSheet(Theme.get_accuracy_widget_style(theme_name))

        self.lbl_header.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_header.setStyleSheet(f"color: {t['text_primary']}; font-weight: bold;")

        self.lbl_white_tag.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_white_tag.setStyleSheet(f"color: {t['text_primary']};")

        self.lbl_black_tag.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.lbl_black_tag.setStyleSheet(f"color: {t['text_secondary']};")

        self.lbl_white_last.setFont(QFont("Segoe UI", 8))
        self.lbl_white_last.setStyleSheet(f"color: {t['text_muted']};")

        self.lbl_black_last.setFont(QFont("Segoe UI", 8))
        self.lbl_black_last.setStyleSheet(f"color: {t['text_muted']};")

        if self._summary:
            self.update_accuracy(self._summary)
        else:
            self.reset()

    @staticmethod
    def get_accuracy_color(acc: float) -> str:
        """Determina el color visual según el rendimiento de precisión."""
        if acc >= 90.0:
            return "#48bb78"
        elif acc >= 75.0:
            return "#4299e1"
        elif acc >= 60.0:
            return "#ecc94b"
        else:
            return "#f56565"

    def update_accuracy(self, summary: AccuracySummary) -> None:
        """Actualiza dinámicamente las etiquetas de precisión acumulada y última jugada."""
        self._summary = summary
        t = Theme.get_tokens(self._theme)

        # Blancas
        if summary.white_moves > 0:
            col_w = self.get_accuracy_color(summary.white_accuracy)
            self.lbl_white_acc.setText(f"{summary.white_accuracy:.1f}%")
            self.lbl_white_acc.setStyleSheet(f"color: {col_w}; font-weight: bold; font-size: 12px;")
            if summary.white_last_accuracy is not None:
                self.lbl_white_last.setText(tr('Última: {value0:.0f}%', value0=summary.white_last_accuracy))
            else:
                self.lbl_white_last.setText(tr("Última: --"))
        else:
            self.lbl_white_acc.setText("--")
            self.lbl_white_acc.setStyleSheet(f"color: {t['text_muted']}; font-weight: bold; font-size: 12px;")
            self.lbl_white_last.setText(tr("Última: --"))

        # Negras
        if summary.black_moves > 0:
            col_b = self.get_accuracy_color(summary.black_accuracy)
            self.lbl_black_acc.setText(f"{summary.black_accuracy:.1f}%")
            self.lbl_black_acc.setStyleSheet(f"color: {col_b}; font-weight: bold; font-size: 12px;")
            if summary.black_last_accuracy is not None:
                self.lbl_black_last.setText(tr('Última: {value0:.0f}%', value0=summary.black_last_accuracy))
            else:
                self.lbl_black_last.setText(tr("Última: --"))
        else:
            self.lbl_black_acc.setText("--")
            self.lbl_black_acc.setStyleSheet(f"color: {t['text_muted']}; font-weight: bold; font-size: 12px;")
            self.lbl_black_last.setText(tr("Última: --"))

    def reset(self) -> None:
        """Restablece los indicadores de precisión a su estado neutro."""
        self._summary = None
        t = Theme.get_tokens(self._theme)
        self.lbl_white_acc.setText("--")
        self.lbl_white_acc.setStyleSheet(f"color: {t['text_muted']}; font-weight: bold; font-size: 12px;")
        self.lbl_white_last.setText(tr("Última: --"))

        self.lbl_black_acc.setText("--")
        self.lbl_black_acc.setStyleSheet(f"color: {t['text_muted']}; font-weight: bold; font-size: 12px;")
        self.lbl_black_last.setText(tr("Última: --"))


class EvalPanel(QWidget):
    """
    Contenedor principal lateral para barra de evaluación, las 3 mejores jugadas,
    jugada adaptativa anticheat y widget de precisión en tiempo real.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme: str = "dark"
        self.setMinimumWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(10)

        # 1. Barra de evaluación a la izquierda
        self.eval_bar = EvalBarWidget(self)
        main_layout.addWidget(self.eval_bar)

        # 2. Tarjetas de candidatos y widget de precisión a la derecha
        cards_layout = QVBoxLayout()
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(6)

        self.lbl_title = QLabel(tr("Análisis Multi-PV"))
        cards_layout.addWidget(self.lbl_title)

        self.card_1 = MoveCardWidget(rank=1, parent=self)
        self.card_2 = MoveCardWidget(rank=2, parent=self)
        self.card_3 = MoveCardWidget(rank=3, parent=self)

        # 4ª Tarjeta: Recomendación Adaptativa (Fosforito / Anticheat)
        self.card_adaptive = MoveCardWidget(rank=4, parent=self)
        self.card_adaptive.lbl_rank.setText(tr("⚡ REC"))
        self.card_adaptive.setObjectName("AdaptiveCard")
        self.card_adaptive.setVisible(False)

        cards_layout.addWidget(self.card_1)
        cards_layout.addWidget(self.card_2)
        cards_layout.addWidget(self.card_3)
        cards_layout.addWidget(self.card_adaptive)

        # 3. Widget de Precisión en tiempo real
        self.accuracy_widget = AccuracyWidget(parent=self)
        cards_layout.addWidget(self.accuracy_widget)

        cards_layout.addStretch()

        main_layout.addLayout(cards_layout)
        self.set_theme("dark")

    def set_theme(self, theme_name: str) -> None:
        """Propaga el cambio de tema a todos los subwidgets del panel."""
        self._theme = theme_name
        t = Theme.get_tokens(theme_name)

        self.lbl_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_title.setStyleSheet(f"color: {t['text_primary']}; font-weight: bold; margin-bottom: 2px;")

        self.eval_bar.set_theme(theme_name)
        self.card_1.set_theme(theme_name)
        self.card_2.set_theme(theme_name)
        self.card_3.set_theme(theme_name)
        self.card_adaptive.set_theme(theme_name)
        self.accuracy_widget.set_theme(theme_name)

    def update_accuracy(self, summary: AccuracySummary) -> None:
        """Actualiza las métricas de precisión de la partida en el widget."""
        self.accuracy_widget.update_accuracy(summary)

    def reset_accuracy(self) -> None:
        """Restablece el widget de precisión a su estado inicial."""
        self.accuracy_widget.reset()

    def update_analysis(self, analysis: Optional[PositionAnalysis]) -> None:
        """Actualiza el panel completo con los resultados del análisis."""
        if analysis is None or not analysis.top_moves:
            self.eval_bar.update_evaluation(0.0, "0.0")
            self.card_1.set_candidate(None, chess.WHITE)
            self.card_2.set_candidate(None, chess.WHITE)
            self.card_3.set_candidate(None, chess.WHITE)
            self.card_adaptive.set_candidate(None, chess.WHITE)
            self.card_adaptive.setVisible(False)
            return

        # Actualizar barra
        best_candidate = analysis.best_move
        display_score = best_candidate.display_score if best_candidate else "0.0"
        is_mate = (best_candidate.mate_in is not None) if best_candidate else False

        self.eval_bar.update_evaluation(
            eval_score=analysis.evaluation_bar_score,
            display_text=display_score,
            is_mate=is_mate
        )

        target_acc = getattr(analysis, "target_accuracy", None)

        # Actualizar las 3 tarjetas estándar
        c1 = analysis.top_moves[0] if len(analysis.top_moves) >= 1 else None
        c2 = analysis.top_moves[1] if len(analysis.top_moves) >= 2 else None
        c3 = analysis.top_moves[2] if len(analysis.top_moves) >= 3 else None

        self.card_1.set_candidate(c1, analysis.turn, target_accuracy=target_acc)
        self.card_2.set_candidate(c2, analysis.turn, target_accuracy=target_acc)
        self.card_3.set_candidate(c3, analysis.turn, target_accuracy=target_acc)

        # 4ª Tarjeta dedicada: Movimiento recomendado adaptativo (Anticheat / Humanización)
        adaptive_mv = getattr(analysis, "adaptive_move", None)
        if adaptive_mv is not None:
            self.card_adaptive.setVisible(True)
            self.card_adaptive.lbl_rank.setText(f"⚡ #{adaptive_mv.rank}")
            self.card_adaptive.set_candidate(adaptive_mv, analysis.turn, target_accuracy=target_acc)
        else:
            self.card_adaptive.setVisible(False)
