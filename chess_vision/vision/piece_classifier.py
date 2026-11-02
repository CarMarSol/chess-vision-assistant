"""
Clasificador de piezas y detector de cambios en casillas de ajedrez.
Combina análisis de varianza, gradientes, perfiles morfológicos y comparación diferencial.
"""

from __future__ import annotations
from typing import Dict, Tuple, Optional, List
import numpy as np
import cv2
import chess
from chess_vision.vision.piece_references import get_reference_ranking


class PieceClassifier:
    """
    Clasificador visual de ocupación de casillas, color de piezas y detección de movimientos.
    """

    @classmethod
    def is_square_occupied(cls, square_img: np.ndarray, threshold_std: float = 10.0) -> bool:
        """
        Determina con alta fidelidad si una casilla está ocupada o vacía.
        Combina muestreo de fondo en las esquinas, análisis de textura/bordes Sobel,
        y contraste entre el cuerpo de la pieza y el fondo del tablero.
        Soporta casillas vacías resaltadas de Chess.com/Lichess sin falsos positivos,
        y detecta piezas oscuras sobre casillas oscuras y peones estrechos sin fallar.
        """
        if square_img is None or square_img.size == 0:
            return False

        h, w = square_img.shape[:2]
        if h < 8 or w < 8:
            return False

        gray = cv2.cvtColor(square_img, cv2.COLOR_BGR2GRAY) if len(square_img.shape) == 3 else square_img

        # Muestreo de las 4 esquinas exteriores (representan fielmente el fondo del tablero)
        c_h, c_w = max(2, int(h * 0.15)), max(2, int(w * 0.15))
        corners = np.concatenate([
            gray[:c_h, :c_w].flatten(),
            gray[:c_h, -c_w:].flatten(),
            gray[-c_h:, :c_w].flatten(),
            gray[-c_h:, -c_w:].flatten()
        ])
        bg_val = float(np.median(corners))

        # Región central (60% del alto y ancho) donde se ubica el cuerpo de la pieza
        ch1, ch2 = int(h * 0.20), int(h * 0.80)
        cw1, cw2 = int(w * 0.20), int(w * 0.80)
        center_roi = gray[ch1:ch2, cw1:cw2]
        if center_roi.size == 0:
            return False

        # Gradientes de bordes Sobel y desviación típica
        grad_x = cv2.Sobel(center_roi, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(center_roi, cv2.CV_32F, 0, 1, ksize=3)
        grad_mag = float(np.mean(np.sqrt(grad_x**2 + grad_y**2)))
        center_std = float(np.std(center_roi))

        # Contraste centro vs fondo y ratio de píxeles de primer plano
        diff = np.abs(center_roi.astype(np.float32) - bg_val)
        fg_ratio = float(np.mean(diff > 18.0))
        center_diff = abs(float(np.mean(center_roi)) - bg_val)

        # Regla de ocupación:
        # 1. Textura pronunciada por bordes y variabilidad (piezas estándar con textura)
        # 2. O contraste de silueta marcado contra el fondo de la casilla (piezas oscuras sobre fondo verde/madera, o piezas claras)
        is_occ = (grad_mag > 14.0 and center_std > 8.0) or (fg_ratio > 0.12 and (grad_mag > 8.0 or center_diff > 18.0))
        return bool(is_occ)

    @classmethod
    def is_square_empty(cls, square_img: np.ndarray) -> bool:
        """Determina si una casilla está completamente vacía."""
        return not cls.is_square_occupied(square_img)

    @classmethod
    def is_square_highlighted(cls, square_img: np.ndarray) -> bool:
        """
        Detecta si una casilla tiene resaltado de movimiento activo.
        Cubre tonos amarillo brillante (#f7f769), verde lima/oliva (#baca44, webs pizarra/gris)
        y tonos azul/cian de Lichess, evitando falsos positivos con casillas verdes normales de Chess.com (#769656).
        Muestrea esquinas exteriores donde el fondo de la casilla siempre es visible.
        """
        if square_img is None or square_img.size == 0:
            return False

        if len(square_img.shape) != 3 or square_img.shape[2] != 3:
            return False

        h, w = square_img.shape[:2]
        if h < 8 or w < 8:
            return False

        # Muestrear las esquinas exteriores donde el color de fondo o resaltado siempre es visible
        c_h, c_w = max(2, int(h * 0.18)), max(2, int(w * 0.18))
        corners = np.concatenate([
            square_img[:c_h, :c_w],
            square_img[:c_h, -c_w:],
            square_img[-c_h:, :c_w],
            square_img[-c_h:, -c_w:]
        ], axis=0)

        hsv = cv2.cvtColor(corners, cv2.COLOR_BGR2HSV)
        H, S, V = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        # 1. Amarillo brillante (#f7f769, etc.): H in [20, 38], S >= 65, V >= 135
        mask_yellow = (H >= 20) & (H <= 38) & (S >= 65) & (V >= 135)
        # 2. Verde lima / oliva intenso (#baca44, temas pizarra/gris): H in [38, 52], S >= 85, V >= 165
        # (filtra casillas verdes oscuras unhighlighted de Chess.com que tienen V ~ 150)
        mask_lime = (H > 38) & (H <= 52) & (S >= 85) & (V >= 165)
        # 3. Azul / cian de Lichess: H in [90, 125], S >= 65, V >= 135
        mask_cyan = (H >= 90) & (H <= 125) & (S >= 65) & (V >= 135)

        hl_mask = mask_yellow | mask_lime | mask_cyan
        return bool(np.mean(hl_mask) > 0.35)

    @classmethod
    def get_highlighted_squares(cls, squares: Dict[str, np.ndarray]) -> List[str]:
        """
        Retorna la lista de casillas que poseen resaltado de movimiento activo.
        """
        hl_list = []
        for sq_name, img in squares.items():
            if img is not None and cls.is_square_highlighted(img):
                hl_list.append(sq_name)
        return hl_list

    @classmethod
    def are_center_ranks_empty(cls, squares: Dict[str, np.ndarray]) -> bool:
        """
        Regla de oro del inicio ('ni he empezado'):
        Si las filas centrales 3, 4, 5 y 6 (32 casillas) están 100% vacías,
        el tablero está en la posición inicial y la partida aún no ha comenzado.
        Ninguna jugada inicial legal en ajedrez deja las filas 3-6 vacías.
        """
        for file_char in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']:
            for rank_char in ['3', '4', '5', '6']:
                sq_name = f"{file_char}{rank_char}"
                img = squares.get(sq_name)
                if img is not None and cls.is_square_occupied(img):
                    return False
        return True

    # Perfiles de color de temas para calibración de fondo (Luminosidad Casilla Clara, Casilla Oscura)
    THEME_PROFILES = {
        "green": {"light": 230.0, "dark": 130.0},
        "wood": {"light": 225.0, "dark": 140.0},
        "blue": {"light": 226.0, "dark": 150.0},
        "mono": {"light": 224.0, "dark": 95.0}
    }

    @classmethod
    def get_piece_color(
        cls,
        square_img: np.ndarray,
        is_light_square: Optional[bool] = None,
        theme: str = "green",
        square_name: Optional[str] = None
    ) -> Optional[chess.Color]:
        """
        Determina el color de la pieza (chess.WHITE o chess.BLACK).
        Resuelve de forma robusta el desafío de piezas blancas con fino borde oscuro en casillas claras
        (evitando que se descarte el cuerpo blanco y se clasifique erróneamente como negra),
        así como piezas negras en casillas oscuras y peones estrechos.
        """
        if square_img is None or square_img.size == 0:
            return None

        references = get_reference_ranking(square_img)
        if references:
            return references[0][0].color

        gray = cv2.cvtColor(square_img, cv2.COLOR_BGR2GRAY) if len(square_img.shape) == 3 else square_img
        h, w = gray.shape[:2]
        if h < 8 or w < 8:
            return None

        # Muestreo del fondo en las 4 esquinas exteriores
        c_h, c_w = max(2, int(h * 0.15)), max(2, int(w * 0.15))
        corners = np.concatenate([
            gray[:c_h, :c_w].flatten(),
            gray[:c_h, -c_w:].flatten(),
            gray[-c_h:, :c_w].flatten(),
            gray[-c_h:, -c_w:].flatten()
        ])
        bg_val = float(np.median(corners))

        # Región central (60% del ancho y alto donde reside el cuerpo de la pieza)
        ch1, ch2 = int(h * 0.20), int(h * 0.80)
        cw1, cw2 = int(w * 0.20), int(w * 0.80)
        center = gray[ch1:ch2, cw1:cw2]
        if center.size == 0:
            return None

        # 1. Casillas oscuras (bg_val < 180.0):
        # La pieza blanca inyecta masa brillante (> 170) sobre el fondo oscuro.
        # La pieza negra es igual o más oscura que el fondo (nunca supera 160).
        if bg_val < 180.0:
            p_bright = float(np.mean(center > 170.0))
            p_dark = float(np.mean(center < 100.0))
            if p_bright > 0.18:
                return chess.WHITE
            elif p_dark > 0.35 or p_bright < 0.12:
                return chess.BLACK
            return chess.WHITE if float(np.mean(center)) > 135.0 else chess.BLACK

        # 2. Casillas claras (bg_val >= 180.0):
        # Extraer píxeles de primer plano que difieren del fondo claro de la casilla.
        # Una pieza negra sobre casilla clara tiene su silueta en primer plano predominantemente oscura
        # (fg_dark_ratio >= 0.65 y fg_median <= 95.0).
        # Una pieza blanca (como la Dama d1 con base de estrías y corona) tiene masa blanca brillante en fg
        # y su ratio oscuro es inferior al 60% (o fg_median >= 98.0).
        else:
            diff = np.abs(center.astype(float) - bg_val)
            fg = center[diff > 18.0]
            if len(fg) >= 15:
                fg_median = float(np.median(fg))
                fg_dark_ratio = float(np.mean(fg < 100.0))

                # Regla de oro de fila base si se especifica square_name:
                if square_name:
                    r_char = square_name.strip()[-1]
                    if r_char == '1':
                        if fg_dark_ratio < 0.70 or fg_median > 70.0:
                            return chess.WHITE
                    elif r_char in ('7', '8'):
                        if fg_dark_ratio >= 0.60 or fg_median <= 95.0:
                            return chess.BLACK

                if fg_dark_ratio >= 0.65 and fg_median <= 95.0:
                    return chess.BLACK
                else:
                    return chess.WHITE
            else:
                return chess.WHITE if float(np.mean(center)) > 130.0 else chess.BLACK

    @classmethod
    def classify_piece_type_with_confidence(
        cls,
        square_img: np.ndarray,
        color: chess.Color,
        square_name: Optional[str] = None
    ) -> Tuple[chess.PieceType, float]:
        """
        Clasifica el tipo de pieza (P, N, B, R, Q, K) junto con una puntuación de confianza (0.0 a 1.0)
        combinando matriz morfológica física completa (asimetría, perfil apical, almenas) y matching
        multitema por IoU invariante a escala con plantillas cburnett y Neo (Chess.com).
        El rey se decide por similitud y altura; una cruz ancha no lo descarta.
        Las puntas separadas de una corona permiten distinguirla de la cruz.
        """
        if square_img is None or square_img.size == 0:
            return chess.PAWN, 0.0

        references = get_reference_ranking(square_img, color)
        if references:
            piece, score = references[0]
            return piece.piece_type, score

        gray = cv2.cvtColor(square_img, cv2.COLOR_BGR2GRAY) if len(square_img.shape) == 3 else square_img
        h, w = gray.shape[:2]
        if h < 8 or w < 8:
            return chess.PAWN, 0.0

        # Muestreo de las esquinas para el fondo de la casilla
        c_h, c_w = max(2, int(h * 0.15)), max(2, int(w * 0.15))
        corners = np.concatenate([
            gray[:c_h, :c_w].flatten(),
            gray[:c_h, -c_w:].flatten(),
            gray[-c_h:, :c_w].flatten(),
            gray[-c_h:, -c_w:].flatten()
        ])
        bg_val = float(np.median(corners))

        # Extracción de la máscara según color y fondo
        if color == chess.WHITE:
            if bg_val < 180.0:
                mask = ((gray > 165) | (gray < 75)).astype(np.uint8) * 255
            else:
                mask = ((gray < 75) | (gray > 235)).astype(np.uint8) * 255
        else:
            thresh_val = 140 if bg_val > 170 else 100
            mask = (gray < thresh_val).astype(np.uint8) * 255

        kernel = np.ones((3, 3), np.uint8)
        sq_sil = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        # Connected components: extraer el componente principal descartando bordes/números marginales
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(sq_sil)
        if num_labels <= 1:
            return chess.PAWN, 0.0

        areas = stats[1:, cv2.CC_STAT_AREA]
        largest_label = int(np.argmax(areas) + 1)
        main_sil = (labels == largest_label).astype(np.uint8) * 255
        # A thin outline can leave the head detached from the body at small resolutions.
        if stats[largest_label, cv2.CC_STAT_HEIGHT] < h * 0.72:
            for label in range(1, num_labels):
                if (stats[label, cv2.CC_STAT_AREA] >= max(3, areas.max() * 0.025) and
                        abs(centroids[label, 0] - centroids[largest_label, 0]) <= w * 0.20):
                    main_sil[labels == label] = 255

        # Rellenar contornos externos para unificar siluetas con líneas interiores (piezas negras Chess.com)
        cnts, _ = cv2.findContours(main_sil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros_like(main_sil)
        if cnts:
            cv2.drawContours(filled, cnts, -1, 255, -1)
        else:
            filled = main_sil

        ys, xs = np.where(filled > 0)
        if len(ys) == 0:
            return chess.PAWN, 0.0

        bh = ys.max() - ys.min() + 1
        bw = xs.max() - xs.min() + 1
        rel_width = bw / float(w)
        rel_height = bh / float(h)

        crop = filled[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

        # Normalización invariante a bounding box a 32x32 para matching de alta fidelidad
        sq_sil_32 = cv2.resize((crop > 0).astype(np.uint8) * 255, (32, 32), interpolation=cv2.INTER_NEAREST) > 0

        # Asimetría horizontal (fuerte en caballos por hocico vs crin, casi 0 en torres y peones)
        half_w = bw // 2
        left_side = crop[:, :half_w]
        right_side = crop[:, -half_w:]
        diff_sym = np.abs(left_side.astype(float) - np.fliplr(right_side).astype(float))
        asym = float(np.sum(diff_sym > 0)) / float(max(1, np.sum(crop > 0)))

        # Ápice superior fino (primeros 8% de altura de la pieza)
        apex_slice = crop[:max(1, int(bh * 0.08)), :]
        apex_cols = np.any(apex_slice > 0, axis=0) if apex_slice.size > 0 else np.array([])
        apex_w = float(np.sum(apex_cols)) / float(max(1, bw)) if len(apex_cols) > 0 else 0.0

        # Perfil superior (primeros 20% de altura de la pieza)
        top_slice = crop[:max(1, int(bh * 0.20)), :]
        top_density = float(np.mean(top_slice > 0)) if top_slice.size > 0 else 0.0
        cols_active = np.any(top_slice > 0, axis=0) if top_slice.size > 0 else np.array([])
        top_w = float(np.sum(cols_active)) / float(max(1, bw)) if len(cols_active) > 0 else 0.0

        # Matching por IoU con plantillas normalizadas multi-set (cburnett + Neo)
        from chess_vision.vision.piece_templates import get_template_masks
        best_pt = chess.PAWN
        best_iou = -1.0
        ious: Dict[chess.PieceType, float] = {}
        for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]:
            sym = chess.piece_symbol(pt)
            sym = sym.upper() if color == chess.WHITE else sym.lower()
            t_masks = get_template_masks(sym)
            max_pt_iou = 0.0
            for t_mask in t_masks:
                inter = np.sum(sq_sil_32 & t_mask)
                union = np.sum(sq_sil_32 | t_mask)
                t_iou = inter / float(max(1, union))
                if t_iou > max_pt_iou:
                    max_pt_iou = t_iou
            ious[pt] = max_pt_iou
            if max_pt_iou > best_iou:
                best_iou = max_pt_iou
                best_pt = pt

        # A crown has separate tips; a wide horizontal cross alone is not a crown.
        apex_peaks = int(np.count_nonzero(np.diff(np.pad(apex_cols.astype(int), (1, 1))) == 1))
        top_peaks = int(np.count_nonzero(np.diff(np.pad(cols_active.astype(int), (1, 1))) == 1))
        queen_iou = ious.get(chess.QUEEN, 0.0)
        if (rel_height >= 0.72 and apex_peaks >= 3 and top_peaks >= 3 and
                queen_iou >= 0.55 and queen_iou >= best_iou - 0.08):
            return chess.QUEEN, float(queen_iou)

        # The cross may be wide: use measured similarity before narrower morphology rules.
        king_iou = ious.get(chess.KING, 0.0)
        if (rel_height >= 0.72 and best_pt in (chess.KING, chess.BISHOP, chess.QUEEN) and
                king_iou >= 0.55 and king_iou >= best_iou - 0.02):
            return chess.KING, float(king_iou)
        if best_pt == chess.KING:
            best_pt = max((pt for pt in ious if pt != chess.KING), key=ious.get)
            best_iou = ious[best_pt]

        # Matriz física de desambiguación morfológica:
        # 1. Peón compacto evidente (altura y anchura compactas, simétrico)
        if rel_width < 0.65 and rel_height < 0.66 and asym < 0.22:
            return chess.PAWN, max(best_iou, 0.95)

        # 2. Torre inequívoca por almenas planas y anchas:
        # Una torre tiene almenas horizontales planas (apex_w >= 0.30 y top_w >= 0.50).
        # Un caballo JAMÁS tiene un ápice ancho plano con almenas.
        if best_pt == chess.ROOK and apex_w >= 0.30 and top_w >= 0.50:
            return chess.ROOK, max(best_iou, 0.92)

        # 3. Caballo infalible:
        # El caballo es la ÚNICA pieza asimétrica horizontalmente con orejas puntiagudas (hocico a un lado, crin al otro).
        # Un caballo NUNCA tiene almenas planas simétricas de torre ni corona/cruz simétrica de dama/rey.
        is_knight_morph = (
            (asym >= 0.20 and apex_w <= 0.28 and (ious.get(chess.KNIGHT, 0.0) >= ious.get(chess.BISHOP, 0.0) - 0.06 or ious.get(chess.KNIGHT, 0.0) >= 0.48)) or
            (best_pt == chess.KNIGHT and asym >= 0.15 and apex_w <= 0.30)
        )
        if is_knight_morph and (best_pt != chess.QUEEN or ious.get(chess.KNIGHT, 0.0) > ious.get(chess.QUEEN, 0.0)):
            best_pt = chess.KNIGHT
            return chess.KNIGHT, max(best_iou, 0.92)

        # Si IoU dio Torre pero el ápice es estrecho (orejas o mitre), NO puede ser Torre:
        if best_pt == chess.ROOK and apex_w < 0.28:
            if asym >= 0.18 and top_w < 0.50:
                best_pt = chess.KNIGHT
            elif rel_width <= 0.68:
                best_pt = chess.PAWN
            else:
                best_pt = chess.BISHOP

        # 4. Alfil vs Torre vs Peón; the king decision above already uses its IoU.
        if best_pt == chess.BISHOP:
            if top_w >= 0.55 and asym < 0.18 and apex_w >= 0.30:
                best_pt = chess.ROOK
            elif rel_width <= 0.68 and rel_height < 0.68:
                best_pt = chess.PAWN
                best_iou = max(best_iou, ious.get(chess.PAWN, 0.85))

        # Protección final de torre contra ápice estrecho
        if best_pt == chess.ROOK and apex_w < 0.28:
            if asym >= 0.16:
                best_pt = chess.KNIGHT
            elif rel_width <= 0.70:
                best_pt = chess.PAWN
            else:
                best_pt = chess.BISHOP

        # Peón estándar (debe ser de baja altura rel_height <= 0.72; un alfil es esbelto y alto rel_height >= 0.75)
        if rel_width <= 0.66 and rel_height <= 0.72 and top_w <= 0.45 and best_pt not in (chess.KNIGHT, chess.KING):
            best_pt = chess.PAWN
            best_iou = max(best_iou, 0.85)

        # La evidencia visual no cambia por casilla; la legalidad se valida al reconstruir la posición.
        return best_pt, max(0.50, float(best_iou))

    @classmethod
    def classify_piece_type(cls, square_img: np.ndarray, color: chess.Color) -> chess.PieceType:
        """
        Clasifica el tipo de pieza (P, N, B, R, Q, K) combinando análisis morfológico
        de silueta unificada y matching por IoU con plantillas cburnett normalizadas.
        """
        pt, _ = cls.classify_piece_type_with_confidence(square_img, color)
        return pt

    @classmethod
    def get_piece_type_ranking(
        cls,
        square_img: np.ndarray,
        color: chess.Color,
        square_name: Optional[str] = None,
        *,
        raw: bool = False
    ) -> List[Tuple[chess.PieceType, float]]:
        """
        Retorna la lista de candidatos (PieceType, score) ordenados de mayor a menor confianza,
        permitiendo que el reconciliador y detector resuelvan piezas duplicadas sin forzar a reina.
        Con raw=True devuelve similitud visual medida, sin prioridades morfológicas.
        """
        if square_img is None or square_img.size == 0:
            return [(chess.PAWN, 0.0)]

        references = get_reference_ranking(square_img, color)
        if references:
            return [(piece.piece_type, score) for piece, score in references]

        gray = cv2.cvtColor(square_img, cv2.COLOR_BGR2GRAY) if len(square_img.shape) == 3 else square_img
        h, w = gray.shape[:2]
        if h < 8 or w < 8:
            return [(chess.PAWN, 0.0)]

        c_h, c_w = max(2, int(h * 0.15)), max(2, int(w * 0.15))
        corners = np.concatenate([
            gray[:c_h, :c_w].flatten(),
            gray[:c_h, -c_w:].flatten(),
            gray[-c_h:, :c_w].flatten(),
            gray[-c_h:, -c_w:].flatten()
        ])
        bg_val = float(np.median(corners))

        if color == chess.WHITE:
            if bg_val < 180.0:
                mask = ((gray > 165) | (gray < 75)).astype(np.uint8) * 255
            else:
                mask = ((gray < 75) | (gray > 235)).astype(np.uint8) * 255
        else:
            thresh_val = 140 if bg_val > 170 else 100
            mask = (gray < thresh_val).astype(np.uint8) * 255

        kernel = np.ones((3, 3), np.uint8)
        sq_sil = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(sq_sil)
        if num_labels <= 1:
            return [(chess.PAWN, 0.0)]

        areas = stats[1:, cv2.CC_STAT_AREA]
        largest_label = int(np.argmax(areas)) + 1
        main_sil = (labels == largest_label).astype(np.uint8) * 255
        if stats[largest_label, cv2.CC_STAT_HEIGHT] < h * 0.72:
            for label in range(1, num_labels):
                if (stats[label, cv2.CC_STAT_AREA] >= max(3, areas.max() * 0.025) and
                        abs(centroids[label, 0] - centroids[largest_label, 0]) <= w * 0.20):
                    main_sil[labels == label] = 255
        cnts, _ = cv2.findContours(main_sil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        filled = np.zeros_like(main_sil)
        if cnts:
            cv2.drawContours(filled, cnts, -1, 255, -1)
        else:
            filled = main_sil

        ys, xs = np.where(filled > 0)
        if len(ys) == 0:
            return [(chess.PAWN, 0.0)]

        crop = filled[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        sq_sil_32 = cv2.resize((crop > 0).astype(np.uint8) * 255, (32, 32), interpolation=cv2.INTER_NEAREST) > 0

        from chess_vision.vision.piece_templates import get_template_masks
        ious: Dict[chess.PieceType, float] = {}
        for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN, chess.KING]:
            sym = chess.piece_symbol(pt)
            sym = sym.upper() if color == chess.WHITE else sym.lower()
            t_masks = get_template_masks(sym)
            max_pt_iou = 0.0
            for t_mask in t_masks:
                inter = np.sum(sq_sil_32 & t_mask)
                union = np.sum(sq_sil_32 | t_mask)
                t_iou = inter / float(max(1, union))
                if t_iou > max_pt_iou:
                    max_pt_iou = t_iou
            ious[pt] = max_pt_iou

        if raw:
            return sorted(ious.items(), key=lambda item: item[1], reverse=True)

        best_pt, best_conf = cls.classify_piece_type_with_confidence(square_img, color, square_name)
        ranking = [(best_pt, best_conf)]
        for pt, iou_val in sorted(ious.items(), key=lambda x: x[1], reverse=True):
            if pt != best_pt:
                ranking.append((pt, float(iou_val)))
        return ranking

    @classmethod
    def get_king_similarity(
        cls,
        square_img: np.ndarray,
        color: chess.Color,
        square_name: Optional[str] = None
    ) -> float:
        """
        Retorna la similitud o IoU (0.0 a 1.0) de la imagen de una casilla frente a la plantilla del Rey.
        """
        if square_img is None or square_img.size == 0:
            return 0.0
        ranking = cls.get_piece_type_ranking(square_img, color, square_name, raw=True)
        for pt, score in ranking:
            if pt == chess.KING:
                return float(score)
        return 0.0

    @classmethod
    def get_second_best_piece_type(
        cls,
        square_img: np.ndarray,
        color: chess.Color,
        exclude: Optional[set] = None,
        square_name: Optional[str] = None
    ) -> chess.PieceType:
        """
        Retorna la mejor alternativa morfológica real excluyendo los tipos en `exclude`.
        """
        if exclude is None:
            exclude = set()
        ranking = cls.get_piece_type_ranking(square_img, color, square_name)
        for pt, _ in ranking:
            if pt not in exclude:
                return pt
        for pt in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.PAWN]:
            if pt not in exclude:
                return pt
        return chess.PAWN

    @classmethod
    def recognize_square(cls, square_img: np.ndarray, is_light_square: Optional[bool] = None, theme: str = "green") -> Optional[chess.Piece]:
        """
        Reconoce si hay una pieza en la casilla y retorna un chess.Piece, o None si está vacía.
        """
        if not cls.is_square_occupied(square_img):
            return None

        color = cls.get_piece_color(square_img, is_light_square=is_light_square, theme=theme)
        if color is None:
            return None

        piece_type = cls.classify_piece_type(square_img, color)
        return chess.Piece(piece_type, color)

    @classmethod
    def get_square_difference_map(
        cls,
        prev_squares: Dict[str, np.ndarray],
        curr_squares: Dict[str, np.ndarray]
    ) -> Dict[str, float]:
        """
        Calcula la magnitud de diferencia absoluta normalizada (0.0 a 1.0)
        para cada una de las 64 casillas entre dos fotogramas consecutivos.
        """
        diff_map: Dict[str, float] = {}

        for sq_name, curr_crop in curr_squares.items():
            prev_crop = prev_squares.get(sq_name)
            if prev_crop is None:
                continue

            if prev_crop.shape != curr_crop.shape:
                curr_crop_resized = cv2.resize(curr_crop, (prev_crop.shape[1], prev_crop.shape[0]))
            else:
                curr_crop_resized = curr_crop

            gray_prev = cv2.cvtColor(prev_crop, cv2.COLOR_BGR2GRAY) if len(prev_crop.shape) == 3 else prev_crop
            gray_curr = cv2.cvtColor(curr_crop_resized, cv2.COLOR_BGR2GRAY) if len(curr_crop_resized.shape) == 3 else curr_crop_resized

            diff = cv2.absdiff(gray_prev, gray_curr)
            diff_score = float(np.mean(diff)) / 255.0
            diff_map[sq_name] = diff_score

        return diff_map

    @classmethod
    def detect_square_differences(
        cls,
        prev_squares: Dict[str, np.ndarray],
        curr_squares: Dict[str, np.ndarray],
        threshold: float = 0.04
    ) -> List[str]:
        """
        Compara las 64 casillas entre dos fotogramas consecutivos y retorna
        la lista de nombres de casillas que han cambiado significativamente.
        Esto permite detectar movimientos en tiempo real (<2ms).
        """
        diff_map = cls.get_square_difference_map(prev_squares, curr_squares)
        changed = [(sq, score) for sq, score in diff_map.items() if score > threshold]
        changed.sort(key=lambda x: x[1], reverse=True)
        return [sq for sq, _ in changed]

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
        junto a su índice de confianza (0.0 a 1.0).
        """
        from chess_vision.vision.board_detector import BoardDetector
        return BoardDetector.scan_full_board_fen(
            image=image,
            orientation=orientation,
            margin_pct=margin_pct,
            inset_pct=inset_pct,
            mental_map=mental_map
        )
