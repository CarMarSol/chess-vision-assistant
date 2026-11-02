"""
Detector automático de orientación del tablero (Blancas abajo vs Negras abajo).
Diseñado para priorizar la perspectiva estándar (blancas abajo) y detectar
la inversión a negras analizando la luminosidad directa de las filas inferiores.
"""

from __future__ import annotations
from typing import Dict, List, Optional
import numpy as np
import cv2
import chess


class OrientationDetector:
    """
    Analiza la distribución y brillo de las piezas en las filas inferiores
    para deducir si el usuario está jugando con Blancas (abajo) o Negras (abajo).
    """

    @classmethod
    def detect_from_square_images(cls, squares: Dict[str, np.ndarray]) -> str:
        """
        Analiza directamente las imágenes recortadas de las casillas de la fila 1 y 2
        (asumiendo inicialmente perspectiva blanca) para verificar si las piezas abajo son blancas o negras.
        """
        from chess_vision.vision.piece_classifier import PieceClassifier

        bottom_squares = [
            "a1", "b1", "c1", "d1", "e1", "f1", "g1", "h1",
            "a2", "b2", "c2", "d2", "e2", "f2", "g2", "h2"
        ]

        top_squares = [
            "a7", "b7", "c7", "d7", "e7", "f7", "g7", "h7",
            "a8", "b8", "c8", "d8", "e8", "f8", "g8", "h8"
        ]

        bottom_luminances: List[float] = []
        top_luminances: List[float] = []

        for sq in bottom_squares:
            img = squares.get(sq)
            if img is not None and PieceClassifier.is_square_occupied(img):
                # Calcular brillo medio en el centro
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
                h, w = gray.shape[:2]
                core = gray[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
                bottom_luminances.append(float(np.mean(core)))

        for sq in top_squares:
            img = squares.get(sq)
            if img is not None and PieceClassifier.is_square_occupied(img):
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
                h, w = gray.shape[:2]
                core = gray[int(h*0.3):int(h*0.7), int(w*0.3):int(w*0.7)]
                top_luminances.append(float(np.mean(core)))

        if bottom_luminances and top_luminances:
            avg_bottom = float(np.mean(bottom_luminances))
            avg_top = float(np.mean(top_luminances))

            # En ajedrez estándar, las piezas blancas son mucho más luminosas que las negras
            # Si abajo son más claras que arriba, o si el promedio abajo es brillante (>135)
            if avg_bottom >= avg_top or avg_bottom > 130:
                return "white"
            elif avg_top - avg_bottom > 25.0 and avg_bottom < 110:
                return "black"

        # Por defecto absoluto, la perspectiva es siempre blancas abajo
        return "white"

    @classmethod
    def detect_from_piece_map(cls, piece_map: Dict[str, Optional[str]]) -> str:
        """
        piece_map: Dict mapping square names (ej. 'e1', 'a8') to piece symbols
        ('P', 'N', 'B', 'R', 'Q', 'K' for white, 'p', 'n', 'b', 'r', 'q', 'k' for black, or None).
        Retorna 'white' o 'black'.
        """
        white_in_1_2 = 0
        black_in_1_2 = 0
        white_in_7_8 = 0
        black_in_7_8 = 0

        for sq, piece in piece_map.items():
            if not piece:
                continue
            rank = sq[1]
            if rank in ('1', '2'):
                if piece.isupper():
                    white_in_1_2 += 1
                else:
                    black_in_1_2 += 1
            elif rank in ('7', '8'):
                if piece.isupper():
                    white_in_7_8 += 1
                else:
                    black_in_7_8 += 1

        # Solo invertir si hay una clara mayoría de piezas negras en la parte inferior
        if black_in_1_2 > white_in_1_2 + 4:
            return "black"

        return "white"

    @classmethod
    def detect_from_board(cls, board: chess.Board) -> str:
        """Determina la orientación a partir de un objeto chess.Board."""
        white_bottom = 0
        black_bottom = 0
        for sq in chess.SQUARES:
            rank = chess.square_rank(sq)
            piece = board.piece_at(sq)
            if piece:
                if rank in (0, 1):  # rangos 1 y 2
                    if piece.color == chess.WHITE:
                        white_bottom += 1
                    else:
                        black_bottom += 1
                elif rank in (6, 7):  # rangos 7 y 8
                    if piece.color == chess.BLACK:
                        white_bottom += 1
                    else:
                        black_bottom += 1
        return "white" if white_bottom >= black_bottom else "black"
