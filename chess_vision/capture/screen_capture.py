"""
Módulo de captura de pantalla ultrarrápido y detección de frames estáticos.
Utiliza MSS y OpenCV/NumPy para capturar regiones de pantalla a alta tasa de refresco
con mínimo consumo de CPU.
"""

from __future__ import annotations
import threading
from typing import Tuple, Optional
import numpy as np
import mss
import cv2


class ScreenCapture:
    """
    Capturador de pantalla optimizado para Chess Vision Assistant.
    Thread-safe mediante almacenamiento local de hilo para instancias de MSS.
    """
    _thread_local = threading.local()

    @classmethod
    def _get_mss_instance(cls) -> mss.mss:
        if not hasattr(cls._thread_local, "sct") or cls._thread_local.sct is None:
            cls._thread_local.sct = mss.mss()
        return cls._thread_local.sct

    @classmethod
    def capture_region(cls, region: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """
        Captura una región específica de la pantalla (x, y, width, height).
        Prioriza QScreen.grabWindow (ultrarrápido, ~1ms, inmune a BitBlt en Windows 11 / DWM).
        Fallback a MSS si no hay QGuiApplication disponible (ej. entornos headless o CLI).
        Retorna la imagen en formato BGR (compatible OpenCV) como uint8 ndarray,
        o None si la región es inválida.
        """
        x, y, w, h = region
        if w <= 10 or h <= 10:
            return None

        # 1. Captura nativa Qt ultrarrápida (~1ms, inmune a fallos BitBlt)
        try:
            from PySide6.QtGui import QGuiApplication, QImage
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                pixmap = screen.grabWindow(0, int(x), int(y), int(w), int(h))
                if not pixmap.isNull():
                    qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_BGR888)
                    arr = np.frombuffer(qimg.bits(), dtype=np.uint8).reshape((qimg.height(), qimg.width(), 3)).copy()
                    return arr
        except Exception:
            pass

        # 2. Fallback a MSS
        monitor = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
        try:
            sct = cls._get_mss_instance()
            sct_img = sct.grab(monitor)
            frame_bgra = np.frombuffer(sct_img.raw, dtype=np.uint8).reshape((sct_img.height, sct_img.width, 4))
            frame_bgr = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
            return frame_bgr
        except Exception as e:
            try:
                cls._thread_local.sct = mss.mss()
            except Exception:
                pass
            return None

    grab_region = capture_region

    @classmethod
    def capture_full_screen(cls, monitor_idx: int = 1) -> Optional[np.ndarray]:
        """Captura un monitor completo (1 = monitor principal, 0 = todos combinados)."""
        # 1. Intentar vía QScreen
        try:
            from PySide6.QtGui import QGuiApplication, QImage
            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                geo = screen.geometry()
                pixmap = screen.grabWindow(0, geo.x(), geo.y(), geo.width(), geo.height())
                if not pixmap.isNull():
                    qimg = pixmap.toImage().convertToFormat(QImage.Format.Format_BGR888)
                    return np.frombuffer(qimg.bits(), dtype=np.uint8).reshape((qimg.height(), qimg.width(), 3)).copy()
        except Exception:
            pass

        # 2. Fallback a MSS
        try:
            sct = cls._get_mss_instance()
            if monitor_idx >= len(sct.monitors):
                monitor_idx = 1
            monitor = sct.monitors[monitor_idx]
            sct_img = sct.grab(monitor)
            frame_bgra = np.frombuffer(sct_img.raw, dtype=np.uint8).reshape((sct_img.height, sct_img.width, 4))
            return cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
        except Exception:
            return None

    @staticmethod
    def compute_frame_difference(frame1: Optional[np.ndarray], frame2: Optional[np.ndarray]) -> float:
        """
        Calcula la diferencia relativa (0.0 a 1.0) entre dos imágenes usando
        MSE (Mean Squared Error) normalizado en escala de grises.
        """
        if frame1 is None or frame2 is None:
            return 1.0

        if frame1.shape != frame2.shape:
            # Redimensionar al tamaño del segundo si difieren mínimamente
            frame1 = cv2.resize(frame1, (frame2.shape[1], frame2.shape[0]))

        # Convertir a escala de grises si tienen 3 canales
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY) if len(frame1.shape) == 3 else frame1
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY) if len(frame2.shape) == 3 else frame2

        # Submuestreo rápido para eficiencia si la imagen es grande (>256x256)
        if gray1.shape[0] > 256 or gray1.shape[1] > 256:
            gray1 = cv2.resize(gray1, (128, 128), interpolation=cv2.INTER_NEAREST)
            gray2 = cv2.resize(gray2, (128, 128), interpolation=cv2.INTER_NEAREST)

        # Diferencia media absoluta normalizada
        diff = cv2.absdiff(gray1, gray2)
        score = float(np.mean(diff)) / 255.0
        return score

    @classmethod
    def has_changed(cls, prev_frame: Optional[np.ndarray], new_frame: Optional[np.ndarray], threshold: float = 0.015) -> bool:
        """
        Determina si el nuevo frame tiene un cambio significativo respecto al anterior.
        Un umbral de 0.015 (1.5% de cambio promedio) filtra el ruido de compresión y reloj.
        """
        if prev_frame is None or new_frame is None:
            return True
        return cls.compute_frame_difference(prev_frame, new_frame) > threshold
