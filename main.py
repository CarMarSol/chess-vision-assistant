"""
Punto de Entrada Principal para Chess Vision Assistant.
"""

from __future__ import annotations
import sys
import os
import argparse

# Asegurar que el directorio raíz del proyecto esté en sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from chess_vision.config import AppConfig
from chess_vision.i18n import LANGUAGES, set_language
from chess_vision.ui.main_window import MainWindow
from chess_vision.engine.stockfish_manager import StockfishManager
import chess


def run_engine_test(stockfish_path: str) -> int:
    """Verificación rápida de inicialización del motor Stockfish en modo consola."""
    print("=" * 60)
    print("Chess Vision Assistant - Comprobación de Motor Stockfish")
    print("=" * 60)
    print(f"Ruta de ejecutable: {stockfish_path}")

    if not os.path.isfile(stockfish_path):
        print(f"[ERROR] No se encuentra el archivo en: {stockfish_path}")
        return 1

    try:
        mgr = StockfishManager(engine_path=stockfish_path, threads=2, hash_mb=64)
        board = chess.Board()
        print(f"Posición inicial: {board.fen()}")
        print("Calculando análisis Multi-PV (3 líneas)...")
        analysis = mgr.analyze_sync(board, depth=12, time_limit=0.5, multipv=3)
        print("\nResultado del análisis:")
        print(f"- Evaluación barra: {analysis.evaluation_bar_score:+.2f}")
        for c in analysis.top_moves:
            print(f"  #{c.rank}: {c.san:<8} Score: {c.display_score:<6} WinRate: {c.win_rate:.1f}% [{c.classification.label}] ({c.classification.category})")
        mgr.quit()
        print("\n[OK] Motor Stockfish respondió correctamente.")
        return 0
    except Exception as e:
        print(f"[ERROR] Fallo al evaluar con Stockfish: {e}")
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chess Vision Assistant - Asistente de Visión y Análisis de Ajedrez en Tiempo Real"
    )
    parser.add_argument(
        "--test-engine", action="store_true", help="Comprueba el motor Stockfish en consola sin GUI"
    )
    parser.add_argument(
        "--boards", type=int, choices=[1, 2, 3, 4], help="Número de tableros simultáneos a mostrar (1 a 4)"
    )
    parser.add_argument(
        "--stockfish-path", type=str, help="Ruta personalizada al binario de Stockfish"
    )
    parser.add_argument(
        "--language", choices=list(LANGUAGES), help="Idioma de interfaz: es, en, fr, pt, de"
    )

    args = parser.parse_args()

    cfg = AppConfig.load()
    if args.stockfish_path:
        cfg.stockfish_path = os.path.abspath(args.stockfish_path)
    if args.boards:
        cfg.active_board_count = args.boards
    if args.language:
        cfg.language = args.language
    set_language(cfg.language)

    if args.test_engine:
        return run_engine_test(cfg.stockfish_path)

    # Iniciar aplicación Qt
    # Ajustes para escalado de alta densidad (HiDPI)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Chess Vision Assistant")
    app.setOrganizationName("ChessVision")

    window = MainWindow(config=cfg)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
