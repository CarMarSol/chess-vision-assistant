"""
Clasificador cualitativo de jugadas al estilo Chess.com / Lichess.
Calcula el Win Rate formal y clasifica las jugadas en:
Brillante (!!), Gran jugada (!), Mejor jugada, Excelente, Buena,
Libro, Imprecisión (?!), Error (?) y Error grave (??).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional, Tuple
import chess


@dataclass
class MoveClassification:
    """Metadatos de la clasificación de un movimiento de ajedrez."""
    category: str  # "brilliant", "great", "best", "excellent", "good", "book", "inaccuracy", "mistake", "blunder"
    label: str     # "Brillante", "Gran jugada", "Mejor jugada", etc.
    symbol: str    # "!!", "!", "", "✓", "?!", "?", "??"
    badge_color: str
    delta_cp: float
    win_rate_loss: float
    description: str


class MoveClassifier:
    """
    Motor de clasificación cualitativa con fórmulas oficiales de Win Rate sigmoidal.
    """

    # Colores visuales oficiales
    COLORS = {
        "brilliant": "#26C2A3",     # Cian / Verde menta brillante (!!)
        "great": "#1B8FD8",         # Azul brillante (!)
        "best": "#81B64C",          # Verde Chess.com
        "excellent": "#457523",     # Verde profundo
        "good": "#7FA650",          # Verde olivo
        "book": "#A87A51",          # Marrón libro de aperturas
        "inaccuracy": "#F7C631",    # Amarillo (?!)
        "mistake": "#FFA500",       # Naranja (?)
        "blunder": "#FA412D",       # Rojo fuerte (??)
    }

    @staticmethod
    def cp_to_win_rate(score_cp: Optional[int], mate_in: Optional[int] = None) -> float:
        """
        Convierte una evaluación en centipeones o mate a porcentaje de probabilidad de victoria (0% a 100%).
        Utiliza el modelo sigmoide calibrado de Lichess / Stockfish:
        WinRate = 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1)
        """
        if mate_in is not None:
            if mate_in > 0:
                return 100.0
            elif mate_in < 0:
                return 0.0
            else:
                return 50.0

        if score_cp is None:
            return 50.0

        # Clampeo de CP para estabilidad numérica
        cp = max(-3000.0, min(3000.0, float(score_cp)))
        try:
            val = 2.0 / (1.0 + math.exp(-0.00368208 * cp)) - 1.0
            return max(0.0, min(100.0, 50.0 + 50.0 * val))
        except OverflowError:
            return 100.0 if cp > 0 else 0.0

    @classmethod
    def is_sacrifice(cls, board: chess.Board, move: chess.Move) -> bool:
        """
        Determina heurísticamente si un movimiento constituye un sacrificio de pieza
        (la pieza se coloca en una casilla donde puede ser capturada por una pieza de menor valor).
        """
        piece = board.piece_at(move.from_square)
        if not piece:
            return False

        piece_values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0
        }
        val = piece_values.get(piece.piece_type, 0)
        if val < 3:
            return False

        # Si el destino está atacado por el rival y defendido o desprotegido
        opponent_color = not board.turn
        dest_square = move.to_square

        # Ver atacantes enemigos en la casilla destino
        enemy_attackers = board.attackers(opponent_color, dest_square)
        if enemy_attackers:
            # Hay piezas enemigas que pueden recapturar
            min_attacker_val = min(
                piece_values.get(board.piece_at(sq).piece_type, 0)
                for sq in enemy_attackers if board.piece_at(sq)
            )
            # Sacrificio si la pieza que entregamos vale más que la que nos come o si es captura gratis
            if val > min_attacker_val:
                return True

        return False

    @classmethod
    def classify_move(
        cls,
        board: chess.Board,
        move: chess.Move,
        rank: int,
        score_cp: Optional[int],
        mate_in: Optional[int],
        best_score_cp: Optional[int],
        best_mate_in: Optional[int],
        second_best_score_cp: Optional[int] = None,
        is_book_move: bool = False,
        book_description: Optional[str] = None
    ) -> MoveClassification:
        """
        Clasifica una jugada evaluando su mérito relativo frente a la mejor alternativa.
        - rank: posición en el ranking Multi-PV (1 = óptima, 2 = 2ª mejor, 3 = 3ª mejor, etc.)
        """
        if is_book_move:
            desc = book_description or "Jugada teórica de apertura estándar."
            return MoveClassification(
                category="book",
                label="Libro",
                symbol="",
                badge_color=cls.COLORS["book"],
                delta_cp=0.0,
                win_rate_loss=0.0,
                description=desc
            )

        # Calcular Win Rates
        current_wr = cls.cp_to_win_rate(score_cp, mate_in)
        best_wr = cls.cp_to_win_rate(best_score_cp, best_mate_in)

        # Delta de Centipeones
        if best_mate_in is not None and mate_in is not None:
            if best_mate_in > 0 and mate_in > 0:
                delta_cp = (mate_in - best_mate_in) * 50.0
            else:
                delta_cp = (best_wr - current_wr) * 10.0
        elif score_cp is not None and best_score_cp is not None:
            delta_cp = max(0.0, float(best_score_cp - score_cp))
        else:
            delta_cp = max(0.0, (best_wr - current_wr) * 10.0)

        wr_loss = max(0.0, best_wr - current_wr)

        # 1. Comprobar si es Brillante (!!)
        if rank == 1 and current_wr >= 85.0 and cls.is_sacrifice(board, move):
            return MoveClassification(
                category="brilliant",
                label="Brillante",
                symbol="!!",
                badge_color=cls.COLORS["brilliant"],
                delta_cp=0.0,
                win_rate_loss=0.0,
                description="¡Sacrificio brillante que mantiene la ventaja ganadora!"
            )

        # 2. Comprobar si es Gran Jugada (!)
        # Única jugada que preserva la ventaja o gana, superando a la segunda por amplio margen
        if rank == 1 and second_best_score_cp is not None and best_score_cp is not None:
            gap_with_second = best_score_cp - second_best_score_cp
            if gap_with_second >= 160 and current_wr >= 60.0:
                return MoveClassification(
                    category="great",
                    label="Gran jugada",
                    symbol="!",
                    badge_color=cls.COLORS["great"],
                    delta_cp=0.0,
                    win_rate_loss=0.0,
                    description="Jugada clave que encuentra el único camino ganador."
                )

        # 3. Mejor jugada
        if rank == 1 or delta_cp <= 8.0:
            return MoveClassification(
                category="best",
                label="Mejor jugada",
                symbol="★",
                badge_color=cls.COLORS["best"],
                delta_cp=0.0,
                win_rate_loss=0.0,
                description="La jugada más precisa según el motor Stockfish."
            )

        # 4. Excelente
        if delta_cp <= 28.0 and wr_loss <= 2.5:
            return MoveClassification(
                category="excellent",
                label="Excelente",
                symbol="✓",
                badge_color=cls.COLORS["excellent"],
                delta_cp=delta_cp,
                win_rate_loss=wr_loss,
                description="Movimiento muy fuerte que mantiene casi intacta la ventaja."
            )

        # 5. Buena
        if delta_cp <= 65.0 and wr_loss <= 6.5:
            return MoveClassification(
                category="good",
                label="Buena",
                symbol="",
                badge_color=cls.COLORS["good"],
                delta_cp=delta_cp,
                win_rate_loss=wr_loss,
                description="Movimiento sólido con mínima pérdida de posición."
            )

        # 6. Imprecisión (?!)
        if delta_cp <= 160.0 and wr_loss <= 15.0:
            return MoveClassification(
                category="inaccuracy",
                label="Imprecisión",
                symbol="?!",
                badge_color=cls.COLORS["inaccuracy"],
                delta_cp=delta_cp,
                win_rate_loss=wr_loss,
                description="Movimiento dudoso que cede parte de la iniciativa."
            )

        # 7. Error (?)
        if delta_cp <= 320.0 and wr_loss <= 28.0:
            return MoveClassification(
                category="mistake",
                label="Error",
                symbol="?",
                badge_color=cls.COLORS["mistake"],
                delta_cp=delta_cp,
                win_rate_loss=wr_loss,
                description="Error táctico o posicional que perjudica la partida."
            )

        # 8. Error grave (??)
        return MoveClassification(
            category="blunder",
            label="Error grave",
            symbol="??",
            badge_color=cls.COLORS["blunder"],
            delta_cp=delta_cp,
            win_rate_loss=wr_loss,
            description="Fallo crítico que compromete severamente la posición."
        )
