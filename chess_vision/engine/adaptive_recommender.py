"""
Módulo de Recomendación Adaptativa y Humanización de Jugadas por Precisión Objetivo.
Ajusta dinámicamente la recomendación del motor (entre jugadas óptimas y secundarias naturales)
para converger la precisión acumulada de la partida hacia un objetivo fijado (ej. 80%),
evitando patrones de juego 100% sobrehumanos (anticheat / humanización).
"""

from __future__ import annotations
from chess_vision.i18n import tr
import random
from typing import List, Optional
import chess

from chess_vision.engine.evaluator import CandidateMove
from chess_vision.engine.styles import ChessStyle


class AdaptiveRecommender:
    """
    Motor heurístico de humanización y control de precisión objetivo.
    Modula la selección del movimiento recomendado entre las líneas Multi-PV analizadas
    para mantener el porcentaje de precisión CAPS dentro del rango deseado.
    """

    @classmethod
    def select_adaptive_move(
        cls,
        candidates: List[CandidateMove],
        current_accuracy: float = 100.0,
        target_accuracy: int = 80,
        tolerance: int = 5,
        elo: int = 2500,
        style: str = ChessStyle.BALANCED,
        board: Optional[chess.Board] = None,
        rng: Optional[random.Random] = None,
        enable_subtle_loss: bool = False,
        subtle_loss_move: int = 20,
        subtle_loss_severity: str = "moderate"
    ) -> Optional[CandidateMove]:
        """
        Selecciona la jugada idónea de entre los candidatos analizados según la convergencia
        de precisión acumulada respecto a la precisión objetivo, o según el modo Derrota Sutil.
        """
        if not candidates:
            return None

        # Limpiar marcas previas
        for c in candidates:
            c.is_adaptive_pick = False
            c.is_subtle_loss_pick = False
            c.adaptive_reason = ""

        # Si sólo hay un movimiento legal disponible (jugada forzada)
        if len(candidates) == 1:
            chosen = candidates[0]
            chosen.is_adaptive_pick = True
            chosen.is_subtle_loss_pick = False
            chosen.adaptive_reason = tr('Única jugada disponible')
            return chosen

        # ---------------------------------------------------------------------
        # MODO DERROTA SUTIL / ERROR NO OBVIO (Jugar bien y perder orgánicamente)
        # ---------------------------------------------------------------------
        if enable_subtle_loss:
            fullmove = board.fullmove_number if board is not None else 1
            best_cand = candidates[0]

            # Determinar si la posición ya está en clara desventaja (eval < -1.5 peones / mate en contra)
            is_disadvantaged = (
                (best_cand.mate_in is not None and best_cand.mate_in < 0) or
                (best_cand.score_cp is not None and best_cand.score_cp < -150)
            )

            # Fase 3: Declive natural una vez en desventaja (eval < -1.5 peones)
            if is_disadvantaged:
                secondary_cands = [c for c in candidates if c.rank >= 2]
                declining_cands: List[CandidateMove] = []
                for c in secondary_cands:
                    # Evitar regalar mate inmediato en 1 si la mejor jugada no lo tiene
                    if c.mate_in is not None and -1 <= c.mate_in < 0:
                        continue
                    delta = c.classification.delta_cp if c.classification else (
                        float(best_cand.score_cp - c.score_cp) if (best_cand.score_cp is not None and c.score_cp is not None) else 60.0
                    )
                    if delta <= 250.0:
                        declining_cands.append(c)

                chosen = declining_cands[0] if declining_cands else candidates[0]
                chosen.is_adaptive_pick = True
                chosen.is_subtle_loss_pick = True
                chosen.adaptive_reason = tr('Derrota sutil (Declive natural y orgánico)')
                return chosen

            # Fase 1: Apertura y consolidación sólida (fullmove < subtle_loss_move)
            if fullmove < subtle_loss_move:
                chosen = candidates[0]
                chosen.is_adaptive_pick = True
                chosen.is_subtle_loss_pick = False
                chosen.adaptive_reason = tr('Derrota sutil (Fase sólida inicial: jugada {value0}/{value1})', value0=fullmove, value1=subtle_loss_move)
                return chosen

            # Fase 2: Inducción del error humano no obvio (fullmove >= subtle_loss_move)
            ranges = {
                "subtle": (90.0, 160.0),
                "moderate": (160.0, 280.0),
                "slow_decline": (70.0, 130.0),
            }
            min_loss, max_loss = ranges.get(subtle_loss_severity, (160.0, 280.0))

            secondary_cands = [c for c in candidates if c.rank >= 2]
            ideal_candidates: List[CandidateMove] = []
            fallback_candidates: List[CandidateMove] = []

            for c in secondary_cands:
                # a) NO ser un blunder grotesco ni entregar mate en 1 o 2
                if c.mate_in is not None and -2 <= c.mate_in < 0:
                    continue

                delta = c.classification.delta_cp if c.classification else (
                    float(best_cand.score_cp - c.score_cp) if (best_cand.score_cp is not None and c.score_cp is not None) else 0.0
                )

                if delta > 420.0:
                    continue

                # b) Pérdida creíble según severidad
                if min_loss <= delta <= max_loss:
                    ideal_candidates.append(c)
                elif 50.0 <= delta <= 380.0:
                    fallback_candidates.append(c)

            if ideal_candidates:
                chosen = ideal_candidates[0]
                cls_meta = chosen.classification
                delta_val = cls_meta.delta_cp if cls_meta else (
                    float(best_cand.score_cp - chosen.score_cp) if (best_cand.score_cp is not None and chosen.score_cp is not None) else min_loss
                )
                chosen.is_adaptive_pick = True
                chosen.is_subtle_loss_pick = True
                chosen.adaptive_reason = tr('Error sutil inducido (No obvio · Pérdida {value0:.0f} cp)', value0=delta_val)
                return chosen
            elif fallback_candidates:
                target_mid = (min_loss + max_loss) / 2.0
                fallback_candidates.sort(key=lambda c: abs(
                    (c.classification.delta_cp if c.classification else (float(best_cand.score_cp - c.score_cp) if (best_cand.score_cp is not None and c.score_cp is not None) else target_mid)) - target_mid
                ))
                chosen = fallback_candidates[0]
                cls_meta = chosen.classification
                delta_val = cls_meta.delta_cp if cls_meta else (
                    float(best_cand.score_cp - chosen.score_cp) if (best_cand.score_cp is not None and chosen.score_cp is not None) else min_loss
                )
                chosen.is_adaptive_pick = True
                chosen.is_subtle_loss_pick = True
                chosen.adaptive_reason = tr('Error sutil inducido (No obvio · Pérdida {value0:.0f} cp)', value0=delta_val)
                return chosen
            else:
                # d) Si en este turno específico no hay alternativa creíble, mantener la mejor jugada
                chosen = candidates[0]
                chosen.is_adaptive_pick = True
                chosen.is_subtle_loss_pick = False
                chosen.adaptive_reason = tr('Derrota sutil (Buscando error sutil sin regalar la partida · Jugada {value0})', value0=fullmove)
                return chosen

        if rng is None:
            rng = random.Random()

        # Diferencia entre precisión actual acumulada y precisión deseada
        diff = current_accuracy - target_accuracy

        # -------------------------------------------------------------
        # CASO 1: Precisión actual MUY ALTA (diff > tolerance)
        # -------------------------------------------------------------
        # El jugador está jugando demasiado perfecto (ej. 94% vs objetivo 80%).
        # Se recomienda una jugada natural secundaria (Rank 2, 3 o 4 sólida)
        # que pierda una pequeña cantidad de centipeones (15-50 cp) para
        # reducir gradualmente la precisión hacia el objetivo sin perder la partida.
        if diff > tolerance:
            secondary_moves = [c for c in candidates if c.rank >= 2]
            safe_moves: List[CandidateMove] = []

            for cand in secondary_moves:
                cls_meta = cand.classification
                delta_cp = cls_meta.delta_cp if cls_meta else 100.0
                win_loss = cls_meta.win_rate_loss if cls_meta else 10.0
                cat = cls_meta.category if cls_meta else "inaccuracy"

                # Criterio de seguridad: No recomendar jugadas que pierdan la partida inmediatamente
                # Evitar blunders masivos a menos que el Elo configurado sea muy bajo (< 1000)
                is_safe = (delta_cp <= 120.0 or win_loss <= 15.0) and (cat != "blunder" or elo < 1000)
                if is_safe:
                    safe_moves.append(cand)

            if safe_moves:
                # Si la precisión está excesivamente alta (diff > 15), preferir Rank 3 o jugada con pérdida moderada
                if diff > 15 and len(safe_moves) > 1:
                    # Preferir la alternativa de mayor rank entre las seguras
                    chosen = safe_moves[-1]
                else:
                    # Preferir Rank 2 (primera alternativa segura)
                    chosen = safe_moves[0]

                chosen.is_adaptive_pick = True
                chosen.adaptive_reason = (
                    tr('Ajuste a objetivo {value0}% (Actual: {value1:.1f}%, jugada secundaria natural)', value0=target_accuracy, value1=current_accuracy)
                )
                return chosen
            else:
                # Si ninguna secundaria es segura (ej. toda otra jugada pierde la dama o lleva a mate),
                # mantener la mejor jugada para no destruir la posición
                chosen = candidates[0]
                chosen.is_adaptive_pick = True
                chosen.adaptive_reason = (
                    tr('Mejor jugada preservada (Sin alternativa secundaria segura, Obj: {value0}%)', value0=target_accuracy)
                )
                return chosen

        # -------------------------------------------------------------
        # CASO 2: Precisión actual MUY BAJA (diff < -tolerance)
        # -------------------------------------------------------------
        # El jugador está por debajo del rango objetivo (ej. 68% vs objetivo 80%).
        # Recomendar la mejor jugada objetiva (Rank 1) para subir la precisión hacia el objetivo.
        elif diff < -tolerance:
            chosen = candidates[0]
            chosen.is_adaptive_pick = True
            chosen.adaptive_reason = (
                tr('Subir precisión a {value0}% (Actual: {value1:.1f}%, mejor jugada objetiva)', value0=target_accuracy, value1=current_accuracy)
            )
            return chosen

        # -------------------------------------------------------------
        # CASO 3: Precisión EN RANGO OBJETIVO (-tolerance <= diff <= tolerance)
        # -------------------------------------------------------------
        # La precisión está en el intervalo deseado (ej. 78% con objetivo 80%).
        # Aplicar aleatoriedad ponderada según Elo y estilo de juego para humanizar.
        else:
            # Ponderación según Elo
            if elo >= 2400:
                base_weights = [0.75, 0.22, 0.03, 0.0]
            elif elo >= 1800:
                base_weights = [0.60, 0.30, 0.08, 0.02]
            elif elo >= 1400:
                base_weights = [0.48, 0.35, 0.14, 0.03]
            else:
                base_weights = [0.38, 0.34, 0.20, 0.08]

            num_cands = len(candidates)
            weights = base_weights[:num_cands]
            while len(weights) < num_cands:
                weights.append(0.01)

            # Ajustar ponderaciones por seguridad y estilo
            adjusted_weights = []
            for idx, cand in enumerate(candidates):
                w = weights[idx]
                cls_meta = cand.classification
                if cls_meta:
                    # Penalizar errores graves
                    if cls_meta.category == "blunder" and elo >= 1200:
                        w = 0.0
                    elif cls_meta.delta_cp > 130.0:
                        w *= 0.1

                # Bonificar jugada de estilo si coincide
                if cand.is_style_pick:
                    w *= 1.35

                adjusted_weights.append(w)

            total_w = sum(adjusted_weights)
            if total_w <= 0.0001:
                chosen = candidates[0]
            else:
                norm_weights = [w / total_w for w in adjusted_weights]
                chosen = rng.choices(candidates, weights=norm_weights, k=1)[0]

            chosen.is_adaptive_pick = True
            chosen.adaptive_reason = (
                tr('Objetivo cumplido ({value0:.1f}% ≈ {value1}%) · Variabilidad humana', value0=current_accuracy, value1=target_accuracy)
            )
            return chosen
