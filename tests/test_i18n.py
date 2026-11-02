"""Language preference, catalog integrity and UI behavior without a live engine."""

import json
import os
from string import Formatter
from unittest.mock import MagicMock

import chess
import pytest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from chess_vision.config import AppConfig, BoardConfig, get_default_stockfish_path
from chess_vision.i18n import (
    LANGUAGES, TRANSLATIONS, board_name, get_language, normalize_language,
    set_language, tr,
)
from chess_vision.ui.board_config_dialog import BoardConfigDialog
from chess_vision.ui.eval_panel import MoveCardWidget
from chess_vision.ui.test_simulation_dialog import PRESET_POSITIONS, SimulationDialog
from chess_vision.engine.evaluator import CandidateMove
from chess_vision.engine.classifier import MoveClassification


@pytest.fixture(autouse=True)
def language_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    set_language("es")
    yield
    set_language("es")


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_language_preference_roundtrip_and_old_settings(tmp_path):
    path = tmp_path / "settings.json"
    config = AppConfig(language="pt-BR")
    assert config.language == "pt"
    assert config.save(str(path))
    assert AppConfig.load(str(path)).language == "pt"
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["language"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert AppConfig.load(str(path)).language == "es"
    data["language"] = "unknown-language"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert AppConfig.load(str(path)).language == "es"


@pytest.mark.parametrize("code", LANGUAGES)
def test_catalogs_preserve_every_format_field(code):
    fields = lambda text: {field for _, field, _, _ in Formatter().parse(text) if field}
    for source, target in TRANSLATIONS[code].items():
        assert fields(source) == fields(target), (code, source)
    set_language(code)
    assert tr("● Jugada: {value0}{value1}", value0="Nf3", value1="").endswith("Nf3")
    assert tr(chess.STARTING_FEN) == chess.STARTING_FEN
    assert tr("New untranslated message") == "New untranslated message"
    assert board_name("My study board") == "My study board"
    assert board_name("Tablero 2").endswith("2")


def test_invalid_language_falls_back_to_spanish():
    assert normalize_language("en_US") == "en"
    assert set_language(None) == "es"
    assert tr("Guardar Cambios") == "Guardar Cambios"


@pytest.mark.parametrize("code,save_text", [
    ("en", "Save changes"), ("fr", "Enregistrer"),
    ("pt", "Salvar alterações"), ("de", "Änderungen speichern"),
])
def test_translated_settings_keep_internal_values(qapp, code, save_text):
    set_language(code)
    config = BoardConfig(name="My custom board")
    dialog = BoardConfigDialog(config)
    assert dialog.btn_save.text() == save_text
    assert "My custom board" in dialog.windowTitle()
    for index, effort in enumerate(("low", "medium", "high", "very_high")):
        depth, _ = BoardConfig(effort=effort).get_effort_depth_and_time()
        assert str(depth) in dialog.cmb_effort.itemText(index)
    dialog.cmb_orientation.setCurrentIndex(2)
    dialog.cmb_style.setCurrentIndex(1)
    dialog.cmb_display_mode.setCurrentIndex(1)
    dialog._save_and_accept()
    assert (config.orientation, config.style, config.display_mode) == ("black", "aggressive", "overlay")
    dialog.close()


def test_translated_simulator_preset_uses_fen_data(qapp):
    set_language("en")
    dialog = SimulationDialog()
    assert dialog.cmb_presets.itemText(1) == "Opera mate (Paul Morphy)"
    dialog.cmb_presets.setCurrentIndex(1)
    assert dialog._board.fen() == chess.Board(PRESET_POSITIONS["Mate de la Ópera (Paul Morphy)"]).fen()
    dialog.close()


def test_move_card_translates_classification_without_changing_notation(qapp):
    set_language("en")
    card = MoveCardWidget(rank=1)
    move = CandidateMove(
        rank=1, move=chess.Move.from_uci("g1f3"), san="Nf3", uci="g1f3",
        classification=MoveClassification(
            category="best", label="Mejor jugada", symbol="★", badge_color="#10b981",
            delta_cp=0.0, win_rate_loss=0.0,
            description="La jugada más precisa según el motor Stockfish.",
        ),
    )
    card.set_candidate(move, chess.WHITE)
    assert card.lbl_san.text() == "Nf3"
    assert "Best move" in card.lbl_badge.text()
    card.close()


def test_language_selector_saves_without_resetting_board(qapp, monkeypatch):
    from chess_vision.ui import main_window
    monkeypatch.setattr(main_window, "StockfishManager", MagicMock())
    notice = MagicMock()
    monkeypatch.setattr(main_window.QMessageBox, "information", notice)
    config = AppConfig(language="en")
    window = main_window.MainWindow(config)
    board = window._board_widgets["board_1"]
    board.sync_mgr.push_move(chess.Move.from_uci("e2e4"))
    before = board.sync_mgr.board.fen()
    window.cmb_language.setCurrentIndex(window.cmb_language.findData("de"))
    assert config.language == "de"
    assert AppConfig.load().language == "de"
    assert get_language() == "en"
    assert board.sync_mgr.board.fen() == before
    assert "Analyze all" in window.btn_refresh.text()
    assert notice.call_count == 1
    window.close()


def test_stockfish_path_uses_path_without_personal_fallback(monkeypatch, tmp_path):
    from chess_vision import config
    expected = str(tmp_path / "stockfish.exe")
    monkeypatch.setattr(config.shutil, "which", lambda executable: expected)
    monkeypatch.setattr(config.os.path, "isfile", lambda path: path == expected)
    assert get_default_stockfish_path() == expected


def test_language_save_error_keeps_previous_preference(qapp, monkeypatch):
    from chess_vision.ui import main_window
    monkeypatch.setattr(main_window, "StockfishManager", MagicMock())
    warning = MagicMock()
    monkeypatch.setattr(main_window.QMessageBox, "warning", warning)
    config = AppConfig(language="es")
    monkeypatch.setattr(config, "save", lambda *args: False)
    window = main_window.MainWindow(config)
    window.cmb_language.setCurrentIndex(window.cmb_language.findData("fr"))
    assert config.language == "es"
    assert window.cmb_language.currentData() == "es"
    assert warning.call_count == 1
    window.close()
