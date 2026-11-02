"""
Reconciliador unificado de movimientos y validador de correspondencia física.
Garantiza coherencia estricta entre la visión por computador y las reglas de ajedrez FIDE.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Set, TYPE_CHECKING
import numpy as np
import chess

from chess_vision.vision.piece_classifier import PieceClassifier

if TYPE_CHECKING:
    from chess_vision.game.piece_mental_map import PieceMentalMap


class ReconcileStatus(Enum):
    CONFIRMED = "confirmed"       # Movimiento unívoco y confirmado legalmente
    UNCERTAIN = "uncertain"       # Ambigüedad o baja confianza: esperar al siguiente frame
    NO_MOVE = "no_move"           # No hay cambios significativos en el tablero
    DESYNC = "desync"             # Cambio visual no reproducible por ninguna jugada legal


@dataclass
class SquareObservation:
    """Observación física y morfológica de una casilla individual del tablero."""
    square: chess.Square
    square_name: str
    is_occupied: bool
    color: Optional[chess.Color]
    piece_type: Optional[chess.PieceType]
    confidence: float = 1.0
    is_highlighted: bool = False
    diff_score: float = 0.0


@dataclass
class ReconcileResult:
    """Resultado del proceso de reconciliación de un fotograma."""
    status: ReconcileStatus
    move: Optional[chess.Move] = None
    moves_chain: Optional[List[chess.Move]] = None
    score: float = 0.0
    confidence: float = 0.0
    explanation: str = ""


class MoveReconciler:
    """
    Motor centralizado de detección y validación de movimientos para Chess Vision Assistant.
    """

    @classmethod
    def build_observations(
        cls,
        current_squares: Dict[str, np.ndarray],
        prev_squares: Optional[Dict[str, np.ndarray]] = None,
        hl_squares: Optional[List[str]] = None,
        diff_map: Optional[Dict[str, float]] = None
    ) -> Dict[chess.Square, SquareObservation]:
        """
        Construye el mapa de observaciones de las 64 casillas examinando ocupación,
        color, tipo de pieza morfológico y resaltados.
        """
        hl_set = set(sq.lower() for sq in (hl_squares or []))
        if diff_map is None and prev_squares:
            diff_map = PieceClassifier.get_square_difference_map(prev_squares, current_squares)
        diff_map = diff_map or {}

        observations: Dict[chess.Square, SquareObservation] = {}

        for sq in chess.SQUARES:
            sq_name = chess.square_name(sq)
            img = current_squares.get(sq_name)
            if img is None or img.size == 0:
                observations[sq] = SquareObservation(
                    square=sq,
                    square_name=sq_name,
                    is_occupied=False,
                    color=None,
                    piece_type=None,
                    confidence=0.0,
                    is_highlighted=(sq_name in hl_set),
                    diff_score=diff_map.get(sq_name, 0.0)
                )
                continue

            is_occ = PieceClassifier.is_square_occupied(img)
            is_hl = (sq_name in hl_set) or PieceClassifier.is_square_highlighted(img)
            diff = diff_map.get(sq_name, 0.0)

            color = None
            pt = None
            conf = 1.0

            if is_occ:
                color = PieceClassifier.get_piece_color(img, square_name=sq_name)
                if color is not None:
                    if hasattr(PieceClassifier, "classify_piece_type_with_confidence"):
                        pt, conf = PieceClassifier.classify_piece_type_with_confidence(img, color, sq_name)
                    else:
                        pt = PieceClassifier.classify_piece_type(img, color)
                        conf = 0.85

            observations[sq] = SquareObservation(
                square=sq,
                square_name=sq_name,
                is_occupied=is_occ,
                color=color,
                piece_type=pt,
                confidence=conf,
                is_highlighted=is_hl,
                diff_score=diff
            )

        return observations

    @classmethod
    def get_castling_rook_squares(cls, move: chess.Move) -> Tuple[str, str]:
        """Retorna (origen, destino) de la torre para un enroque."""
        if move == chess.Move.from_uci("e1g1"):
            return "h1", "f1"
        elif move == chess.Move.from_uci("e1c1"):
            return "a1", "d1"
        elif move == chess.Move.from_uci("e8g8"):
            return "h8", "f8"
        elif move == chess.Move.from_uci("e8c8"):
            return "a8", "d8"
        return "", ""

    @classmethod
    def reconcile(
        cls,
        board: chess.Board,
        observed_squares: Dict[chess.Square, SquareObservation],
        hl_squares: Optional[List[str]] = None,
        diff_map: Optional[Dict[str, float]] = None,
        mental_map: Optional[PieceMentalMap] = None
    ) -> ReconcileResult:
        """
        Evalúa de forma exhaustiva las jugadas legales del tablero contra las observaciones físicas.
        La identidad inmutable de cada pieza proviene del mapa mental (PieceMentalMap).
        El OCR visual sólo se utiliza para detectar cambios de ocupación espacial y casillas resaltadas.
        Si existe ambigüedad o movimiento en progreso, devuelve ReconcileStatus.UNCERTAIN.
        """
        hl_set = set(sq.lower() for sq in (hl_squares or []))
        diff_map = diff_map or {}
        max_diff = max((obs.diff_score for obs in observed_squares.values()), default=0.0)

        # 1. Regla de oro de inicio: STARTING_FEN con filas 3 a 6 vacías
        if board.fen() == chess.STARTING_FEN:
            ranks_empty = True
            for f in range(8):
                for r in (2, 3, 4, 5):  # filas 3, 4, 5, 6
                    sq = chess.square(f, r)
                    if observed_squares.get(sq) and observed_squares[sq].is_occupied:
                        ranks_empty = False
                        break
                if not ranks_empty:
                    break
            if ranks_empty and not hl_set:
                return ReconcileResult(status=ReconcileStatus.NO_MOVE, explanation="Posición inicial sin comenzar")

        turn = board.turn

        # 2. Comprobar enroques por el desplazamiento físico del Rey.
        for legal_mv in board.legal_moves:
            if board.is_castling(legal_mv):
                from_sq = legal_mv.from_square
                to_sq = legal_mv.to_square
                from_name = chess.square_name(from_sq)
                to_name = chess.square_name(to_sq)

                r_from_name, r_to_name = cls.get_castling_rook_squares(legal_mv)
                r_from = chess.parse_square(r_from_name) if r_from_name else None
                r_to = chess.parse_square(r_to_name) if r_to_name else None

                obs_kfrom = observed_squares.get(from_sq)
                obs_kto = observed_squares.get(to_sq)
                obs_rfrom = observed_squares.get(r_from) if r_from is not None else None
                obs_rto = observed_squares.get(r_to) if r_to is not None else None

                if not obs_kfrom or not obs_kto:
                    continue

                # En Chess.com y Lichess, el resaltado de movimiento SOLO se aplica a la casilla de origen y destino del Rey
                kfrom_vacated = not obs_kfrom.is_occupied and obs_kfrom.confidence > 0.0
                kto_occupied = (obs_kto.is_occupied and obs_kto.color == turn and
                                obs_kto.confidence > 0.0)

                k_from_hl = obs_kfrom.is_highlighted or (from_name in hl_set)
                k_to_hl = obs_kto.is_highlighted or (to_name in hl_set)
                k_highlighted = k_from_hl or k_to_hl

                # Verificación de torre (permite sumar puntos extra, pero no bloquea si está en animación)
                rfrom_vacated = obs_rfrom is not None and (not obs_rfrom.is_occupied or obs_rfrom.color != turn)
                rto_occupied = obs_rto is not None and obs_rto.is_occupied and (obs_rto.color == turn or obs_rto.piece_type == chess.ROOK)
                # The legal king move is sufficient; the rook may still be animating.
                if kfrom_vacated and kto_occupied:
                    score = 50.0
                    if k_highlighted:
                        score += 20.0
                    if k_from_hl and k_to_hl:
                        score += 15.0
                    if rfrom_vacated:
                        score += 10.0
                    if rto_occupied:
                        score += 10.0

                    return ReconcileResult(
                        status=ReconcileStatus.CONFIRMED,
                        move=legal_mv,
                        score=score,
                        confidence=0.98,
                        explanation=f"Enroque {legal_mv} verificado físicamente"
                    )

        # Manual synchronization may omit pixel differences; first check the physical king move.
        if max_diff < 0.035 and not hl_set:
            return ReconcileResult(status=ReconcileStatus.NO_MOVE, explanation="Sin cambios visuales")

        # 3. Comprobar En Passant (3 casillas involucradas)
        for legal_mv in board.legal_moves:
            if board.is_en_passant(legal_mv):
                from_sq = legal_mv.from_square
                to_sq = legal_mv.to_square
                ep_sq = chess.square(chess.square_file(to_sq), chess.square_rank(from_sq))

                obs_from = observed_squares.get(from_sq)
                obs_to = observed_squares.get(to_sq)
                obs_ep = observed_squares.get(ep_sq)

                if obs_from and obs_to and obs_ep:
                    if (not obs_from.is_occupied and not obs_ep.is_occupied and obs_to.is_occupied):
                        if obs_to.color == turn:
                            return ReconcileResult(
                                status=ReconcileStatus.CONFIRMED,
                                move=legal_mv,
                                score=45.0,
                                confidence=0.95,
                                explanation="En passant verificado físicamente"
                            )

        # 4. Evaluación de jugadas regulares y capturas
        candidate_scores: List[Tuple[float, chess.Move, str]] = []

        for legal_mv in board.legal_moves:
            if board.is_castling(legal_mv) or board.is_en_passant(legal_mv):
                continue

            from_sq = legal_mv.from_square
            to_sq = legal_mv.to_square
            from_name = chess.square_name(from_sq)
            to_name = chess.square_name(to_sq)

            obs_from = observed_squares.get(from_sq)
            obs_to = observed_squares.get(to_sq)

            if not obs_from or not obs_to:
                continue

            # Condición física 1: origen DEBE estar vacío ahora. Si está ocupado, descartar 100% (-9999)
            if obs_from.is_occupied:
                continue

            # Condición física 2: destino DEBE estar ocupado ahora
            if not obs_to.is_occupied:
                continue

            # Condición física 3: color en destino debe coincidir con el turno que movió
            # (o estar ambas casillas explícitamente resaltadas)
            is_both_hl = (from_name in hl_set and to_name in hl_set)
            if obs_to.color != turn and not is_both_hl:
                continue

            # Puntuación basada en correspondencia física y evidencia
            score = 10.0
            if obs_to.color == turn:
                score += 15.0

            # Origen vacío y desocupado
            score += 15.0

            # Diferencia de píxeles
            score += (obs_from.diff_score + obs_to.diff_score) * 10.0

            # Bonificación determinante de casilla origen:
            # Si el origen quedó vacío y además tiene resaltado activo o cambio visual notable,
            # mientras que otras piezas legales candidatas siguen en su casilla original ocupada,
            # esta jugada es la única físicamente confirmada.
            if obs_from.is_highlighted:
                score += 30.0
            if from_name in hl_set:
                score += 25.0
            if obs_to.is_highlighted:
                score += 20.0
            if is_both_hl:
                score += 35.0

            # Verificación de tipo de pieza (identidad inmutable desde mapa mental / tablero)
            moving_pt = mental_map.piece_type_at(from_sq) if mental_map else board.piece_type_at(from_sq)
            if moving_pt == chess.QUEEN:
                # Movimientos de Dama: alta prioridad para saltos largos diagonales o rectos
                if not obs_from.is_occupied and obs_to.is_occupied and (obs_to.color == turn or is_both_hl):
                    score += 25.0
                    if obs_to.piece_type == chess.QUEEN:
                        score += 20.0
            elif legal_mv.promotion:
                if legal_mv.promotion == chess.QUEEN:
                    score += 12.0
                if obs_to.piece_type == legal_mv.promotion:
                    score += 8.0
            elif moving_pt and obs_to.piece_type:
                if obs_to.piece_type == moving_pt:
                    score += 10.0

            candidate_scores.append((score, legal_mv, f"{from_name}{to_name}"))

        if candidate_scores:
            candidate_scores.sort(key=lambda x: x[0], reverse=True)

            # Si hay casillas resaltadas y el mejor candidato está en ellas
            top_score, top_move, top_str = candidate_scores[0]

            # Detección de ambigüedad: si hay dos candidatos con puntuaciones casi idénticas
            if len(candidate_scores) > 1:
                second_score, second_move, second_str = candidate_scores[1]
                # Si la diferencia es mínima y ninguno tiene exclusividad por resaltado
                top_is_hl = {chess.square_name(top_move.from_square), chess.square_name(top_move.to_square)}.issubset(hl_set)
                sec_is_hl = {chess.square_name(second_move.from_square), chess.square_name(second_move.to_square)}.issubset(hl_set)

                if not top_is_hl and not sec_is_hl:
                    if abs(top_score - second_score) < 2.0:
                        return ReconcileResult(
                            status=ReconcileStatus.UNCERTAIN,
                            move=None,
                            score=top_score,
                            confidence=0.5,
                            explanation=f"Ambigüedad entre {top_move} ({top_score:.1f}) y {second_move} ({second_score:.1f})"
                        )

            return ReconcileResult(
                status=ReconcileStatus.CONFIRMED,
                move=top_move,
                score=top_score,
                confidence=0.92,
                explanation=f"Jugada {top_str} confirmada con puntuación {top_score:.1f}"
            )

        # 5. Búsqueda de reconciliación en cadena (Catch-up de 1-2 plies por lag)
        if len(hl_set) >= 2 or max_diff > 0.05:
            chain_result = cls._reconcile_chain_moves(board, observed_squares, hl_set, diff_map)
            if chain_result:
                return chain_result

        # 6. Si hubo cambios visuales notables pero ninguna jugada encaja
        if max_diff > 0.06 or len(hl_set) >= 2:
            return ReconcileResult(
                status=ReconcileStatus.DESYNC,
                explanation="Cambios visuales incompatibles con el árbol legal actual"
            )

        return ReconcileResult(status=ReconcileStatus.NO_MOVE, explanation="Sin jugada identificable")

    @classmethod
    def _reconcile_chain_moves(
        cls,
        board: chess.Board,
        observed: Dict[chess.Square, SquareObservation],
        hl_set: Set[str],
        diff_map: Dict[str, float]
    ) -> Optional[ReconcileResult]:
        """
        Busca reconciliación en cadena de 2 plies (m1 -> m2) si se perdió una semijugada previa.
        Solo se confirma si el estado final resultante coincide fuertemente con todo el tablero observado.
        """
        candidates: List[Tuple[float, List[chess.Move]]] = []

        for m1 in list(board.legal_moves):
            f1 = m1.from_square
            t1 = m1.to_square
            f1_name = chess.square_name(f1)
            t1_name = chess.square_name(t1)

            board.push(m1)
            try:
                for m2 in board.legal_moves:
                    f2 = m2.from_square
                    t2 = m2.to_square
                    f2_name = chess.square_name(f2)
                    t2_name = chess.square_name(t2)

                    obs_f2 = observed.get(f2)
                    obs_t2 = observed.get(t2)
                    if not obs_f2 or not obs_t2:
                        continue

                    # m2 físicamente: f2 vacío, t2 ocupado
                    if not obs_f2.is_occupied and obs_t2.is_occupied:
                        # m1 físicamente: f1 vacío (o reocupado por m2), t1 ocupado (salvo que m2 saliera de ahí)
                        obs_f1 = observed.get(f1)
                        obs_t1 = observed.get(t1)

                        f1_ok = (f1_name == t2_name) or (obs_f1 and not obs_f1.is_occupied)
                        t1_ok = (t1_name == f2_name) or (obs_t1 and obs_t1.is_occupied)

                        if f1_ok and t1_ok:
                            score = 20.0
                            is_m2_hl = {f2_name, t2_name}.issubset(hl_set)
                            if is_m2_hl:
                                score += 30.0
                            if obs_t2.color == board.turn:
                                score += 15.0

                            candidates.append((score, [m1, m2]))
            finally:
                board.pop()

        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_score, best_chain = candidates[0]
            return ReconcileResult(
                status=ReconcileStatus.CONFIRMED,
                move=best_chain[0],
                moves_chain=best_chain,
                score=best_score,
                confidence=0.88,
                explanation=f"Reconciliación en cadena (+{len(best_chain)} jugadas)"
            )

        return None
