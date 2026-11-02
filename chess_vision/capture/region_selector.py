"""
Selector de región de pantalla interactivo estilo Herramienta de Recortes de Windows.
Permite seleccionar visualmente el tablero de ajedrez con retícula en vivo y lupa de aumento.
"""

from __future__ import annotations
from chess_vision.i18n import tr
from typing import Optional, Tuple
from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QCursor, QPixmap, QImage, QScreen, QGuiApplication
)
from PySide6.QtWidgets import QWidget, QApplication


class RegionSelectorWindow(QWidget):
    """
    Ventana semitransparente fullscreen que permite al usuario arrastrar un rectángulo
    para seleccionar la región exacta del tablero de ajedrez.
    """
    region_selected = Signal(int, int, int, int)  # (x, y, width, height)
    cancelled = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._start_pos: Optional[QPoint] = None
        self._current_pos: Optional[QPoint] = None
        self._is_selecting: bool = False

        # Snapshot de la pantalla completa para la lupa y el velo
        self._screen_pixmap: Optional[QPixmap] = None
        self._virtual_geometry: QRect = QRect()

        self._init_geometry()

    def _init_geometry(self) -> None:
        """Calcula la geometría unificada de todas las pantallas conectadas."""
        screens = QGuiApplication.screens()
        if not screens:
            return

        combined_rect = screens[0].geometry()
        for screen in screens[1:]:
            combined_rect = combined_rect.united(screen.geometry())

        self._virtual_geometry = combined_rect
        self.setGeometry(combined_rect)

    def start_selection(self) -> None:
        """Captura la pantalla actual, muestra la ventana y espera la interacción del usuario."""
        self._init_geometry()

        # Capturar pantalla virtual completa
        primary_screen = QGuiApplication.primaryScreen()
        if primary_screen:
            # Capturar monitor primario o ventana completa
            self._screen_pixmap = primary_screen.grabWindow(
                0,
                self._virtual_geometry.x(),
                self._virtual_geometry.y(),
                self._virtual_geometry.width(),
                self._virtual_geometry.height()
            )

        self._start_pos = None
        self._current_pos = None
        self._is_selecting = False

        self.show()
        self.raise_()
        self.activateWindow()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
            self.close()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._confirm_selection()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_pos = event.globalPosition().toPoint()
            self._current_pos = self._start_pos
            self._is_selecting = True
            self.update()

    def mouseMoveEvent(self, event) -> None:
        self._current_pos = event.globalPosition().toPoint()
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._is_selecting:
            self._current_pos = event.globalPosition().toPoint()
            self._is_selecting = False
            self._confirm_selection()

    def _get_current_rect(self) -> QRect:
        if not self._start_pos or not self._current_pos:
            return QRect()
        x1 = min(self._start_pos.x(), self._current_pos.x())
        y1 = min(self._start_pos.y(), self._current_pos.y())
        x2 = max(self._start_pos.x(), self._current_pos.x())
        y2 = max(self._start_pos.y(), self._current_pos.y())
        return QRect(x1, y1, x2 - x1, y2 - y1)

    def _confirm_selection(self) -> None:
        rect = self._get_current_rect()
        if rect.width() >= 50 and rect.height() >= 50:
            self.region_selected.emit(rect.x(), rect.y(), rect.width(), rect.height())
            self.close()
        else:
            # Muy pequeño, ignorar o cancelar
            self.cancelled.emit()
            self.close()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Fondo oscuro translúcido (Velo de recorte)
        overlay_color = QColor(10, 15, 25, 140)
        painter.fillRect(self.rect(), overlay_color)

        rect = self._get_current_rect()

        if self._screen_pixmap and not rect.isEmpty():
            # 2. Dibujar área seleccionada nítida (sin velo)
            # Convertir coordenadas globales a locales de la ventana
            local_rect = QRect(
                rect.x() - self._virtual_geometry.x(),
                rect.y() - self._virtual_geometry.y(),
                rect.width(),
                rect.height()
            )
            painter.drawPixmap(local_rect, self._screen_pixmap, local_rect)

            # 3. Borde elegante con acento cian / verde
            border_pen = QPen(QColor(38, 194, 163, 240), 2, Qt.PenStyle.SolidLine)
            painter.setPen(border_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(local_rect)

            # 4. Cuadrícula de guía 8x8 translúcida para encajar el tablero
            grid_pen = QPen(QColor(255, 255, 255, 60), 1, Qt.PenStyle.DashLine)
            painter.setPen(grid_pen)
            cell_w = local_rect.width() / 8.0
            cell_h = local_rect.height() / 8.0
            for i in range(1, 8):
                # Líneas verticales
                vx = local_rect.x() + int(i * cell_w)
                painter.drawLine(vx, local_rect.top(), vx, local_rect.bottom())
                # Líneas horizontales
                hy = local_rect.y() + int(i * cell_h)
                painter.drawLine(local_rect.left(), hy, local_rect.right(), hy)

            # 5. Etiqueta con dimensiones en vivo (ej. "800 x 800 px")
            info_text = tr("Región Tablero: {width} x {height} px  (Soltar ratón para confirmar)", width=rect.width(), height=rect.height())
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            text_rect = QRect(local_rect.left(), max(0, local_rect.top() - 28), 420, 24)
            painter.fillRect(text_rect, QColor(20, 24, 33, 220))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, info_text)

        # 6. Lupa flotante (Magnifier) cerca del cursor
        if self._current_pos and self._screen_pixmap:
            self._draw_magnifier(painter, self._current_pos)

    def _draw_magnifier(self, painter: QPainter, global_pos: QPoint) -> None:
        """Dibuja una lupa circular con aumento 3x y retícula central."""
        local_x = global_pos.x() - self._virtual_geometry.x()
        local_y = global_pos.y() - self._virtual_geometry.y()

        mag_size = 130
        offset_x = 25
        offset_y = 25

        # Evitar salirse de la pantalla
        if local_x + offset_x + mag_size > self.width():
            offset_x = -mag_size - 25
        if local_y + offset_y + mag_size > self.height():
            offset_y = -mag_size - 25

        dest_rect = QRect(local_x + offset_x, local_y + offset_y, mag_size, mag_size)

        # Área de origen a ampliar (ej. 32x32 píxeles)
        src_radius = 20
        src_rect = QRect(local_x - src_radius, local_y - src_radius, src_radius * 2, src_radius * 2)

        # Guardar estado de pintor
        painter.save()

        # Recorte circular
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addEllipse(dest_rect)
        painter.setClipPath(path)

        # Fondo negro
        painter.fillRect(dest_rect, QColor(0, 0, 0))

        # Copiar y ampliar snapshot
        painter.drawPixmap(dest_rect, self._screen_pixmap, src_rect)

        # Retícula central (crosshair)
        painter.setClipping(False)
        center_x = dest_rect.center().x()
        center_y = dest_rect.center().y()

        reticle_pen = QPen(QColor(255, 50, 50, 200), 1)
        painter.setPen(reticle_pen)
        painter.drawLine(center_x - 10, center_y, center_x + 10, center_y)
        painter.drawLine(center_x, center_y - 10, center_x, center_y + 10)

        # Borde exterior de la lupa
        border_pen = QPen(QColor(38, 194, 163, 255), 3)
        painter.setPen(border_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(dest_rect)

        painter.restore()
