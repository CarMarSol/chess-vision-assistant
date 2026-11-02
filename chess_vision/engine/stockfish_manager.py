"""
Gestor de Stockfish asíncrono y tolerante a fallos para Chess Vision Assistant.
Maneja cola de solicitudes concurrentes por tablero, cancelación de análisis obsoletos,
y control óptimo de CPU.
"""

from __future__ import annotations
import os
import sys
import threading
from typing import Dict, Optional, Callable, Any, List
from concurrent.futures import ThreadPoolExecutor
import chess
import chess.engine
from PySide6.QtCore import QObject, Signal

from chess_vision.config import get_default_stockfish_path
from chess_vision.engine.evaluator import Evaluator, PositionAnalysis
from chess_vision.engine.styles import EloManager


class StockfishManager(QObject):
    """
    Controlador centralizado del motor Stockfish con interfaz de señales Qt.
    Soporta múltiples tableros simultáneos sin bloqueo de la UI.
    """
    analysis_ready = Signal(str, object)  # (board_id, PositionAnalysis)
    engine_status_changed = Signal(bool, str)  # (is_ready, message)
    error_occurred = Signal(str, str)  # (board_id, error_message)

    def __init__(
        self,
        engine_path: Optional[str] = None,
        threads: int = 2,
        hash_mb: int = 64,
        parent: Optional[QObject] = None
    ):
        super().__init__(parent)
        self.engine_path = engine_path or get_default_stockfish_path()
        self.threads = max(1, threads)
        self.hash_mb = max(16, hash_mb)

        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="StockfishWorker")

        # Registro de solicitud activa más reciente por tablero: board_id -> int (request_id)
        self._latest_request_id: Dict[str, int] = {}
        self._request_counter = 0

        self._is_running = True
        self.init_engine()

    def init_engine(self) -> bool:
        """Inicializa o reinicia el proceso del motor Stockfish."""
        with self._lock:
            if self._engine is not None:
                try:
                    self._engine.quit()
                except Exception:
                    pass
                self._engine = None

            if not os.path.isfile(self.engine_path):
                msg = f"No se encontró el ejecutable de Stockfish en: {self.engine_path}"
                self.engine_status_changed.emit(False, msg)
                return False

            try:
                self._engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
                options = {
                    "Threads": self.threads,
                    "Hash": self.hash_mb
                }
                self._engine.configure(options)
                engine_name = self._engine.id.get("name", "Stockfish")
                self.engine_status_changed.emit(True, f"Motor listo: {engine_name}")
                return True
            except Exception as e:
                self._engine = None
                self.engine_status_changed.emit(False, f"Error al inicializar Stockfish: {e}")
                return False

    def restart(self) -> bool:
        """Reinicia el motor en caso de desincronización o caída."""
        return self.init_engine()

    def set_threads_and_hash(self, threads: int, hash_mb: int) -> None:
        """Actualiza la configuración de hilos y memoria hash del motor."""
        self.threads = max(1, threads)
        self.hash_mb = max(16, hash_mb)
        with self._lock:
            if self._engine:
                try:
                    self._engine.configure({
                        "Threads": self.threads,
                        "Hash": self.hash_mb
                    })
                except Exception:
                    pass

    def analyze_sync(
        self,
        board: chess.Board,
        depth: int = 14,
        time_limit: float = 0.35,
        multipv: int = 4,
        style: str = "balanced",
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
        Ejecuta un análisis sincrónico Multi-PV (útil para pruebas unitarias o cálculos directos).
        """
        with self._lock:
            if not self._engine:
                if not self.init_engine() or not self._engine:
                    raise RuntimeError("Motor Stockfish no disponible.")

            # Ajustar opciones de Elo
            elo_opts = EloManager.get_engine_options(elo)
            try:
                self._engine.configure(elo_opts)
            except Exception:
                pass

            # Ajuste de profundidad para Elo bajo
            actual_depth = EloManager.adjust_search_depth_for_low_elo(elo, depth)

            limit = chess.engine.Limit(depth=actual_depth, time=time_limit)
            infos = self._engine.analyse(board, limit, multipv=multipv)

            # Si analyse devuelve una lista de infos (multipv > 1)
            if isinstance(infos, dict):
                infos_list = [infos]
            else:
                infos_list = list(infos)

            return Evaluator.process_engine_multipv_results(
                board,
                infos_list,
                style=style,
                elo=elo,
                target_accuracy=target_accuracy,
                current_accuracy=current_accuracy,
                enable_adaptive=enable_adaptive,
                adaptive_tolerance=adaptive_tolerance,
                enable_subtle_loss=enable_subtle_loss,
                subtle_loss_move=subtle_loss_move,
                subtle_loss_severity=subtle_loss_severity
            )

    def request_analysis_async(
        self,
        board_id: str,
        board: chess.Board,
        depth: int = 14,
        time_limit: float = 0.35,
        multipv: int = 4,
        style: str = "balanced",
        elo: int = 2500,
        target_accuracy: Optional[int] = 80,
        current_accuracy: Optional[float] = None,
        enable_adaptive: bool = True,
        adaptive_tolerance: int = 5,
        enable_subtle_loss: bool = False,
        subtle_loss_move: int = 20,
        subtle_loss_severity: str = "moderate"
    ) -> int:
        """
        Encola un análisis asíncrono para un tablero específico.
        Cancela automáticamente cualquier solicitud anterior pendiente de ese tablero.
        Retorna el id de solicitud generado.
        """
        self._request_counter += 1
        req_id = self._request_counter
        self._latest_request_id[board_id] = req_id

        # Clonar tablero para aislamiento de hilos
        board_clone = board.copy()

        self._executor.submit(
            self._worker_run_analysis,
            board_id,
            req_id,
            board_clone,
            depth,
            time_limit,
            multipv,
            style,
            elo,
            target_accuracy,
            current_accuracy,
            enable_adaptive,
            adaptive_tolerance,
            enable_subtle_loss,
            subtle_loss_move,
            subtle_loss_severity
        )
        return req_id

    def _worker_run_analysis(
        self,
        board_id: str,
        req_id: int,
        board: chess.Board,
        depth: int,
        time_limit: float,
        multipv: int,
        style: str,
        elo: int,
        target_accuracy: Optional[int] = 80,
        current_accuracy: Optional[float] = None,
        enable_adaptive: bool = True,
        adaptive_tolerance: int = 5,
        enable_subtle_loss: bool = False,
        subtle_loss_move: int = 20,
        subtle_loss_severity: str = "moderate"
    ) -> None:
        """Trabajo de fondo ejecutado en el hilo de análisis."""
        # Si ya hay una solicitud más nueva para este tablero, abortar inmediatamente
        if self._latest_request_id.get(board_id) != req_id:
            return

        try:
            analysis = self.analyze_sync(
                board=board,
                depth=depth,
                time_limit=time_limit,
                multipv=multipv,
                style=style,
                elo=elo,
                target_accuracy=target_accuracy,
                current_accuracy=current_accuracy,
                enable_adaptive=enable_adaptive,
                adaptive_tolerance=adaptive_tolerance,
                enable_subtle_loss=enable_subtle_loss,
                subtle_loss_move=subtle_loss_move,
                subtle_loss_severity=subtle_loss_severity
            )
            # Volver a verificar que la solicitud siga siendo la más reciente tras el cálculo
            if self._latest_request_id.get(board_id) == req_id:
                self.analysis_ready.emit(board_id, analysis)
        except Exception as e:
            if self._latest_request_id.get(board_id) == req_id:
                self.error_occurred.emit(board_id, str(e))

    def quit(self) -> None:
        """Libera los recursos del motor y cierra los hilos."""
        self._is_running = False
        self._executor.shutdown(wait=False, cancel_futures=True)
        with self._lock:
            if self._engine:
                try:
                    self._engine.quit()
                except Exception:
                    pass
                self._engine = None
