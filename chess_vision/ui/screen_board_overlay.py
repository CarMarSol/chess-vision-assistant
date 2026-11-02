"""
Ventana de superposición transparente (ScreenBoardOverlay) para Chess Vision Assistant.
Dibuja indicaciones tácticas y flechas de análisis directamente sobre el tablero de la pantalla,
con exclusión de captura de pantalla (WDA_EXCLUDEFROMCAPTURE) para no interferir en el reconocimiento visual.
"""

from __future__ import annotations
import ctypes
from typing import List, Tuple, Optional
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from chess_vision.engine.evaluator import CandidateMove
from chess_vision.ui.arrow_overlay import ArrowOverlay


class ScreenBoardOverlay(QWidget):
    """
    Ventana flotante transparente que se superpone exactamente a la región del tablero en pantalla.
    Permite visualizar las mejores jugadas (Multi-PV) en tiempo real sin interacción de ratón.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # Configurar flags para ventana flotante transparente sin bordes
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )

        # Atributos de transparencia y no intrusión
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self._candidate_moves: List[CandidateMove] = []
        self._orientation: str = "white"
        self._overlay_visible: bool = True
        self._region: Optional[Tuple[int, int, int, int]] = None

        # Excluir de la captura en Windows (WDA_EXCLUDEFROMCAPTURE = 0x00000011)
        self._apply_anti_capture()

    def _apply_anti_capture(self) -> None:
        """Configura la afinidad de visualización de la ventana para que sea invisible a capturas de pantalla."""
        try:
            hwnd = int(self.winId())
            if hasattr(ctypes, "windll") and hasattr(ctypes.windll, "user32"):
                ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x00000011)
        except Exception:
            pass

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._apply_anti_capture()

    def update_geometry(self, region: Tuple[int, int, int, int]) -> None:
        """Posiciona y dimensiona la ventana de superposición exactamente en la región (x, y, w, h)."""
        self._region = region
        x, y, w, h = region
        self.setGeometry(int(x), int(y), int(w), int(h))

    def set_candidate_moves(self, moves: List[CandidateMove]) -> None:
        """Actualiza las jugadas candidatas a proyectar sobre el tablero en pantalla."""
        self._candidate_moves = list(moves) if moves else []
        self.update()

    def clear_arrows(self) -> None:
        """Limpia las flechas proyectadas en el overlay."""
        self._candidate_moves = []
        self.update()

    def set_orientation(self, orientation: str) -> None:
        """Establece la orientación del tablero ('white' o 'black') para el trazado de flechas."""
        self._orientation = orientation if orientation in ("white", "black") else "white"
        self.update()

    def set_overlay_visible(self, visible: bool) -> None:
        """Habilita o deshabilita la visualización de flechas en el overlay."""
        self._overlay_visible = bool(visible)
        self.update()

    def is_overlay_visible(self) -> bool:
        """Indica si el dibujo de flechas en el overlay está activado."""
        return self._overlay_visible

    def paintEvent(self, event: QPaintEvent) -> None:
        """Dibuja las flechas tácticas candidatas sobre el fondo transparente."""
        if not self._overlay_visible or not self._candidate_moves:
            return

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            board_rect = QRectF(self.rect())
            ArrowOverlay.draw_candidate_arrows(
                painter=painter,
                candidate_moves=self._candidate_moves,
                board_rect=board_rect,
                orientation=self._orientation
            )
        finally:
            painter.end()

    def closeEvent(self, event) -> None:
        self.clear_arrows()
        super().closeEvent(event)
