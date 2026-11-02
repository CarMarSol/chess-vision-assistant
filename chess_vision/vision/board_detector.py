"""
Detector y segmentador de tablero de ajedrez 8x8.
Divide la región capturada en las 64 casillas individuales con mapeo algebraico exacto.
"""

from __future__ import annotations
from typing import Any, Dict, Tuple, Optional, List
import numpy as np
import cv2
import chess


class BoardDetector:
    """
    Segmentador y extractor de casillas de ajedrez para visión por computador.
    Mapea píxeles a coordenadas estándar algebraicas (a1 a h8).
    """

    FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    RANKS = ['1', '2', '3', '4', '5', '6', '7', '8']

    @classmethod
    def get_square_name(cls, row: int, col: int, orientation: str = "white") -> str:
        """
        Retorna el nombre algebraico de la casilla (ej. 'e4') dada su fila y columna visual (0 a 7).
        row 0 = parte superior de la imagen
        col 0 = parte izquierda de la imagen
        """
        if orientation == "white":
            # Arriba es rango 8, abajo rango 1; izquierda es 'a', derecha es 'h'
            file_char = cls.FILES[col]
            rank_char = cls.RANKS[7 - row]
        else:
            # Vista desde negras: arriba es rango 1, abajo rango 8; izquierda es 'h', derecha es 'a'
            file_char = cls.FILES[7 - col]
            rank_char = cls.RANKS[row]

        return f"{file_char}{rank_char}"

    @classmethod
    def get_grid_coords_for_square(cls, square_name: str, orientation: str = "white") -> Tuple[int, int]:
        """
        Retorna (row, col) visual (0 a 7) para un nombre de casilla dado (ej. 'e4').
        """
        file_char = square_name[0].lower()
        rank_char = square_name[1]

        file_idx = cls.FILES.index(file_char)
        rank_idx = cls.RANKS.index(rank_char)

        if orientation == "white":
            row = 7 - rank_idx
            col = file_idx
        else:
            row = rank_idx
            col = 7 - file_idx

        return row, col

    @classmethod
    def crop_margins(cls, image: np.ndarray, margin_pct: float = 0.01) -> np.ndarray:
        """Recorta un porcentaje de borde del tablero para eliminar marcos externos."""
        if margin_pct <= 0.0:
            return image

        h, w = image.shape[:2]
        pad_x = int(w * margin_pct)
        pad_y = int(h * margin_pct)

        x1 = max(0, pad_x)
        y1 = max(0, pad_y)
        x2 = min(w, w - pad_x)
        y2 = min(h, h - pad_y)

        if x2 - x1 >= 64 and y2 - y1 >= 64:
            return image[y1:y2, x1:x2]
        return image

    @classmethod
    def extract_squares(
        cls,
        image: np.ndarray,
        orientation: str = "white",
        margin_pct: float = 0.01,
        inset_pct: float = 0.08
    ) -> Dict[str, np.ndarray]:
        """
        Extrae las 64 casillas como recortes individuales etiquetados con su nombre algebraico.
        Aplica auto-calibración de bordes oscuros para descartar los marcos externos con números.
        """
        if image is None or image.size == 0:
            return {}

        # 1. Intentar auto-detección del tablero para descartar márgenes oscuros o claros
        bounds = cls.auto_detect_board_bounds(image)
        if bounds is not None:
            bx, by, bw, bh = bounds
            board_img = image[by:by+bh, bx:bx+bw]
        else:
            board_img = cls.crop_margins(image, margin_pct)

        h, w = board_img.shape[:2]
        cell_w = w / 8.0
        cell_h = h / 8.0

        squares: Dict[str, np.ndarray] = {}

        for row in range(8):
            for col in range(8):
                sq_name = cls.get_square_name(row, col, orientation)

                # Coordenadas brutas de la casilla
                x1 = int(round(col * cell_w))
                y1 = int(round(row * cell_h))
                x2 = int(round((col + 1) * cell_w))
                y2 = int(round((row + 1) * cell_h))

                # Inset interior de seguridad
                pad_cx = int(round((x2 - x1) * inset_pct))
                pad_cy = int(round((y2 - y1) * inset_pct))

                ix1 = max(0, min(x1 + pad_cx, w - 1))
                iy1 = max(0, min(y1 + pad_cy, h - 1))
                ix2 = max(ix1 + 4, min(x2 - pad_cx, w))
                iy2 = max(iy1 + 4, min(y2 - pad_cy, h))

                squares[sq_name] = board_img[iy1:iy2, ix1:ix2]

        return squares

    @classmethod
    def auto_detect_board_bounds(cls, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Detecta el rectángulo del tablero descartando márgenes oscuros (< 55) y márgenes claros (> 245)
        de la interfaz web mediante el contorno de mayor área con relación de aspecto cuadrada (0.85 a 1.15).
        Retorna (x, y, w, h) o None si no se detecta con suficiente confianza.
        """
        if image is None or image.size == 0:
            return None

        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # Determinar si la captura incluye márgenes blancos de ventana web
        has_white_border = (
            np.mean(gray[:5, :] > 245) > 0.4 or
            np.mean(gray[-5:, :] > 245) > 0.4 or
            np.mean(gray[:, :5] > 245) > 0.4 or
            np.mean(gray[:, -5:] > 245) > 0.4
        )

        if has_white_border:
            thresh = ((gray > 50) & (gray < 248)).astype(np.uint8) * 255
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
            thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        else:
            thresh = (gray > 55).astype(np.uint8) * 255

        cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None

        min_area = (h * w) * 0.40  # Debe ocupar al menos el 40% del área capturada
        best_rect = None
        max_area = 0.0

        for c in cnts:
            x, y, bw, bh = cv2.boundingRect(c)
            area = bw * bh
            if area < min_area:
                continue

            aspect = bw / float(max(1, bh))
            if 0.85 <= aspect <= 1.15:
                if area > max_area:
                    max_area = area
                    best_rect = (x, y, bw, bh)

        return best_rect

    @classmethod
    def scan_full_board_fen(
        cls,
        image: np.ndarray,
        orientation: str = "white",
        margin_pct: float = 0.01,
        inset_pct: float = 0.08,
        mental_map: Optional[Any] = None
    ) -> Tuple[str, float]:
        """
        Escanea visualmente las 64 casillas del tablero capturado y retorna la FEN correspondiente
        junto a su índice de confianza global (0.0 a 1.0).
        Reconstruye automáticamente la posición en tiempo real:
        - Detecta ocupación y color de cada casilla.
        - Identifica el tipo morfológico de pieza (K, Q, R, B, N, P).
        - Busca cada Rey por similitud visual en todo el tablero, sin preferir su fila inicial.
        - Determina el turno basándose en casillas resaltadas de la última jugada.
        - Valida que la FEN resultante sea legal y coherente.
        """
        if image is None or image.size == 0:
            return chess.STARTING_FEN, 0.0

        from chess_vision.vision.piece_classifier import PieceClassifier

        # 1. Obtener imagen del tablero y auto-alineación cuadrada
        bounds = cls.auto_detect_board_bounds(image)
        if bounds is not None:
            bx, by, bw, bh = bounds
            board_img = image[by:by+bh, bx:bx+bw]
        else:
            board_img = cls.crop_margins(image, margin_pct)

        h, w = board_img.shape[:2]
        if abs(w - h) > 4 and 0.80 <= w / float(max(1, h)) <= 1.25:
            target_dim = max(w, h)
            padded = np.zeros((target_dim, target_dim, 3), dtype=board_img.dtype)
            if w > h:
                diff = w - h
                padded[diff:, :w] = board_img
                padded[:diff, :w] = board_img[:1, :w]
                board_img = padded
            else:
                diff = h - w
                padded[:h, diff:] = board_img
                padded[:h, :diff] = board_img[:h, :1]
                board_img = padded

        # 2. Extraer casillas según la orientación dada
        squares = cls.extract_squares(board_img, orientation=orientation, margin_pct=0.0, inset_pct=inset_pct)
        if len(squares) != 64:
            return chess.STARTING_FEN, 0.0

        # 3. Detectar casillas resaltadas (para determinar turno activo)
        hl_squares = PieceClassifier.get_highlighted_squares(squares)

        # 4. Clasificar cada casilla
        board_pieces: Dict[chess.Square, Tuple[chess.Piece, float]] = {}
        king_scores: Dict[chess.Square, float] = {}
        confidences: List[float] = []

        for sq in chess.SQUARES:
            sq_name = chess.square_name(sq)
            crop = squares.get(sq_name)
            if crop is None or crop.size == 0:
                continue

            if not PieceClassifier.is_square_occupied(crop):
                continue

            color = PieceClassifier.get_piece_color(crop, square_name=sq_name)
            if color is None:
                continue

            pt, conf = PieceClassifier.classify_piece_type_with_confidence(crop, color, sq_name)
            board_pieces[sq] = (chess.Piece(pt, color), conf)
            confidences.append(conf)

            king_scores[sq] = PieceClassifier.get_king_similarity(crop, color, sq_name)

        visual_pieces = dict(board_pieces)
        # A map from before castling or a missed move cannot label a fresh screenshot.
        if mental_map is not None:
            memory_squares = {rec.square for rec in mental_map.get_surviving_pieces() if rec.square is not None}
            if (memory_squares == set(board_pieces) and
                    all(mental_map.color_at(sq) == piece.color for sq, (piece, _) in board_pieces.items())):
                board_pieces = mental_map.disambiguate_board_pieces(board_pieces)

        # Locate each king using raw visual scores on all occupied squares, without home-rank bias.
        royal_confident = True
        for color in (chess.WHITE, chess.BLACK):
            candidates = sorted(
                ((king_scores[sq], sq) for sq, (piece, _) in visual_pieces.items() if piece.color == color),
                reverse=True,
            )
            if (not candidates or candidates[0][0] < 0.55 or
                    (len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.02)):
                royal_confident = False
                continue
            king_score, king_square = candidates[0]
            for sq, (piece, confidence) in list(board_pieces.items()):
                if piece.color == color and piece.piece_type == chess.KING and sq != king_square:
                    visual_piece, visual_confidence = visual_pieces[sq]
                    alternative = visual_piece.piece_type
                    if alternative == chess.KING:
                        alternative = PieceClassifier.get_second_best_piece_type(
                            squares[chess.square_name(sq)], color, exclude={chess.KING},
                            square_name=chess.square_name(sq),
                        )
                    board_pieces[sq] = (chess.Piece(alternative, color), visual_confidence)
            board_pieces[king_square] = (chess.Piece(chess.KING, color), king_score)

        # 5.5 Regla de conteo de Damas:
        # En ajedrez normal (salvo promociones en fila 8/1), cada bando tiene a lo sumo 1 Dama.
        # Evita que un caballo o alfil se clasifique erróneamente como Dama.
        for side_color in (chess.WHITE, chess.BLACK):
            side_queens = [(sq, c) for sq, (p, c) in board_pieces.items() if p.color == side_color and p.piece_type == chess.QUEEN]
            if len(side_queens) > 1:
                promo_rank = 7 if side_color == chess.WHITE else 0
                has_promo = any(chess.square_rank(sq) == promo_rank for sq, _ in side_queens)
                if not has_promo:
                    known_queen_sq = None
                    if mental_map:
                        for rec in mental_map.get_surviving_pieces(side_color):
                            if rec.piece_type == chess.QUEEN and rec.square is not None:
                                known_queen_sq = rec.square
                                break
                    queen_home = chess.D1 if side_color == chess.WHITE else chess.D8
                    preferred_sq = known_queen_sq if known_queen_sq in [sq for sq, _ in side_queens] else queen_home
                    side_queens.sort(key=lambda sc: (sc[0] == preferred_sq, sc[1]), reverse=True)
                    for sq, _ in side_queens[1:]:
                        p, c = board_pieces[sq]
                        crop_sq = squares.get(chess.square_name(sq))
                        alt_pt = PieceClassifier.get_second_best_piece_type(
                            crop_sq, side_color, exclude={chess.KING, chess.QUEEN}, square_name=chess.square_name(sq)
                        ) if crop_sq is not None else chess.KNIGHT
                        board_pieces[sq] = (chess.Piece(alt_pt, side_color), c * 0.9)

        # Enforce regla de ajedrez: los peones nunca pueden estar en fila 1 ni en fila 8
        for sq, (p, c) in list(board_pieces.items()):
            if p.piece_type == chess.PAWN:
                r = chess.square_rank(sq)
                if r == 0 or r == 7:
                    board_pieces[sq] = (chess.Piece(chess.ROOK, p.color), c)

        # 6. Determinar el turno activo
        turn = chess.WHITE
        if hl_squares:
            for hl_name in hl_squares:
                try:
                    hsq = chess.parse_square(hl_name.lower())
                    if hsq in board_pieces:
                        moved_piece, _ = board_pieces[hsq]
                        turn = not moved_piece.color
                        break
                except Exception:
                    pass

        # 7. Comprobar derechos de enroque estándar
        castling_parts = []
        if chess.E1 in board_pieces and board_pieces[chess.E1][0] == chess.Piece(chess.KING, chess.WHITE):
            if chess.H1 in board_pieces and board_pieces[chess.H1][0] == chess.Piece(chess.ROOK, chess.WHITE):
                castling_parts.append("K")
            if chess.A1 in board_pieces and board_pieces[chess.A1][0] == chess.Piece(chess.ROOK, chess.WHITE):
                castling_parts.append("Q")
        if chess.E8 in board_pieces and board_pieces[chess.E8][0] == chess.Piece(chess.KING, chess.BLACK):
            if chess.H8 in board_pieces and board_pieces[chess.H8][0] == chess.Piece(chess.ROOK, chess.BLACK):
                castling_parts.append("k")
            if chess.A8 in board_pieces and board_pieces[chess.A8][0] == chess.Piece(chess.ROOK, chess.BLACK):
                castling_parts.append("q")
        castling_str = "".join(castling_parts) if castling_parts else "-"

        # 8. Construir cadena FEN
        ranks = []
        for r in range(7, -1, -1):
            empty_count = 0
            rank_str = ""
            for f in range(8):
                sq = chess.square(f, r)
                if sq in board_pieces:
                    if empty_count > 0:
                        rank_str += str(empty_count)
                        empty_count = 0
                    p, _ = board_pieces[sq]
                    rank_str += p.symbol()
                else:
                    empty_count += 1
            if empty_count > 0:
                rank_str += str(empty_count)
            ranks.append(rank_str)

        placement = "/".join(ranks)
        turn_str = "w" if turn == chess.WHITE else "b"
        fen = f"{placement} {turn_str} {castling_str} - 0 1"

        avg_conf = float(np.mean(confidences)) if confidences else 0.90

        if not royal_confident:
            return fen, 0.0

        # 9. Validación sintáctica y de legalidad
        try:
            val_board = chess.Board(fen)
            if not val_board.is_valid():
                alt_fen = f"{placement} {'b' if turn_str == 'w' else 'w'} {castling_str} - 0 1"
                alt_board = chess.Board(alt_fen)
                if alt_board.is_valid():
                    return alt_fen, max(0.85, avg_conf)
            return fen, max(0.85, avg_conf)
        except Exception:
            return fen, max(0.5, avg_conf - 0.20)
