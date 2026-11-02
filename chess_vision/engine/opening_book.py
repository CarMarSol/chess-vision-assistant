"""
Módulo de Base de Aperturas (Opening Book) en formato Polyglot (.bin).
Soporta lectura con chess.polyglot y compilador programático integrado
para las principales líneas teóricas del ajedrez.
"""

from __future__ import annotations
import os
import sys
import struct
from typing import Dict, List, Optional, Tuple, Set
import chess
import chess.polyglot


def get_default_book_path() -> str:
    """Resuelve la ruta de openings.bin soportando entornos congelados con PyInstaller."""
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        cand1 = os.path.join(exe_dir, "data", "openings.bin")
        if os.path.isfile(cand1):
            return cand1
        if hasattr(sys, "_MEIPASS"):
            cand2 = os.path.join(sys._MEIPASS, "data", "openings.bin")
            if os.path.isfile(cand2):
                return cand2
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "openings.bin"))


DEFAULT_BOOK_PATH = get_default_book_path()

# Catálogo exhaustivo de aperturas teóricas estándar (SAN)
CURATED_OPENINGS: Dict[str, List[List[str]]] = {
    "Apertura Ruy Lopez (Española)": [
        ["e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7", "Re1", "b5", "Bb3", "d6", "c3", "O-O"],
        ["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6", "O-O", "Nxe4", "d4", "Nd6", "Bxc6", "dxc6", "dxe5", "Nf5"],
        ["e4", "e5", "Nf3", "Nc6", "Bb5", "d6", "d4", "Bd7", "Nc3", "Nf6"]
    ],
    "Apertura Italiana (Giuoco Piano)": [
        ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "c3", "Nf6", "d3", "d6", "O-O", "O-O"],
        ["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6", "d3", "Bc5", "c3", "O-O"],
        ["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5", "b4", "Bxb4", "c3", "Ba5"]  # Gambito Evans
    ],
    "Defensa Siciliana": [
        ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6", "Be3", "e5"],  # Najdorf
        ["e4", "c5", "Nf3", "Nc6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "e5"],               # Sveshnikov
        ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "g6", "Be3", "Bg7"],  # Dragón
        ["e4", "c5", "Nf3", "e6", "d4", "cxd4", "Nxd4", "a6", "Bd3", "Nf6"],                # Kan
        ["e4", "c5", "c3", "Nf6", "e5", "Nd5", "d4", "cxd4"]                                # Alapin
    ],
    "Defensa Francesa": [
        ["e4", "e6", "d4", "d5", "Nc3", "Nf6", "Bg5", "Be7", "e5", "Nfd7"],                 # Clásica
        ["e4", "e6", "d4", "d5", "e5", "c5", "c3", "Nc6", "Nf3", "Qb6"],                    # Avance
        ["e4", "e6", "d4", "d5", "Nd2", "Nf6", "e5", "Nfd7", "Bd3", "c5"]                   # Tarrasch
    ],
    "Defensa Caro-Kann": [
        ["e4", "c6", "d4", "d5", "Nc3", "dxe4", "Nxe4", "Bf5", "Ng3", "Bg6", "h4", "h6"],   # Clásica
        ["e4", "c6", "d4", "d5", "e5", "Bf5", "Nf3", "e6", "Be2", "c5"],                    # Avance
        ["e4", "c6", "d4", "d5", "exd5", "cxd5", "Bd3", "Nc6", "c3"]                        # Cambio
    ],
    "Gambito de Dama": [
        ["d4", "d5", "c4", "e6", "Nc3", "Nf6", "Bg5", "Be7", "e3", "O-O", "Nf3", "h6"],     # Declinado (Ortodoxa)
        ["d4", "d5", "c4", "c6", "Nf3", "Nf6", "Nc3", "dxc4", "a4", "Bf5"],                 # Defensa Eslava
        ["d4", "d5", "c4", "dxc4", "Nf3", "Nf6", "e3", "e6", "Bxc4", "c5", "O-O", "a6"]    # Aceptado
    ],
    "Defensa India de Rey": [
        ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "Nf3", "O-O", "Be2", "e5", "O-O", "Nc6", "d5", "Ne7"], # Clásica
        ["d4", "Nf6", "c4", "g6", "Nc3", "Bg7", "e4", "d6", "f3", "O-O", "Be3", "e5"]       # Samisch
    ],
    "Defensa Grunfeld": [
        ["d4", "Nf6", "c4", "g6", "Nc3", "d5", "cxd5", "Nxd5", "e4", "Nxc3", "bxc3", "Bg7"]
    ],
    "Defensa Nimzoindia": [
        ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4", "e3", "O-O", "Bd3", "d5", "Nf3", "c5"]
    ],
    "Apertura Inglesa": [
        ["c4", "e5", "Nc3", "Nf6", "Nf3", "Nc6", "g3", "d5", "cxd5", "Nxd5"],
        ["c4", "c5", "Nc3", "Nc6", "g3", "g6", "Bg2", "Bg7", "Nf3", "Nf6"]
    ],
    "Apertura Reti": [
        ["Nf3", "d5", "c4", "c6", "b3", "Nf6", "g3", "Bf5", "Bg2", "e6", "O-O", "Be7"]
    ],
    "Defensa Escandinava": [
        ["e4", "d5", "exd5", "Qxd5", "Nc3", "Qa5", "d4", "Nf6", "Nf3", "c6"]
    ]
}


