"""
Sincronizador de estado de juego y validador de jugadas legales para Chess Vision Assistant.
Garantiza coherencia estricta entre la visión por computador y las reglas oficiales de ajedrez.
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Set, Dict
import chess
from PySide6.QtCore import QObject, Signal

from chess_vision.game.piece_mental_map import PieceMentalMap


class SyncManager(QObject):
    """
    Gestiona el tablero chess.Board de un juego en vivo, reconciliando
    las diferencias visuales detectadas con el árbol de movimientos legales.
    """
    move_played = Signal(object, str)       # (chess.Move, san_str)
    board_reset = Signal()
    desync_detected = Signal(str)           # mensaje de error / causa
    game_over = Signal(str)                 # resultado: "1-0", "0-1", "1/2-1/2"

    def __init__(self, fen: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._board = chess.Board(fen) if fen else chess.Board()
        self._mental_map = PieceMentalMap(fen)
        self._move_history: List[Tuple[chess.Move, str]] = []  # (move, san)
        self._undone_moves: List[chess.Move] = []
        self._is_synced = True

    @property
    def board(self) -> chess.Board:
        """Acceso de sólo lectura / consulta al tablero actual."""
        return self._board

    @property
    def mental_map(self) -> PieceMentalMap:
        """Acceso al mapa mental y base de datos persistente de piezas."""
        return self._mental_map

    @property
    def is_synced(self) -> bool:
        return self._is_synced

    @property
    def fen(self) -> str:
        return self._board.fen()

    @property
    def turn(self) -> chess.Color:
        return self._board.turn

    def reset(self) -> None:
        """Reinicia el tablero a la posición inicial estándar de ajedrez."""
        self._board.reset()
        self._mental_map.reset()
        self._move_history.clear()
        self._undone_moves.clear()
        self._is_synced = True
        self.board_reset.emit()

    def set_fen(self, fen: str) -> bool:
        """Establece manualmente una posición FEN válida."""
        try:
            new_board = chess.Board(fen)
            self._board = new_board
            self._mental_map.load_from_fen(fen)
            self._move_history.clear()
            self._undone_moves.clear()
            self._is_synced = True
            self.board_reset.emit()
            self._check_game_termination()
            return True
        except ValueError as e:
            self.desync_detected.emit(f"FEN inválido: {e}")
            return False

    def push_move(self, move: chess.Move) -> bool:
        """Aplica un movimiento legal al tablero y actualiza el mapa mental de piezas."""
        if move not in self._board.legal_moves:
            # Si es promoción sin pieza especificada, intentar con dama
            if move.promotion is None:
                pawn_promo = chess.Move(move.from_square, move.to_square, promotion=chess.QUEEN)
                if pawn_promo in self._board.legal_moves:
                    move = pawn_promo
                else:
                    return False
            else:
                return False

        board_before = self._board.copy()
        san = self._board.san(move)
        # Actualizar mapa mental: tipo y color son invariantes absolutos
        self._mental_map.apply_move(move, board_before=board_before)
        self._board.push(move)
        self._move_history.append((move, san))
        self._undone_moves.clear()
        self._is_synced = True

        self.move_played.emit(move, san)
        self._check_game_termination()
        return True

    def undo_last_move(self) -> Optional[chess.Move]:
        """Deshace el último movimiento jugado."""
        if not self._board.move_stack:
            return None
        last_move = self._board.pop()
        self._mental_map.load_from_fen(self._board.fen())
        if self._move_history:
            self._move_history.pop()
        self._undone_moves.append(last_move)
        return last_move

    def redo_move(self) -> Optional[chess.Move]:
        """Reaplica el último movimiento deshecho."""
        if not self._undone_moves:
            return None
        move = self._undone_moves.pop()
        self.push_move(move)
        return move

    def match_and_apply_changed_squares(
        self,
        changed_squares: List[str],
        current_squares: Optional[Dict[str, any]] = None,
        diff_map: Optional[Dict[str, float]] = None
    ) -> Optional[chess.Move]:
        """
        Reconcilia la lista de casillas visualmente modificadas con las jugadas legales actuales.
        Aplica validación física estricta de ocupación (origen vacío, destino ocupado)
        y puntuación diferencial para resolver desambiguaciones con precisión absoluta.
        """
        if not changed_squares or len(changed_squares) < 2:
            return None

        from chess_vision.vision.piece_classifier import PieceClassifier

        changed_set: Set[str] = set(sq.lower() for sq in changed_squares)

        # 0. Reconciliación unificada con MoveReconciler si hay imágenes de casillas disponibles
        if current_squares:
            from chess_vision.game.move_reconciler import MoveReconciler, ReconcileStatus
            hl_squares = PieceClassifier.get_highlighted_squares(current_squares)
            observed = MoveReconciler.build_observations(current_squares, hl_squares=hl_squares, diff_map=diff_map)
            rec_res = MoveReconciler.reconcile(
                self._board,
                observed,
                hl_squares=hl_squares,
                diff_map=diff_map,
                mental_map=self._mental_map
            )

            if rec_res.status == ReconcileStatus.CONFIRMED:
                if rec_res.moves_chain:
                    for m in rec_res.moves_chain:
                        self.push_move(m)
                    return rec_res.moves_chain[-1]
                elif rec_res.move:
                    self.push_move(rec_res.move)
                    return rec_res.move
            elif rec_res.status == ReconcileStatus.DESYNC:
                self._is_synced = False
                self.desync_detected.emit(rec_res.explanation)
                return None

        # 1. Comprobar ENROQUE (involucra exactamente 4 casillas: rey y torre)
        if len(changed_set) >= 3:
            for legal_mv in self._board.legal_moves:
                if self._board.is_castling(legal_mv):
                    from_sq = chess.square_name(legal_mv.from_square)
                    to_sq = chess.square_name(legal_mv.to_square)
                    rook_from, rook_to = self._get_castling_rook_squares(legal_mv)
                    castling_set = {from_sq, to_sq, rook_from, rook_to}

                    if castling_set.issubset(changed_set) or len(changed_set.intersection(castling_set)) >= 3:
                        # Verificación física si hay imágenes disponibles
                        if current_squares:
                            king_orig_empty = PieceClassifier.is_square_empty(current_squares.get(from_sq))
                            rook_orig_empty = PieceClassifier.is_square_empty(current_squares.get(rook_from))
                            king_dest_occ = PieceClassifier.is_square_occupied(current_squares.get(to_sq))
                            rook_dest_occ = PieceClassifier.is_square_occupied(current_squares.get(rook_to))
                            if not (king_orig_empty and rook_orig_empty and king_dest_occ and rook_dest_occ):
                                continue
                            if (PieceClassifier.get_piece_color(current_squares.get(to_sq)) != self._board.turn or
                                PieceClassifier.get_piece_color(current_squares.get(rook_to)) != self._board.turn):
                                continue

                        self.push_move(legal_mv)
                        return legal_mv

        # 2. Comprobar EN PASSANT (involucra exactamente 3 casillas)
        if len(changed_set) >= 3:
            for legal_mv in self._board.legal_moves:
                if self._board.is_en_passant(legal_mv):
                    from_sq = chess.square_name(legal_mv.from_square)
                    to_sq = chess.square_name(legal_mv.to_square)
                    ep_sq = chess.square_name(chess.square(
                        chess.square_file(legal_mv.to_square),
                        chess.square_rank(legal_mv.from_square)
                    ))
                    ep_set = {from_sq, to_sq, ep_sq}

                    if ep_set.issubset(changed_set) or len(changed_set.intersection(ep_set)) >= 2:
                        if current_squares:
                            orig_empty = PieceClassifier.is_square_empty(current_squares.get(from_sq))
                            capt_empty = PieceClassifier.is_square_empty(current_squares.get(ep_sq))
                            dest_occ = PieceClassifier.is_square_occupied(current_squares.get(to_sq))
                            if not (orig_empty and capt_empty and dest_occ):
                                continue
                            if PieceClassifier.get_piece_color(current_squares.get(to_sq)) != self._board.turn:
                                continue

                        self.push_move(legal_mv)
                        return legal_mv

        # 3. Movimiento normal / captura: búsqueda con correspondencia estricta y puntuación diferencial
        max_allowed_changed = 6 if current_squares else 2
        candidate_moves: List[Tuple[float, chess.Move]] = []
        if len(changed_set) <= max_allowed_changed:
            for legal_mv in self._board.legal_moves:
                from_sq = chess.square_name(legal_mv.from_square)
                to_sq = chess.square_name(legal_mv.to_square)

                # Origen y destino deben estar en changed_set
                if {from_sq, to_sq}.issubset(changed_set):
                    score = (diff_map.get(from_sq, 0.0) + diff_map.get(to_sq, 0.0)) if diff_map else 0.0

                    # Verificación física rigurosa:
                    if current_squares:
                        from_img = current_squares.get(from_sq)
                        to_img = current_squares.get(to_sq)

                        # La casilla origen DEBE estar físicamente vacía ahora
                        if not PieceClassifier.is_square_empty(from_img):
                            continue

                        # La casilla destino DEBE estar físicamente ocupada ahora
                        if not PieceClassifier.is_square_occupied(to_img):
                            continue

                        # El color de la pieza en destino favorece fuertemente al bando que movió
                        dest_color = PieceClassifier.get_piece_color(to_img)
                        if dest_color == self._board.turn:
                            score += 10.0
                        elif dest_color is not None:
                            score -= 5.0

                        # Bonificación por resaltado activo (Chess.com / Lichess)
                        if PieceClassifier.is_square_highlighted(from_img):
                            score += 15.0
                        if PieceClassifier.is_square_highlighted(to_img):
                            score += 15.0

                        # Bonificación heurística de tipo de pieza (desde mapa mental)
                        moving_pt = self._mental_map.piece_type_at(legal_mv.from_square) or self._board.piece_type_at(legal_mv.from_square)
                        if moving_pt and PieceClassifier.classify_piece_type(to_img, self._board.turn) == moving_pt:
                            score += 2.0

                    candidate_moves.append((score, legal_mv))

        if candidate_moves:
            # Ordenar por mayor puntuación diferencial y prioridad estándar a coronación en dama
            candidate_moves.sort(key=lambda x: (x[0], x[1].promotion == chess.QUEEN), reverse=True)
            best_match = candidate_moves[0][1]
            self.push_move(best_match)
            return best_match

        # Si cambiaron casillas y no coincide con ninguna jugada legal, emitir desincronización
        if len(changed_squares) >= 2:
            self._is_synced = False
            self.desync_detected.emit(
                f"Cambio visual detectado en {changed_squares[:4]} no coincide con ninguna jugada legal."
            )

        return None

    def _get_castling_rook_squares(self, move: chess.Move) -> Tuple[str, str]:
        """Retorna (rook_from_square_name, rook_to_square_name) para un enroque."""
        if move == chess.Move.from_uci("e1g1"):
            return "h1", "f1"
        elif move == chess.Move.from_uci("e1c1"):
            return "a1", "d1"
        elif move == chess.Move.from_uci("e8g8"):
            return "h8", "f8"
        elif move == chess.Move.from_uci("e8c8"):
            return "a8", "d8"
        return "", ""

    def _check_game_termination(self) -> None:
        """Verifica si la partida ha finalizado por jaque mate o tablas."""
        if self._board.is_checkmate():
            result = "0-1" if self._board.turn == chess.WHITE else "1-0"
            self.game_over.emit(result)
        elif self._board.is_stalemate():
            self.game_over.emit("1/2-1/2 (Ahogado)")
        elif self._board.is_insufficient_material():
            self.game_over.emit("1/2-1/2 (Material insuficiente)")
        elif self._board.can_claim_fifty_moves():
            self.game_over.emit("1/2-1/2 (Regla de 50 jugadas)")
        elif self._board.can_claim_threefold_repetition():
            self.game_over.emit("1/2-1/2 (Triple repetición)")

    def get_pgn_text(self) -> str:
        """Genera el texto de la partida en formato PGN estándar."""
        import chess.pgn
        game = chess.pgn.Game.from_board(self._board)
        exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
        return game.accept(exporter)
