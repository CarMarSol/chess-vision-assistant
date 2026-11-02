"""
Evaluador Multi-PV de posiciones de ajedrez.
Analiza concurrentemente las 3 mejores líneas de juego y las clasifica.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import chess
import chess.engine
from chess_vision.engine.classifier import MoveClassifier, MoveClassification
from chess_vision.engine.styles import StyleEvaluator, EloManager, ChessStyle
from chess_vision.engine.opening_book import get_opening_book


@dataclass
class CandidateMove:
    """Representa una de las jugadas candidatas encontradas en el análisis Multi-PV."""
    rank: int                      # 1 = Óptimo, 2 = Alternativa 1, 3 = Alternativa 2
    move: chess.Move
    san: str                       # Notación algebraica (ej. "Nf3", "e4", "O-O")
    uci: str                       # Notación UCI (ej. "g1f3", "e2e4")
    score_cp: Optional[int] = None # Centipeones (perspectiva del turno)
    mate_in: Optional[int] = None  # Mate en N jugadas
    pv: List[chess.Move] = field(default_factory=list)
    depth: int = 0
    nodes: int = 0
    win_rate: float = 50.0
    classification: MoveClassification = field(default_factory=lambda: MoveClassification(
        category="best", label="Mejor jugada", symbol="", badge_color="#81B64C",
        delta_cp=0.0, win_rate_loss=0.0, description=""
    ))
    is_style_pick: bool = False
    is_objective_best: bool = False
    is_adaptive_pick: bool = False
    is_subtle_loss_pick: bool = False
    adaptive_reason: str = ""

    @property
    def display_score(self) -> str:
        """Formatea la puntuación para la interfaz gráfica (+1.25, -0.40, M3, -M2)."""
        if self.mate_in is not None:
            if self.mate_in > 0:
                return f"M{self.mate_in}"
            else:
                return f"-M{abs(self.mate_in)}"
        if self.score_cp is not None:
            val = self.score_cp / 100.0
            sign = "+" if val > 0 else ""
            return f"{sign}{val:.2f}"
        return "0.00"


@dataclass
class PositionAnalysis:
    """Resultado consolidado del análisis de una posición para un tablero."""
    fen: str
    turn: chess.Color
    top_moves: List[CandidateMove]
    best_move: Optional[CandidateMove] = None
    alternative_1: Optional[CandidateMove] = None
    alternative_2: Optional[CandidateMove] = None
    objective_best_move: Optional[CandidateMove] = None
    style_recommended_move: Optional[CandidateMove] = None
    adaptive_move: Optional[CandidateMove] = None
    target_accuracy: Optional[int] = None
    style_name: str = "balanced"
    evaluation_bar_score: float = 0.0  # -1.0 a +1.0 o centipeones desde perspectiva blancas
    is_check: bool = False
    is_checkmate: bool = False
    is_stalemate: bool = False
    is_subtle_loss_mode: bool = False


class Evaluator:
    """
    Motor de análisis Multi-PV que procesa las líneas candidatas y
    las decora con clasificaciones y estilos de juego.
    """

    @classmethod
    def process_engine_multipv_results(
        cls,
        board: chess.Board,
        engine_infos: List[dict],
        style: str = ChessStyle.BALANCED,
        elo: int = 2500,
        target_accuracy: Optional[int] = 80,
        current_accuracy: Optional[float] = None,
        enable_adaptive: bool = True,
        adaptive_tolerance: int = 5,
        enable_subtle_loss: bool = False,
        subtle_loss_move: int = 20,
        subtle_loss_severity: str = "moderate"
    ) -> PositionAnalysis:
        """
        Transforma los resultados brutos del motor (lista de infos Multi-PV)
        en una estructura PositionAnalysis con exactamente hasta 3 líneas candidatas.
        """
        if not engine_infos:
            return PositionAnalysis(
                fen=board.fen(),
                turn=board.turn,
                top_moves=[],
                is_check=board.is_check(),
                is_checkmate=board.is_checkmate(),
                is_stalemate=board.is_stalemate()
            )

        # Ordenar infos por puntuación descendente
        # En python-chess, multipv 1 es la mejor línea
        candidates_raw = []
        for info in engine_infos:
            pv = info.get("pv", [])
            if not pv:
                continue

            move = pv[0]
            score_obj = info.get("score")
            score_cp = None
            mate_in = None

            if score_obj:
                # Obtener score relativo al bando que mueve
                rel_score = score_obj.relative
                if rel_score.is_mate():
                    mate_in = rel_score.mate()
                else:
                    score_cp = rel_score.score()

            depth = info.get("depth", 0)
            nodes = info.get("nodes", 0)

            candidates_raw.append({
                "move": move,
                "pv": pv,
                "score_cp": score_cp,
                "adjusted_cp": score_cp,
                "mate_in": mate_in,
                "depth": depth,
                "nodes": nodes
            })

        # Aplicar modulación de estilo con límite de margen seguro (50-70 cp)
        ranked_candidates, obj_best_item = StyleEvaluator.filter_and_rank_by_style(
            board=board,
            candidates_raw=candidates_raw,
            style=style,
            max_margin_cp=StyleEvaluator.DEFAULT_STYLE_MARGIN_CP
        )

        obj_best_mv = obj_best_item["move"] if obj_best_item else None

        # Extraer puntuación óptima (#1) y segunda para clasificación objetiva
        best_item = obj_best_item
        second_item = candidates_raw[1] if len(candidates_raw) > 1 else None

        best_score_cp = best_item["score_cp"] if best_item else None
        best_mate_in = best_item["mate_in"] if best_item else None
        second_score_cp = second_item["score_cp"] if second_item else None

        top_moves: List[CandidateMove] = []
        for idx, item in enumerate(ranked_candidates[:4]):
            rank = idx + 1
            mv = item["move"]
            try:
                san_str = board.san(mv)
            except Exception:
                san_str = mv.uci()

            is_book, book_name = get_opening_book().is_book_move(board, mv)

            cls_meta = MoveClassifier.classify_move(
                board=board,
                move=mv,
                rank=rank,
                score_cp=item["score_cp"],
                mate_in=item["mate_in"],
                best_score_cp=best_score_cp,
                best_mate_in=best_mate_in,
                second_best_score_cp=second_score_cp,
                is_book_move=is_book,
                book_description=book_name
            )

            wr = MoveClassifier.cp_to_win_rate(item["score_cp"], item["mate_in"])
            is_obj_best = (mv == obj_best_mv)
            is_style = (idx == 0 and style != ChessStyle.BALANCED and not is_obj_best and item.get("is_style_eligible", False))

            cand = CandidateMove(
                rank=rank,
                move=mv,
                san=san_str,
                uci=mv.uci(),
                score_cp=item["score_cp"],
                mate_in=item["mate_in"],
                pv=item["pv"],
                depth=item["depth"],
                nodes=item["nodes"],
                win_rate=wr,
                classification=cls_meta,
                is_style_pick=is_style,
                is_objective_best=is_obj_best
            )
            top_moves.append(cand)

        # Cálculo de la barra de evaluación desde la perspectiva de las blancas
        eval_bar_score = 0.0
        if top_moves:
            # Barra basada en la mejor jugada objetiva
            obj_cand = next((c for c in top_moves if c.is_objective_best), top_moves[0])
            if obj_cand.mate_in is not None:
                turn_sign = 1 if board.turn == chess.WHITE else -1
                eval_bar_score = 100.0 * turn_sign if obj_cand.mate_in > 0 else -100.0 * turn_sign
            elif obj_cand.score_cp is not None:
                turn_sign = 1 if board.turn == chess.WHITE else -1
                eval_bar_score = (obj_cand.score_cp / 100.0) * turn_sign

        obj_best_cand = next((c for c in top_moves if c.is_objective_best), (top_moves[0] if top_moves else None))
        style_rec_cand = top_moves[0] if top_moves else None

        # Selección de movimiento adaptativo por precisión objetivo o derrota sutil
        adaptive_cand = None
        if (enable_adaptive or enable_subtle_loss) and top_moves:
            from chess_vision.engine.adaptive_recommender import AdaptiveRecommender
            curr_acc = current_accuracy if current_accuracy is not None else 100.0
            tgt_acc = target_accuracy if target_accuracy is not None else 80
            adaptive_cand = AdaptiveRecommender.select_adaptive_move(
                candidates=top_moves,
                current_accuracy=curr_acc,
                target_accuracy=tgt_acc,
                tolerance=adaptive_tolerance,
                elo=elo,
                style=style,
                board=board,
                enable_subtle_loss=enable_subtle_loss,
                subtle_loss_move=subtle_loss_move,
                subtle_loss_severity=subtle_loss_severity
            )

        analysis = PositionAnalysis(
            fen=board.fen(),
            turn=board.turn,
            top_moves=top_moves,
            best_move=top_moves[0] if len(top_moves) >= 1 else None,
            alternative_1=top_moves[1] if len(top_moves) >= 2 else None,
            alternative_2=top_moves[2] if len(top_moves) >= 3 else None,
            objective_best_move=obj_best_cand,
            style_recommended_move=style_rec_cand,
            adaptive_move=adaptive_cand,
            target_accuracy=target_accuracy if enable_adaptive else None,
            style_name=style,
            evaluation_bar_score=eval_bar_score,
            is_check=board.is_check(),
            is_checkmate=board.is_checkmate(),
            is_stalemate=board.is_stalemate(),
            is_subtle_loss_mode=enable_subtle_loss
        )
        return analysis