def encode_polyglot_move(board: chess.Board, move: chess.Move) -> int:
    """Codifica un movimiento chess.Move al formato entero de 16 bits de Polyglot."""
    to_sq = move.to_square & 0x3F
    from_sq = (move.from_square & 0x3F) << 6

    # Promoción: 1 = Caballo, 2 = Alfil, 3 = Torre, 4 = Dama
    if move.promotion:
        promo_code = (move.promotion - 1) & 0x7
        promo_part = promo_code << 12
    else:
        promo_part = 0

    return from_sq | to_sq | promo_part


def compile_polyglot_book(
    output_path: str = DEFAULT_BOOK_PATH,
    openings: Optional[Dict[str, List[List[str]]]] = None
) -> int:
    """
    Compila un libro Polyglot .bin a partir de las variantes teóricas.
    Garantiza que las entradas estén perfectamente ordenadas por Zobrist key.
    Retorna la cantidad de entradas compiladas.
    """
    catalog = openings or CURATED_OPENINGS
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # Registro de entradas: list of (key, raw_move, weight, learn)
    entries: List[Tuple[int, int, int, int]] = []
    seen: Set[Tuple[int, int]] = set()

    for opening_name, variations in catalog.items():
        for line in variations:
            board = chess.Board()
            weight = 100
            for san_move in line:
                try:
                    move = board.parse_san(san_move)
                except ValueError:
                    break

                key = chess.polyglot.zobrist_hash(board)
                raw_mv = encode_polyglot_move(board, move)

                if (key, raw_mv) not in seen:
                    seen.add((key, raw_mv))
                    entries.append((key, raw_mv, weight, 0))

                board.push(move)
                weight = max(10, weight - 2)

    # El estándar Polyglot requiere OBLIGATORIAMENTE que las entradas estén ordenadas por key ascendente
    entries.sort(key=lambda e: e[0])

    # Escribir el archivo binario
    with open(output_path, "wb") as f:
        for key, raw_move, weight, learn in entries:
            packed = chess.polyglot.ENTRY_STRUCT.pack(key, raw_move, weight, learn)
            f.write(packed)

    return len(entries)


class OpeningBook:
    """
    Gestor del libro de aperturas Polyglot (.bin).
    Permite consultar rápidamente si una posición o movimiento pertenece a la teoría.
    """
    _instance: Optional[OpeningBook] = None

    def __init__(self, book_path: str = DEFAULT_BOOK_PATH):
        self.book_path = os.path.abspath(book_path)
        self._name_map: Dict[int, str] = {}
        self._reader: Optional[chess.polyglot.MemoryMappedReader] = None

        self._ensure_book_exists()
        self._build_name_map()
        self._open_reader()

    @classmethod
    def get_default(cls) -> OpeningBook:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_book_exists(self) -> None:
        """Si el archivo binario no existe o está vacío, compilarlo inmediatamente."""
        if not os.path.isfile(self.book_path) or os.path.getsize(self.book_path) == 0:
            compile_polyglot_book(self.book_path)

    def _open_reader(self) -> None:
        """Abre el archivo Polyglot con MemoryMappedReader."""
        if os.path.isfile(self.book_path) and os.path.getsize(self.book_path) > 0:
            try:
                self._reader = chess.polyglot.open_reader(self.book_path)
            except Exception as e:
                print(f"[WARN] No se pudo mapear {self.book_path}: {e}")
                self._reader = None

    def _build_name_map(self) -> None:
        """Construye un mapa rápido de Zobrist Key -> Nombre de Apertura."""
        for opening_name, variations in CURATED_OPENINGS.items():
            for line in variations:
                board = chess.Board()
                for san in line:
                    try:
                        mv = board.parse_san(san)
                    except ValueError:
                        break
                    key = chess.polyglot.zobrist_hash(board)
                    if key not in self._name_map:
                        self._name_map[key] = opening_name
                    board.push(mv)

    def is_book_position(self, board: chess.Board) -> bool:
        """Retorna True si la posición actual se encuentra en el libro de aperturas."""
        if self._reader is None:
            return False
        try:
            return self._reader.get(board) is not None
        except Exception:
            return False

    def is_book_move(self, board: chess.Board, move: chess.Move) -> Tuple[bool, Optional[str]]:
        """Retorna (True, nombre_apertura) si el movimiento específico es una continuación teórica del libro."""
        if self._reader is None:
            return False, None
        try:
            for entry in self._reader.find_all(board):
                if entry.move == move:
                    name = self.get_opening_name(board)
                    return True, name
            return False, None
        except Exception:
            return False, None

    def get_book_moves(self, board: chess.Board) -> List[chess.Move]:
        """Retorna la lista de movimientos teóricos para la posición actual."""
        if self._reader is None:
            return []
        try:
            return [entry.move for entry in self._reader.find_all(board)]
        except Exception:
            return []

    def get_opening_name(self, board: chess.Board) -> Optional[str]:
        """Retorna el nombre descriptivo de la apertura para la posición."""
        key = chess.polyglot.zobrist_hash(board)
        return self._name_map.get(key)

    def close(self) -> None:
        if self._reader:
            try:
                self._reader.close()
            except Exception:
                pass
            self._reader = None


def get_opening_book() -> OpeningBook:
    """Helper global para acceder a la instancia singleton de OpeningBook."""
    return OpeningBook.get_default()
