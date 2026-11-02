"""
Módulo de Configuración y Persistencia para Chess Vision Assistant.
Soporta configuración granular por tablero (1 a 4 tableros) y parámetros globales del motor.
"""

from __future__ import annotations
import os
import sys
import json
import shutil
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple, Dict, Any
from chess_vision.i18n import normalize_language


def get_default_stockfish_path() -> str:
    """Busca y resuelve el ejecutable de Stockfish en rutas locales, empaquetadas y estándar."""
    candidates = []

    # 1. Soporte para ejecutables congelados con PyInstaller
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        candidates.append(os.path.join(exe_dir, "bin", "stockfish.exe"))
        candidates.append(os.path.join(exe_dir, "stockfish.exe"))
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "bin", "stockfish.exe"))
            candidates.append(os.path.join(sys._MEIPASS, "stockfish.exe"))

    # 2. Ruta del proyecto y ejecutables instalados en PATH.
    candidates.extend([
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "bin", "stockfish.exe")),
    ])
    installed_engine = shutil.which("stockfish.exe") or shutil.which("stockfish")
    if installed_engine:
        candidates.append(installed_engine)

    for path in candidates:
        if os.path.isfile(path):
            return os.path.abspath(path)
    return candidates[0]


@dataclass
class BoardConfig:
    """Configuración individual de un tablero analizado."""
    id: str = "board_1"
    name: str = "Tablero 1"
    region: Optional[Tuple[int, int, int, int]] = None  # (x, y, width, height)
    orientation: str = "auto"  # "auto", "white", "black"
    elo: int = 2500  # Rango: 700 - 2800
    style: str = "balanced"  # "balanced", "aggressive", "defensive", "tactical", "positional"
    effort: str = "medium"  # "low", "medium", "high", "very_high"
    display_mode: str = "independent"  # "independent" o "overlay"
    margin_pct: float = 0.01  # Margen externo del tablero (1%)
    cell_inset_pct: float = 0.08  # Margen interior de cada casilla (8%)
    show_arrows: bool = True
    show_eval_bar: bool = True
    auto_scan: bool = True
    scan_interval_ms: int = 80
    board_theme: str = "green"  # "green" (Chess.com), "wood" (Lichess), "blue" (Clásico), "mono" (Monocromo)
    enable_target_accuracy: bool = True  # Activación de recomendación adaptativa por precisión objetivo
    target_accuracy: int = 80  # Rango: 60 - 98 (%)
    target_accuracy_tolerance: int = 5  # Margen de tolerancia (+- 5%)
    enable_subtle_loss: bool = False  # Modo derrota sutil (perder jugando bien)
    subtle_loss_move: int = 20  # Jugada objetivo para inducir error (10 - 45)
    subtle_loss_severity: str = "moderate"  # "subtle", "moderate", "slow_decline"
    arrow_colors: Dict[str, str] = field(default_factory=lambda: {
        "best": "#26C2A3",       # Cian / Verde menta brillante
        "alternative_1": "#1B8FD8", # Azul elegante
        "alternative_2": "#FFA500", # Naranja / Ámbar
        "adaptive": "#39FF14",    # Verde Neón Fosforito (Recomendado)
        "brilliant": "#00CED1",
        "great": "#1B8FD8",
        "inaccuracy": "#F7C631",
        "mistake": "#FFA500",
        "blunder": "#FA412D"
    })

    def get_effort_depth_and_time(self) -> Tuple[int, float]:
        """Retorna (depth, max_time_seconds) según el nivel de esfuerzo."""
        mapping = {
            "low": (8, 0.08),
            "medium": (12, 0.20),
            "high": (16, 0.50),
            "very_high": (20, 1.20)
        }
        return mapping.get(self.effort.lower(), (12, 0.20))

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.region is not None:
            data["region"] = list(self.region)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BoardConfig:
        clean_data = dict(data)
        if "region" in clean_data and clean_data["region"] is not None:
            clean_data["region"] = tuple(clean_data["region"])
        if "display_mode" not in clean_data or clean_data["display_mode"] not in ("independent", "overlay"):
            clean_data["display_mode"] = clean_data.get("display_mode", "independent") or "independent"
        if "subtle_loss_severity" in clean_data and clean_data["subtle_loss_severity"] not in ("subtle", "moderate", "slow_decline"):
            clean_data["subtle_loss_severity"] = "moderate"
        if "subtle_loss_move" in clean_data:
            try:
                clean_data["subtle_loss_move"] = max(10, min(45, int(clean_data["subtle_loss_move"])))
            except Exception:
                clean_data["subtle_loss_move"] = 20
        valid_fields = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in clean_data.items() if k in valid_fields}
        return cls(**filtered)


