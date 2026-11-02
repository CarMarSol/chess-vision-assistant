"""
Modulador de estilos de juego y simulación de niveles de Elo para Stockfish.
Soporta: Equilibrado, Agresivo, Defensivo, Táctico y Posicional; y rango Elo 700 - 2800.
"""

from __future__ import annotations
import random
from typing import List, Dict, Any, Optional
import chess
from chess_vision.engine.classifier import MoveClassification


class ChessStyle:
    """Constantes de estilos de juego."""
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    DEFENSIVE = "defensive"
    TACTICAL = "tactical"
    POSITIONAL = "positional"

    ALL_STYLES = [BALANCED, AGGRESSIVE, DEFENSIVE, TACTICAL, POSITIONAL]


class StyleEvaluator:
    """
    Aplica heurísticas de estilo para ponderar o seleccionar movimientos de ajedrez
    según la personalidad táctica o estratégica deseada, garantizando un margen
    máximo de pérdida de centipeones (50-70 cp) para no perjudicar la partida.
    """
    DEFAULT_STYLE_MARGIN_CP: float = 65.0

    @classmethod
    def filter_and_rank_by_style(
        cls,
        board: chess.Board,
        candidates_raw: List[Dict[str, Any]],
        style: str,
        max_margin_cp: float = DEFAULT_STYLE_MARGIN_CP
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Reordena las candidatas según el estilo sólo si su pérdida respecto a la
        mejor jugada objetiva no excede `max_margin_cp` (ej. 65 cp).
        Retorna (lista_reordenada, mejor_objetivo_original).
        """
        if not candidates_raw:
            return [], None

        objective_best = candidates_raw[0]
        style = style.lower()
        if style == ChessStyle.BALANCED or len(candidates_raw) <= 1:
            return candidates_raw, objective_best

        best_score_cp = objective_best.get("score_cp")
        best_mate = objective_best.get("mate_in")

        # Si hay mate forzado en la mejor línea objetiva, no desviar por estilo salvo otro mate
        if best_mate is not None and best_mate > 0:
            return candidates_raw, objective_best

        # Asignar adjusted_cp respetando el margen de seguridad
        for item in candidates_raw:
            mv = item["move"]
            score_cp = item.get("score_cp")
            bonus = cls.score_bonus_for_style(board, mv, style)
            item["style_bonus"] = bonus

            if score_cp is not None and best_score_cp is not None:
                loss_cp = best_score_cp - score_cp
                if loss_cp <= max_margin_cp:
                    # Dentro del margen seguro: bonificación activa
                    item["adjusted_cp"] = score_cp + int(bonus)
                    item["is_style_eligible"] = True
                else:
                    # Pérdida excesiva: se mantiene sin bonificación para no provocar blunder
                    item["adjusted_cp"] = score_cp
                    item["is_style_eligible"] = False
            else:
                item["adjusted_cp"] = score_cp
                item["is_style_eligible"] = False

        # Reordenar por adjusted_cp
        def sort_key(c):
            if c.get("mate_in") is not None:
                return 100000 if c["mate_in"] > 0 else -100000
            return c.get("adjusted_cp") if c.get("adjusted_cp") is not None else -99999

        ranked = sorted(candidates_raw, key=sort_key, reverse=True)
        return ranked, objective_best

    @classmethod
    def score_bonus_for_style(cls, board: chess.Board, move: chess.Move, style: str) -> float:
        """
        Calcula un ajuste en centipeones según las características del movimiento
        y el estilo seleccionado.
        """
        style = style.lower()
        if style == ChessStyle.BALANCED:
            return 0.0

        bonus = 0.0
        piece = board.piece_at(move.from_square)
        is_capture = board.is_capture(move)
        gives_check = board.gives_check(move)
        is_castling = board.is_castling(move)

        # 1. Estilo Agresivo: busca iniciativa, jaques, capturas y avances
        if style == ChessStyle.AGGRESSIVE:
            if gives_check:
                bonus += 35.0
            if is_capture:
                bonus += 25.0
            # Avance hacia el campo contrario
            rank_from = chess.square_rank(move.from_square)
            rank_to = chess.square_rank(move.to_square)
            if (board.turn == chess.WHITE and rank_to > rank_from) or (board.turn == chess.BLACK and rank_to < rank_from):
                bonus += 15.0

        # 2. Estilo Defensivo: busca seguridad de rey, consolidación y simplificación
        elif style == ChessStyle.DEFENSIVE:
            if is_castling:
                bonus += 40.0
            # Si el rey está bajo ataque o el movimiento retira una pieza amenazada
            if piece and piece.piece_type == chess.KING:
                bonus += 15.0
            # Cambios de damas si vamos con ventaja
            if is_capture and board.piece_at(move.to_square) and board.piece_at(move.to_square).piece_type == chess.QUEEN:
                bonus += 25.0

        # 3. Estilo Táctico: busca combinaciones, sacrificios y piezas en contacto
        elif style == ChessStyle.TACTICAL:
            if gives_check:
                bonus += 30.0
            if is_capture:
                bonus += 20.0
            # Ataques a piezas mayores
            dest_attackers = board.attackers(not board.turn, move.to_square)
            if dest_attackers:
                bonus += 25.0

        # 4. Estilo Posicional: control del centro, estructura de peones y torres abiertas
        elif style == ChessStyle.POSITIONAL:
            # Control de casillas centrales (d4, e4, d5, e5)
            center_squares = {chess.D4, chess.E4, chess.D5, chess.E5, chess.C4, chess.F4, chess.C5, chess.F5}
            if move.to_square in center_squares:
                bonus += 30.0
            if is_castling:
                bonus += 25.0
            # Torres en columnas abiertas
            if piece and piece.piece_type == chess.ROOK:
                file_idx = chess.square_file(move.to_square)
                pawns_in_file = [sq for sq in chess.SQUARES if chess.square_file(sq) == file_idx and board.piece_at(sq) and board.piece_at(sq).piece_type == chess.PAWN]
                if not pawns_in_file:
                    bonus += 35.0

        return bonus


class EloManager:
    """
    Gestiona los parámetros de configuración del motor según el nivel de Elo objetivo (700 a 2800).
    """

    @classmethod
    def get_engine_options(cls, elo: int) -> Dict[str, Any]:
        """
        Retorna las opciones UCI adecuadas para Stockfish según el Elo especificado.
        Stockfish soporta UCI_LimitStrength desde Elo 1320 hasta 3190.
        """
        elo_clamped = max(700, min(2800, elo))

        if elo_clamped >= 1320:
            return {
                "UCI_LimitStrength": True,
                "UCI_Elo": elo_clamped
            }
        else:
            # Para niveles < 1320, usamos el mínimo de Stockfish (1320)
            # y en la evaluación limitaremos adicionalmente depth y skill
            return {
                "UCI_LimitStrength": True,
                "UCI_Elo": 1320
            }

    @classmethod
    def adjust_search_depth_for_low_elo(cls, elo: int, base_depth: int) -> int:
        """Limita la profundidad máxima de búsqueda para Elo inferior a 1320."""
        if elo >= 1400:
            return base_depth
        elif elo >= 1100:
            return min(base_depth, 6)
        elif elo >= 900:
            return min(base_depth, 4)
        else:
            return min(base_depth, 2)
