"""
Módulo de cálculo y seguimiento de Precisión de Partida (CAPS - Computer Accuracy Percentage System).
Calcula la precisión de jugadas individuales y el promedio acumulado para Blancas y Negras
siguiendo las fórmulas oficiales sigmoides de Win Rate (Lichess / Chess.com).
"""

from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import chess

from chess_vision.engine.classifier import MoveClassifier
from chess_vision.engine.evaluator import PositionAnalysis, CandidateMove
from chess_vision.engine.opening_book import get_opening_book


@dataclass
class AccuracySummary:
    """Resumen consolidado de precisión para el panel de interfaz de usuario."""
    white_accuracy: float = 100.0
    black_accuracy: float = 100.0
    white_last_accuracy: Optional[float] = None
    black_last_accuracy: Optional[float] = None
    white_moves: int = 0
    black_moves: int = 0


class AccuracyTracker:
    """
    Rastreador de precisión de movimientos y evaluaciones en tiempo real para ambos bandos.
    Implementa el modelo CAPS basado en la pérdida de probabilidad de victoria (Delta Win%).
    """

    def __init__(self):
        self._white_history: List[float] = []
        self._black_history: List[float] = []
        # Estructura para registrar jugadas pendientes de evaluación posterior si no estaban en Multi-PV
        self._pending_move: Optional[Dict[str, Any]] = None

    @staticmethod
    def cp_to_win_rate(score_cp: Optional[int], mate_in: Optional[int] = None) -> float:
        """
        Convierte centipeones o distancia a mate en porcentaje de victoria (0% - 100%).
        Win%(cp) = 50 + 50 * (2.0 / (1.0 + exp(-0.00368208 * cp)) - 1.0)
        """
        return MoveClassifier.cp_to_win_rate(score_cp, mate_in)

    @staticmethod
    def calculate_move_accuracy(
        delta_win: float,
        is_book: bool = False,
        is_best: bool = False
    ) -> float:
        """
        Calcula la precisión de una jugada individual (0.0% a 100.0%) a partir de delta_win.
        acc = max(0.0, min(100.0, 103.1668 * exp(-0.04354 * delta_win) - 3.1669))
        """
        if is_book or is_best or delta_win <= 0.0001:
            return 100.0

        try:
            acc = 103.1668 * math.exp(-0.04354 * delta_win) - 3.1669
            return max(0.0, min(100.0, acc))
        except OverflowError:
            return 0.0

    @property
    def white_accuracy(self) -> float:
        """Promedio acumulado de precisión de Blancas."""
        if not self._white_history:
            return 100.0
        return sum(self._white_history) / len(self._white_history)

    @property
    def black_accuracy(self) -> float:
        """Promedio acumulado de precisión de Negras."""
        if not self._black_history:
            return 100.0
        return sum(self._black_history) / len(self._black_history)

    @property
    def white_last_acc(self) -> Optional[float]:
        """Precisión de la última jugada realizada por Blancas."""
        return self._white_history[-1] if self._white_history else None

    @property
    def black_last_acc(self) -> Optional[float]:
        """Precisión de la última jugada realizada por Negras."""
        return self._black_history[-1] if self._black_history else None

    @property
    def white_moves_count(self) -> int:
        """Cantidad de jugadas evaluadas de Blancas."""
        return len(self._white_history)

    @property
    def black_moves_count(self) -> int:
        """Cantidad de jugadas evaluadas de Negras."""
        return len(self._black_history)

    def reset(self) -> None:
        """Reinicia el historial de precisión al comenzar una nueva partida o pulsar Reiniciar."""
        self._white_history.clear()
        self._black_history.clear()
        self._pending_move = None

    def record_move(
        self,
        color: chess.Color,
        accuracy: Optional[float] = None,
        score_cp: Optional[int] = None,
        best_score_cp: Optional[int] = None,
        mate_in: Optional[int] = None,
        best_mate_in: Optional[int] = None,
        win_best: Optional[float] = None,
        win_played: Optional[float] = None,
        is_book: bool = False,
        is_best: bool = False,
        move: Optional[chess.Move] = None
    ) -> float:
        """
        Registra una jugada calculando su precisión e incorporándola al historial del bando correspondiente.
        """
        if is_book or is_best:
            acc = 100.0
        elif accuracy is not None:
            acc = max(0.0, min(100.0, float(accuracy)))
        elif win_best is not None and win_played is not None:
            delta_win = max(0.0, float(win_best) - float(win_played))
            acc = self.calculate_move_accuracy(delta_win)
        elif best_score_cp is not None or best_mate_in is not None:
            wb = self.cp_to_win_rate(best_score_cp, best_mate_in)
            wp = self.cp_to_win_rate(score_cp, mate_in)
            delta_win = max(0.0, wb - wp)
            acc = self.calculate_move_accuracy(delta_win)
        else:
            acc = 100.0

        if color == chess.WHITE:
            self._white_history.append(acc)
        else:
            self._black_history.append(acc)

        # Si había jugada pendiente para este bando, limpiarla
        if self._pending_move and self._pending_move.get("color") == color:
            self._pending_move = None

        return acc

    def record_move_from_board(
        self,
        board_before: chess.Board,
        move: chess.Move,
        previous_analysis: Optional[PositionAnalysis] = None
    ) -> float:
        """
        Evalúa y registra una jugada realizada sobre el tablero a partir de la posición previa y su análisis.
        """
        color = board_before.turn

        # 1. Comprobar libro de aperturas
        try:
            is_book, _ = get_opening_book().is_book_move(board_before, move)
            if is_book:
                return self.record_move(color, is_book=True, move=move)
        except Exception:
            pass

        # 2. Si disponemos del análisis previo de la posición
        if previous_analysis and previous_analysis.top_moves:
            best_cand = previous_analysis.objective_best_move or previous_analysis.best_move
            win_best = best_cand.win_rate if best_cand else 50.0

            if best_cand and move == best_cand.move:
                return self.record_move(color, is_best=True, move=move)

            # Buscar si está entre las líneas candidatas Multi-PV
            cand_played = next((c for c in previous_analysis.top_moves if c.move == move), None)
            if cand_played is not None:
                delta_win = max(0.0, win_best - cand_played.win_rate)
                acc = self.calculate_move_accuracy(delta_win)
                return self.record_move(color, accuracy=acc, move=move)

            # Si la jugada no está en el Multi-PV, es inferior a todas las candidatas.
            # Registramos pendiente para evaluarla con la respuesta del motor o usamos estimación inicial
            worst_cand = previous_analysis.top_moves[-1]
            estimated_loss = max(10.0, win_best - worst_cand.win_rate + 5.0)
            provisional_acc = self.calculate_move_accuracy(estimated_loss)

            # Anotar pendiente para ajustar con el siguiente análisis
            self._pending_move = {
                "color": color,
                "win_best": win_best,
                "move": move,
                "history_index": len(self._white_history) if color == chess.WHITE else len(self._black_history)
            }
            return self.record_move(color, accuracy=provisional_acc, move=move)

        # Si no había análisis previo, registrar como 100% o jugada pendiente neutral
        self._pending_move = {
            "color": color,
            "win_best": 50.0,
            "move": move,
            "history_index": len(self._white_history) if color == chess.WHITE else len(self._black_history)
        }
        return self.record_move(color, accuracy=100.0, move=move)

    def record_analysis(self, analysis: PositionAnalysis) -> Optional[AccuracySummary]:
        """
        Recibe el análisis de la nueva posición y, si existía una jugada pendiente de clasificar
        con precisión exacta, ajusta retrospectivamente la precisión del último movimiento.
        """
        if not self._pending_move or not analysis or not analysis.top_moves:
            return self.get_summary()

        color = self._pending_move["color"]
        win_best = self._pending_move["win_best"]
        hist_idx = self._pending_move["history_index"]

        # En la nueva posición le toca al oponente.
        # La evaluación óptima del oponente se invierte para el bando que acaba de mover:
        # win_played = 100.0 - win_rate_oponente
        opp_best = analysis.objective_best_move or analysis.best_move
        if opp_best is not None:
            win_played = max(0.0, min(100.0, 100.0 - opp_best.win_rate))
            delta_win = max(0.0, win_best - win_played)
            acc = self.calculate_move_accuracy(delta_win)

            history = self._white_history if color == chess.WHITE else self._black_history
            if 0 <= hist_idx < len(history):
                history[hist_idx] = acc

        self._pending_move = None
        return self.get_summary()

    def get_summary(self) -> AccuracySummary:
        """Genera un snapshot inmutable del estado actual de precisión."""
        return AccuracySummary(
            white_accuracy=round(self.white_accuracy, 1),
            black_accuracy=round(self.black_accuracy, 1),
            white_last_accuracy=round(self.white_last_acc, 1) if self.white_last_acc is not None else None,
            black_last_accuracy=round(self.black_last_acc, 1) if self.black_last_acc is not None else None,
            white_moves=self.white_moves_count,
            black_moves=self.black_moves_count
        )