@dataclass
class AppConfig:
    """Configuración global de la aplicación."""
    active_board_count: int = 1  # 1 a 4 tableros
    stockfish_path: str = field(default_factory=get_default_stockfish_path)
    threads_per_board: int = 2
    hash_per_board_mb: int = 64
    theme: str = "dark"
    language: str = "es"
    boards: List[BoardConfig] = field(default_factory=lambda: [
        BoardConfig(id="board_1", name="Tablero 1"),
        BoardConfig(id="board_2", name="Tablero 2"),
        BoardConfig(id="board_3", name="Tablero 3"),
        BoardConfig(id="board_4", name="Tablero 4"),
    ])

    def __post_init__(self) -> None:
        self.language = normalize_language(self.language)

    @classmethod
    def get_config_file_path(cls) -> str:
        """Determina la ruta preferida para guardar el archivo de configuración."""
        appdata = os.environ.get("APPDATA")
        if appdata:
            dir_path = os.path.join(appdata, "ChessVisionAssistant")
            try:
                os.makedirs(dir_path, exist_ok=True)
                return os.path.join(dir_path, "settings.json")
            except OSError:
                pass
        # Fallback local en el directorio de trabajo
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "settings.json"))

    def save(self, filepath: Optional[str] = None) -> bool:
        """Guarda la configuración actual en formato JSON."""
        target = filepath or self.get_config_file_path()
        try:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            payload = {
                "active_board_count": self.active_board_count,
                "stockfish_path": self.stockfish_path,
                "threads_per_board": self.threads_per_board,
                "hash_per_board_mb": self.hash_per_board_mb,
                "theme": self.theme,
                "language": normalize_language(self.language),
                "boards": [b.to_dict() for b in self.boards]
            }
            with open(target, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[ERROR] Error al guardar configuración en {target}: {e}")
            return False

    @classmethod
    def load(cls, filepath: Optional[str] = None) -> AppConfig:
        """Carga la configuración desde JSON o crea una predeterminada si no existe."""
        target = filepath or cls.get_config_file_path()
        if not os.path.isfile(target):
            # Intentar fallback local si no existe en AppData
            local_fallback = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "settings.json"))
            if os.path.isfile(local_fallback):
                target = local_fallback
            else:
                cfg = cls()
                cfg.save(target)
                return cfg

        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)

            boards_raw = data.get("boards", [])
            boards = []
            for i, b_data in enumerate(boards_raw):
                try:
                    boards.append(BoardConfig.from_dict(b_data))
                except Exception:
                    boards.append(BoardConfig(id=f"board_{i+1}", name=f"Tablero {i+1}"))

            # Asegurar al menos 4 tableros configurados
            while len(boards) < 4:
                idx = len(boards) + 1
                boards.append(BoardConfig(id=f"board_{idx}", name=f"Tablero {idx}"))

            cfg = cls(
                active_board_count=max(1, min(4, int(data.get("active_board_count", 1)))),
                stockfish_path=str(data.get("stockfish_path", get_default_stockfish_path())),
                threads_per_board=int(data.get("threads_per_board", 2)),
                hash_per_board_mb=int(data.get("hash_per_board_mb", 64)),
                theme=str(data.get("theme", "dark")),
                language=normalize_language(data.get("language", "es")),
                boards=boards
            )

            # Validar existencia de Stockfish, si no es válido restablecer al default detectado
            if not os.path.isfile(cfg.stockfish_path):
                cfg.stockfish_path = get_default_stockfish_path()

            return cfg
        except Exception as e:
            print(f"[WARN] Error al cargar configuración desde {target}: {e}. Usando predeterminada.")
            return cls()
