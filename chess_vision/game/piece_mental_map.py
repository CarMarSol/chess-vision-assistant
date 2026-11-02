"""
Mapa mental y base de datos persistente de piezas de ajedrez para Chess Vision Assistant.
Rastrea la identidad única e invariante de cada pieza (32 piezas iniciales) a lo largo
de toda la partida, independientemente de fluctuaciones o ruidos del OCR visual.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
import chess


def is_dark_square(sq: chess.Square) -> bool:
    """Retorna True si la casilla es de color oscuro, False si es clara."""
    return (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 0


PIECE_NAMES_ES: Dict[chess.PieceType, str] = {
    chess.PAWN: "Peón",
    chess.KNIGHT: "Caballo",
    chess.BISHOP: "Alfil",
    chess.ROOK: "Torre",
    chess.QUEEN: "Dama",
    chess.KING: "Rey"
}


@dataclass
class PieceRecord:
    """Registro inmutable de la identidad de una pieza física de ajedrez."""
    piece_id: str                          # Identificador único (ej. 'w_N_b1', 'w_B_c1', 'w_K_e1')
    piece_type: chess.PieceType            # Tipo de pieza (K, Q, R, B, N, P)
    color: chess.Color                     # chess.WHITE o chess.BLACK
    square: Optional[chess.Square]         # Casilla actual (0..63) o None si capturada
    original_square: chess.Square          # Casilla inicial de colocación
    bishop_square_color: Optional[bool] = None  # Para alfiles: True = casilla oscura, False = casilla clara
    promoted: bool = False                 # Si fue promovido a partir de peón
    move_count: int = 0                    # Veces que se ha movido esta pieza

    @property
    def is_alive(self) -> bool:
        return self.square is not None

    @property
    def name_es(self) -> str:
        return PIECE_NAMES_ES.get(self.piece_type, "Pieza")

    def as_chess_piece(self) -> chess.Piece:
        return chess.Piece(self.piece_type, self.color)


class PieceMentalMap:
    """
    Base de datos / mapa mental en memoria de las 32 piezas de ajedrez.
    Mantiene la certeza de la identidad de cada pieza entre jugadas:
    - Una pieza que era Caballo en casilla origen SIGUE SIENDO CABALLO en destino con 100% de certeza.
    - Las capturas eliminan del tablero la pieza capturada.
    - Los enroques mueven coherentemente Rey y Torre.
    - Las promociones actualizan el tipo del peón promovido.
    - Sirve como oráculo de desambiguación para el OCR óptico (scan_full_board_fen).
    """

    def __init__(self, fen: Optional[str] = None):
        self._pieces: Dict[str, PieceRecord] = {}
        self._square_to_id: Dict[chess.Square, str] = {}
        self._captured_pieces: List[PieceRecord] = []
        self._piece_counter: int = 0
        self.load_from_fen(fen or chess.STARTING_FEN)

    @property
    def pieces(self) -> Dict[str, PieceRecord]:
        return self._pieces

    def reset(self, fen: Optional[str] = None) -> None:
        """Reinicia el mapa mental a la posición estándar o a la dada por FEN."""
        self.load_from_fen(fen or chess.STARTING_FEN)

    def load_from_fen(self, fen: str) -> None:
        """Inicializa las identidades de las piezas a partir de una cadena FEN."""
        self._pieces.clear()
        self._square_to_id.clear()
        self._captured_pieces.clear()
        self._piece_counter = 0

        board = chess.Board(fen)

        # Si es la posición inicial canónica, asignar IDs semánticos exactos
        is_starting = (board.fen() == chess.STARTING_FEN)

        for sq in chess.SQUARES:
            p = board.piece_at(sq)
            if p is not None:
                sq_name = chess.square_name(sq)
                color_prefix = "w" if p.color == chess.WHITE else "b"
                type_symbol = p.symbol().upper()

                if is_starting:
                    pid = f"{color_prefix}_{type_symbol}_{sq_name}"
                else:
                    self._piece_counter += 1
                    pid = f"{color_prefix}_{type_symbol}_{sq_name}_{self._piece_counter}"

                bishop_sq_color = None
                if p.piece_type == chess.BISHOP:
                    bishop_sq_color = is_dark_square(sq)

                rec = PieceRecord(
                    piece_id=pid,
                    piece_type=p.piece_type,
                    color=p.color,
                    square=sq,
                    original_square=sq,
                    bishop_square_color=bishop_sq_color,
                    promoted=False,
                    move_count=0
                )
                self._pieces[pid] = rec
                self._square_to_id[sq] = pid

    def piece_at(self, square: chess.Square) -> Optional[chess.Piece]:
        """Retorna la pieza (chess.Piece) situada en la casilla según el mapa mental."""
        pid = self._square_to_id.get(square)
        if pid and pid in self._pieces:
            rec = self._pieces[pid]
            if rec.is_alive:
                return rec.as_chess_piece()
        return None

    def piece_type_at(self, square: chess.Square) -> Optional[chess.PieceType]:
        """Retorna el tipo de pieza (chess.PieceType) en la casilla, o None si está vacía."""
        p = self.piece_at(square)
        return p.piece_type if p else None

    def color_at(self, square: chess.Square) -> Optional[chess.Color]:
        """Retorna el bando de la pieza en la casilla, o None si está vacía."""
        p = self.piece_at(square)
        return p.color if p else None

    def piece_record_at(self, square: chess.Square) -> Optional[PieceRecord]:
        """Retorna el registro completo de la pieza en la casilla especificada."""
        pid = self._square_to_id.get(square)
        if pid and pid in self._pieces:
            return self._pieces[pid]
        return None

    def get_piece_name_at(self, square: chess.Square) -> Optional[str]:
        """Retorna el nombre en español de la pieza en la casilla (ej. 'Caballo', 'Peón')."""
        rec = self.piece_record_at(square)
        return rec.name_es if rec else None

    def get_status_summary(self) -> str:
        """
        Retorna un resumen de las piezas vivas en el mapa mental.
        Ej: '32 piezas activas' si son 32, o '16 blancas / 15 negras (31 piezas)'.
        """
        white_pieces = self.get_surviving_pieces(chess.WHITE)
        black_pieces = self.get_surviving_pieces(chess.BLACK)
        total = len(white_pieces) + len(black_pieces)
        if total == 32:
            return "32 piezas activas"
        return f"{len(white_pieces)} blancas / {len(black_pieces)} negras ({total} piezas)"

    def get_piece_by_id(self, piece_id: str) -> Optional[PieceRecord]:
        return self._pieces.get(piece_id)

    def get_surviving_pieces(self, color: Optional[chess.Color] = None) -> List[PieceRecord]:
        """Retorna todas las piezas actualmente activas sobre el tablero."""
        res: List[PieceRecord] = []
        for rec in self._pieces.values():
            if rec.is_alive:
                if color is None or rec.color == color:
                    res.append(rec)
        return res

    def get_captured_pieces(self, color: Optional[chess.Color] = None) -> List[PieceRecord]:
        """Retorna todas las piezas que han sido capturadas."""
        if color is None:
            return list(self._captured_pieces)
        return [r for r in self._captured_pieces if r.color == color]

    def get_surviving_counts(self, color: chess.Color) -> Dict[chess.PieceType, int]:
        """Retorna el conteo de piezas vivas agrupadas por tipo para un color."""
        counts: Dict[chess.PieceType, int] = {
            chess.PAWN: 0,
            chess.KNIGHT: 0,
            chess.BISHOP: 0,
            chess.ROOK: 0,
            chess.QUEEN: 0,
            chess.KING: 0
        }
        for rec in self.get_surviving_pieces(color):
            counts[rec.piece_type] = counts.get(rec.piece_type, 0) + 1
        return counts

    def get_surviving_bishops_by_square_color(self, color: chess.Color) -> Dict[str, int]:
        """
        Retorna cuántos alfiles vivos existen de casillas oscuras ('dark')
        y de casillas claras ('light').
        """
        counts = {"dark": 0, "light": 0}
        for rec in self.get_surviving_pieces(color):
            if rec.piece_type == chess.BISHOP:
                if rec.bishop_square_color is True:
                    counts["dark"] += 1
                elif rec.bishop_square_color is False:
                    counts["light"] += 1
                elif rec.square is not None:
                    # Inferencia por casilla actual si no estaba grabado
                    if is_dark_square(rec.square):
                        counts["dark"] += 1
                    else:
                        counts["light"] += 1
        return counts

    def apply_move(self, move: chess.Move, board_before: Optional[chess.Board] = None) -> None:
        """
        Aplica un movimiento al mapa mental:
        - Mueve la pieza de origen a destino conservando INVARIABLE su identidad (Caballo -> Caballo).
        - En caso de captura, registra la pieza enemiga eliminada.
        - En caso de enroque, traslada tanto al Rey como a la Torre correspondiente.
        - En caso de en passant, elimina el peón capturado en la fila adyacente.
        - En caso de promoción, transforma el peón a la pieza elegida (Dama por defecto).
        - Mantiene sincronizada la base de datos sin duplicidades ni piezas fantasmas.
        """
        from_sq = move.from_square
        to_sq = move.to_square

        if from_sq == to_sq:
            return

        pid = self._square_to_id.get(from_sq)
        if pid is None:
            # Buscar si alguna pieza viva tiene square == from_sq
            for p_rec in self._pieces.values():
                if p_rec.is_alive and p_rec.square == from_sq:
                    pid = p_rec.piece_id
                    self._square_to_id[from_sq] = pid
                    break

        if pid is None and board_before is not None:
            # Recuperación de contingencia si no estaba indexado
            p = board_before.piece_at(from_sq)
            if p is not None:
                self._piece_counter += 1
                pid = f"{'w' if p.color == chess.WHITE else 'b'}_{p.symbol().upper()}_{chess.square_name(from_sq)}_{self._piece_counter}"
                rec = PieceRecord(
                    piece_id=pid,
                    piece_type=p.piece_type,
                    color=p.color,
                    square=from_sq,
                    original_square=from_sq,
                    bishop_square_color=is_dark_square(from_sq) if p.piece_type == chess.BISHOP else None
                )
                self._pieces[pid] = rec
                self._square_to_id[from_sq] = pid

        if pid is None or pid not in self._pieces:
            return

        moving_rec = self._pieces[pid]

        # 1. Comprobar Enroque
        if moving_rec.piece_type == chess.KING:
            diff_file = chess.square_file(to_sq) - chess.square_file(from_sq)
            if abs(diff_file) > 1:
                # El Rey se enroca: determinar casillas de la torre
                rook_from = None
                rook_to = None
                if to_sq == chess.G1:
                    rook_from, rook_to = chess.H1, chess.F1
                elif to_sq == chess.C1:
                    rook_from, rook_to = chess.A1, chess.D1
                elif to_sq == chess.G8:
                    rook_from, rook_to = chess.H8, chess.F8
                elif to_sq == chess.C8:
                    rook_from, rook_to = chess.A8, chess.D8

                if rook_from is not None and rook_from in self._square_to_id:
                    r_pid = self._square_to_id[rook_from]
                    r_rec = self._pieces[r_pid]
                    del self._square_to_id[rook_from]
                    r_rec.square = rook_to
                    r_rec.move_count += 1
                    self._square_to_id[rook_to] = r_pid

        # 2. Comprobar Captura normal en casilla de destino
        captured_pid = self._square_to_id.get(to_sq)
        if captured_pid and captured_pid in self._pieces and captured_pid != pid:
            cap_rec = self._pieces[captured_pid]
            cap_rec.square = None
            if cap_rec not in self._captured_pieces:
                self._captured_pieces.append(cap_rec)
            del self._square_to_id[to_sq]

        # 3. Comprobar Captura al paso (En Passant)
        if moving_rec.piece_type == chess.PAWN and chess.square_file(from_sq) != chess.square_file(to_sq) and not captured_pid:
            ep_captured_sq = chess.square(chess.square_file(to_sq), chess.square_rank(from_sq))
            ep_pid = self._square_to_id.get(ep_captured_sq)
            if ep_pid and ep_pid in self._pieces:
                ep_rec = self._pieces[ep_pid]
                ep_rec.square = None
                if ep_rec not in self._captured_pieces:
                    self._captured_pieces.append(ep_rec)
                if ep_captured_sq in self._square_to_id:
                    del self._square_to_id[ep_captured_sq]

        # 4. Comprobar Promoción
        if moving_rec.piece_type == chess.PAWN and (chess.square_rank(to_sq) in (0, 7) or move.promotion is not None):
            promo_type = move.promotion or chess.QUEEN
            moving_rec.piece_type = promo_type
            moving_rec.promoted = True

        # 5. Traslado físico de la pieza de from_sq a to_sq
        if from_sq in self._square_to_id:
            del self._square_to_id[from_sq]

        moving_rec.square = to_sq
        moving_rec.move_count += 1
        self._square_to_id[to_sq] = pid

        # 6. Limpieza preventiva de inconsistencias: ninguna otra pieza debe quedar en to_sq
        for other_pid, other_rec in self._pieces.items():
            if other_pid != pid and other_rec.square == to_sq:
                other_rec.square = None
                if other_rec not in self._captured_pieces:
                    self._captured_pieces.append(other_rec)

    def disambiguate_board_pieces(
        self,
        board_pieces: Dict[chess.Square, Tuple[chess.Piece, float]]
    ) -> Dict[chess.Square, Tuple[chess.Piece, float]]:
        """
        Corrige y desambigua piezas clasificadas por visión óptica utilizando el mapa mental:
        0. Memoria posicional absoluta: si una pieza conocida está registrada en el mapa mental
           en la casilla sq, su identidad física en la base de datos PREVALECE sobre errores ópticos.
        1. Regla inviolable de Caballos: MÁXIMO 2 Caballos por bando (salvo peones promovidos).
           Cualquier caballo en exceso que no corresponda a los caballos registrados se reclasifica
           a su tipo real (Alfil si falta alfil en la casilla / Peón si está en fila de peones).
        2. Regla de Alfiles: Máximo 2 Alfiles por bando (1 de casillas claras, 1 de casillas oscuras).
        3. Regla de Damas: Máximo 1 Dama por bando (en apertura/medio juego).
        4. Regla de Torres: Máximo 2 Torres por bando (salvo promociones).
        5. Exactamente 1 Rey por bando.
        """
        corrected = dict(board_pieces)

        for color in (chess.WHITE, chess.BLACK):
            surviving = self.get_surviving_pieces(color)
            surv_counts = self.get_surviving_counts(color) if surviving else {
                chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1, chess.KING: 1
            }
            surv_bishops = self.get_surviving_bishops_by_square_color(color) if surviving else {"dark": 1, "light": 1}

            # Paso 0: Memoria posicional de casillas conocidas no alteradas
            # Si una pieza conocida no se ha movido o está registrada en el mapa mental,
            # su identidad física prevalece sobre fluctuaciones o errores morfológicos del OCR.
            for sq, (p_det, conf_det) in list(corrected.items()):
                if p_det.color == color:
                    p_mem = self.piece_at(sq)
                    if p_mem is not None and p_mem.color == color:
                        if p_det.piece_type != p_mem.piece_type:
                            corrected[sq] = (chess.Piece(p_mem.piece_type, color), max(conf_det, 0.95))

            max_knights = min(2, surv_counts.get(chess.KNIGHT, 2)) if surv_counts.get(chess.KNIGHT, 2) > 0 else 2
            surv_bishops_count = min(2, surv_counts.get(chess.BISHOP, 2))

            # Paso 1: Comprobar color de casillas de alfiles (compatibilidad topológica)
            for sq in list(corrected.keys()):
                piece, conf = corrected[sq]
                if piece.color == color and piece.piece_type == chess.BISHOP:
                    is_dark = is_dark_square(sq)
                    if is_dark and surv_bishops.get("dark", 1) == 0:
                        # Alfil falso en casilla oscura -> reclasificar a Caballo si hay cupo, sino Peón
                        curr_k = [s for s, (p, _) in corrected.items() if p.color == color and p.piece_type == chess.KNIGHT]
                        if len(curr_k) < max_knights:
                            corrected[sq] = (chess.Piece(chess.KNIGHT, color), conf)
                        elif chess.square_rank(sq) in (1, 2, 3, 4, 5, 6):
                            corrected[sq] = (chess.Piece(chess.PAWN, color), conf)
                    elif (not is_dark) and surv_bishops.get("light", 1) == 0:
                        # Alfil falso en casilla clara -> reclasificar a Caballo si hay cupo, sino Peón
                        curr_k = [s for s, (p, _) in corrected.items() if p.color == color and p.piece_type == chess.KNIGHT]
                        if len(curr_k) < max_knights:
                            corrected[sq] = (chess.Piece(chess.KNIGHT, color), conf)
                        elif chess.square_rank(sq) in (1, 2, 3, 4, 5, 6):
                            corrected[sq] = (chess.Piece(chess.PAWN, color), conf)

            # Paso 2: REGLA INVIOLABLE DE CABALLOS (Máximo 2 Caballos por bando)
            det_knights = [sq for sq, (p, _) in corrected.items() if p.color == color and p.piece_type == chess.KNIGHT]
            if len(det_knights) > max_knights:
                # Separar caballos confirmados por el mapa mental de caballos en exceso
                legit_knights = []
                excess_knights = []
                for k_sq in det_knights:
                    rec = self.piece_record_at(k_sq)
                    if rec and rec.color == color and rec.piece_type == chess.KNIGHT:
                        legit_knights.append(k_sq)
                    else:
                        excess_knights.append(k_sq)

                if len(legit_knights) > max_knights:
                    excess_knights.extend(legit_knights[max_knights:])
                    legit_knights = legit_knights[:max_knights]

                needed = max_knights - len(legit_knights)
                if needed > 0 and excess_knights:
                    canonical_sqs = {chess.B1, chess.G1, chess.F3, chess.C3} if color == chess.WHITE else {chess.B8, chess.G8, chess.F6, chess.C6}
                    excess_knights.sort(key=lambda s: (s in canonical_sqs, corrected[s][1]), reverse=True)
                    legit_knights.extend(excess_knights[:needed])
                    excess_knights = excess_knights[needed:]

                # Ordenar caballos en exceso para priorizar casillas naturales de desarrollo de alfil (ej. e7/d7/g7)
                canonical_bishop_sqs = {chess.E7, chess.D7, chess.G7} if color == chess.BLACK else {chess.E2, chess.D2, chess.G2}
                excess_knights.sort(key=lambda s: (s in canonical_bishop_sqs, corrected[s][1]), reverse=True)

                # Reclasificar rigurosamente cada caballo en exceso
                for fix_sq in excess_knights:
                    p, conf = corrected[fix_sq]
                    # 2.1 Si el mapa mental conocía otra pieza en esa casilla
                    rec = self.piece_record_at(fix_sq)
                    if rec and rec.color == color and rec.piece_type != chess.KNIGHT:
                        corrected[fix_sq] = (chess.Piece(rec.piece_type, color), max(conf, 0.95))
                        continue

                    # 2.2 Si falta un Alfil en el color de casilla correspondiente
                    is_dark = is_dark_square(fix_sq)
                    det_bishops = [s for s, (bp, _) in corrected.items() if bp.color == color and bp.piece_type == chess.BISHOP]
                    bishops_on_color = [s for s in det_bishops if is_dark_square(s) == is_dark]
                    surv_bishops_color = surv_bishops.get("dark" if is_dark else "light", 1)

                    if len(bishops_on_color) < surv_bishops_color:
                        corrected[fix_sq] = (chess.Piece(chess.BISHOP, color), conf)
                        continue

                    # 2.3 Si está en filas de peones (1 a 6)
                    rank = chess.square_rank(fix_sq)
                    if rank in (1, 2, 3, 4, 5, 6):
                        corrected[fix_sq] = (chess.Piece(chess.PAWN, color), conf)
                        continue

                    # 2.4 Si está en fila 0 o 7, comprobar Torre
                    det_rooks = [s for s, (rp, _) in corrected.items() if rp.color == color and rp.piece_type == chess.ROOK]
                    if len(det_rooks) < surv_counts.get(chess.ROOK, 2):
                        corrected[fix_sq] = (chess.Piece(chess.ROOK, color), conf)
                    else:
                        corrected[fix_sq] = (chess.Piece(chess.BISHOP, color), conf)

            # Paso 3: REGLA DE ALFILES (Máximo 2 Alfiles: 1 oscuro, 1 claro)
            det_bishops = [sq for sq, (p, _) in corrected.items() if p.color == color and p.piece_type == chess.BISHOP]
            for sq_color_name, is_dark_val in (("dark", True), ("light", False)):
                bishops_color = [s for s in det_bishops if is_dark_square(s) == is_dark_val]
                max_bishops_color = surv_bishops.get(sq_color_name, 1)
                if len(bishops_color) > max_bishops_color:
                    bishops_color.sort(
                        key=lambda s: (
                            self.piece_record_at(s) is not None and self.piece_record_at(s).piece_type == chess.BISHOP,
                            corrected[s][1]
                        ),
                        reverse=True
                    )
                    excess_b = bishops_color[max_bishops_color:]
                    for b_fix in excess_b:
                        p, conf = corrected[b_fix]
                        curr_k = [s for s, (kp, _) in corrected.items() if kp.color == color and kp.piece_type == chess.KNIGHT]
                        if len(curr_k) < max_knights:
                            corrected[b_fix] = (chess.Piece(chess.KNIGHT, color), conf)
                        elif chess.square_rank(b_fix) in (1, 2, 3, 4, 5, 6):
                            corrected[b_fix] = (chess.Piece(chess.PAWN, color), conf)
                        else:
                            corrected[b_fix] = (chess.Piece(chess.ROOK, color), conf)

            # Paso 4: REGLA DE DAMAS (Máximo 1 Dama por bando en apertura / medio juego)
            det_queens = [sq for sq, (p, _) in corrected.items() if p.color == color and p.piece_type == chess.QUEEN]
            surv_queens_count = surv_counts.get(chess.QUEEN, 1)
            if len(det_queens) > max(1, surv_queens_count):
                promo_rank = 7 if color == chess.WHITE else 0
                has_promo = any(chess.square_rank(sq) == promo_rank for sq in det_queens)
                if not has_promo:
                    home_sq = chess.D1 if color == chess.WHITE else chess.D8
                    det_queens.sort(
                        key=lambda s: (
                            self.piece_record_at(s) is not None and self.piece_record_at(s).piece_type == chess.QUEEN,
                            s == home_sq,
                            corrected[s][1]
                        ),
                        reverse=True
                    )
                    for q_fix in det_queens[1:]:
                        p, conf = corrected[q_fix]
                        curr_b = [s for s, (bp, _) in corrected.items() if bp.color == color and bp.piece_type == chess.BISHOP]
                        curr_k = [s for s, (kp, _) in corrected.items() if kp.color == color and kp.piece_type == chess.KNIGHT]
                        if len(curr_b) < surv_bishops_count:
                            corrected[q_fix] = (chess.Piece(chess.BISHOP, color), conf * 0.9)
                        elif len(curr_k) < max_knights:
                            corrected[q_fix] = (chess.Piece(chess.KNIGHT, color), conf * 0.9)
                        elif chess.square_rank(q_fix) in (1, 2, 3, 4, 5, 6):
                            corrected[q_fix] = (chess.Piece(chess.PAWN, color), conf * 0.9)
                        else:
                            corrected[q_fix] = (chess.Piece(chess.ROOK, color), conf * 0.9)

            # Paso 5: REGLA DE TORRES (Máximo 2 Torres por bando)
            det_rooks = [sq for sq, (p, _) in corrected.items() if p.color == color and p.piece_type == chess.ROOK]
            surv_rooks_count = surv_counts.get(chess.ROOK, 2)
            if len(det_rooks) > max(2, surv_rooks_count):
                det_rooks.sort(
                    key=lambda s: (
                        self.piece_record_at(s) is not None and self.piece_record_at(s).piece_type == chess.ROOK,
                        chess.square_rank(s) in (0, 7),
                        corrected[s][1]
                    ),
                    reverse=True
                )
                for r_fix in det_rooks[2:]:
                    p, conf = corrected[r_fix]
                    if chess.square_rank(r_fix) in (1, 2, 3, 4, 5, 6):
                        corrected[r_fix] = (chess.Piece(chess.PAWN, color), conf * 0.9)
                    else:
                        corrected[r_fix] = (chess.Piece(chess.BISHOP, color), conf * 0.9)

        # Regla de oro de fila base (Rango 1 = Blancas, Rango 8 = Negras):
        # En la posición inicial o durante la apertura, ninguna pieza de la fila 1 (a1-h1)
        # puede ser clasificada como pieza Negra salvo que el mapa mental registre que una pieza negra llegó allí.
        # Y ninguna pieza de la fila 8 (a8-h8) puede ser clasificada como Blanca salvo que una pieza blanca llegase allí.
        for sq, (p_det, conf_det) in list(corrected.items()):
            r = chess.square_rank(sq)
            p_mem = self.piece_at(sq)
            if r == 0:  # Fila 1 (a1-h1)
                if p_det.color == chess.BLACK:
                    if p_mem is None or p_mem.color == chess.WHITE:
                        corrected[sq] = (chess.Piece(p_det.piece_type, chess.WHITE), max(conf_det, 0.95))
            elif r == 7:  # Fila 8 (a8-h8)
                if p_det.color == chess.WHITE:
                    if p_mem is None or p_mem.color == chess.BLACK:
                        corrected[sq] = (chess.Piece(p_det.piece_type, chess.BLACK), max(conf_det, 0.95))

        return corrected

    def to_board(self) -> chess.Board:
        """Construye un objeto chess.Board reflejando exactamente las posiciones del mapa mental."""
        board = chess.Board(None)  # Tablero vacío
        for sq, pid in self._square_to_id.items():
            rec = self._pieces.get(pid)
            if rec and rec.is_alive:
                board.set_piece_at(sq, rec.as_chess_piece())
        return board
