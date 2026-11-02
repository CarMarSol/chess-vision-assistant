"""
Diálogo de configuración individual de tablero para Chess Vision Assistant.
Permite personalizar Elo, estilo de juego, esfuerzo, orientación y calibración visual.
"""

from __future__ import annotations
from chess_vision.i18n import tr, board_name
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QSlider, QSpinBox, QCheckBox, QPushButton, QLabel, QGroupBox, QWidget
)
from chess_vision.config import BoardConfig
from chess_vision.ui.theme import Theme


class BoardConfigDialog(QDialog):
    """
    Diálogo para editar la configuración de un tablero.
    """

    def __init__(self, config: BoardConfig, parent: Optional[QWidget] = None, theme: str = "dark"):
        super().__init__(parent)
        self.config = config
        self._theme = theme
        self.setWindowTitle(tr('Configuración: {value0}', value0=board_name(config.name)))
        self.setMinimumWidth(440)

        t = Theme.get_tokens(theme)
        self.setStyleSheet(f"""
            {Theme.get_application_stylesheet(theme)}
            QDialog {{
                background-color: {t["bg_dialog"]};
                color: {t["text_primary"]};
            }}
            QGroupBox {{
                background-color: {t["bg_surface"]};
            }}
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)

        # 1. Grupo General
        grp_general = QGroupBox(tr("General"))
        layout_gen = QFormLayout(grp_general)

        self.txt_name = QLineEdit(config.name)
        layout_gen.addRow(tr("Nombre:"), self.txt_name)

        self.cmb_orientation = QComboBox()
        self.cmb_orientation.addItems([tr("Auto (Detección automática)"), tr("Blancas abajo"), tr("Negras abajo")])
        ori_map = {"auto": 0, "white": 1, "black": 2}
        self.cmb_orientation.setCurrentIndex(ori_map.get(config.orientation.lower(), 0))
        layout_gen.addRow(tr("Orientación:"), self.cmb_orientation)

        # Tema visual del tablero
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItems([tr("Verde Chess.com"), tr("Madera Lichess"), tr("Azul Clásico"), tr("Monocromo")])
        theme_map = {"green": 0, "wood": 1, "blue": 2, "mono": 3}
        self.cmb_theme.setCurrentIndex(theme_map.get(getattr(config, "board_theme", "green"), 0))
        layout_gen.addRow(tr("Estilo de tablero:"), self.cmb_theme)

        main_layout.addWidget(grp_general)

        # 2. Grupo Motor & IA
        grp_engine = QGroupBox(tr("Motor & Estilo de Juego"))
        layout_eng = QFormLayout(grp_engine)

        # Elo Slider & SpinBox
        elo_layout = QHBoxLayout()
        self.slider_elo = QSlider(Qt.Orientation.Horizontal)
        self.slider_elo.setRange(700, 2800)
        self.slider_elo.setValue(config.elo)
        self.spin_elo = QSpinBox()
        self.spin_elo.setRange(700, 2800)
        self.spin_elo.setValue(config.elo)
        self.slider_elo.valueChanged.connect(self.spin_elo.setValue)
        self.spin_elo.valueChanged.connect(self.slider_elo.setValue)
        elo_layout.addWidget(self.slider_elo)
        elo_layout.addWidget(self.spin_elo)
        layout_eng.addRow(tr("Nivel Elo:"), elo_layout)

        # Estilo de juego
        self.cmb_style = QComboBox()
        self.cmb_style.addItems([tr("Equilibrado (Standard)"), tr("Agresivo (Ataque)"), tr("Defensivo (Sólido)"), tr("Táctico (Dinámico)"), tr("Posicional (Estratégico)")])
        style_map = {"balanced": 0, "aggressive": 1, "defensive": 2, "tactical": 3, "positional": 4}
        self.cmb_style.setCurrentIndex(style_map.get(config.style.lower(), 0))
        layout_eng.addRow(tr("Estilo de juego:"), self.cmb_style)

        # Esfuerzo de análisis
        self.cmb_effort = QComboBox()
        self.cmb_effort.addItems([tr("Bajo (Rápido, depth 8)"), tr("Medio (Equilibrado, depth 12)"), tr("Alto (Profundo, depth 16)"), tr("Muy alto (Torneo, depth 20)")])
        effort_map = {"low": 0, "medium": 1, "high": 2, "very_high": 3}
        self.cmb_effort.setCurrentIndex(effort_map.get(config.effort.lower(), 1))
        layout_eng.addRow(tr("Esfuerzo de cálculo:"), self.cmb_effort)

        main_layout.addWidget(grp_engine)

        # 3. Grupo Simulación y precisión objetivo
        grp_accuracy = QGroupBox(tr("Simulación y precisión objetivo"))
        layout_acc = QFormLayout(grp_accuracy)

        self.chk_adaptive = QCheckBox(tr("Activar jugada adaptativa por precisión objetivo"))
        self.chk_adaptive.setChecked(getattr(config, "enable_target_accuracy", True))
        layout_acc.addRow(self.chk_adaptive)

        # Selector rápido de perfiles
        self.cmb_acc_profile = QComboBox()
        self.cmb_acc_profile.addItems([
            tr("Personalizado"),
            tr("Club (72%)"),
            tr("Intermedio (80%)"),
            tr("Avanzado (88%)"),
            tr("Maestro (94%)")
        ])
        layout_acc.addRow(tr("Perfil predefinido:"), self.cmb_acc_profile)

        # Precisión objetivo: Slider & SpinBox (60% - 98%)
        target_layout = QHBoxLayout()
        self.slider_target_acc = QSlider(Qt.Orientation.Horizontal)
        self.slider_target_acc.setRange(60, 98)
        self.slider_target_acc.setValue(getattr(config, "target_accuracy", 80))

        self.spin_target_acc = QSpinBox()
        self.spin_target_acc.setRange(60, 98)
        self.spin_target_acc.setSuffix("%")
        self.spin_target_acc.setValue(getattr(config, "target_accuracy", 80))

        self.slider_target_acc.valueChanged.connect(self.spin_target_acc.setValue)
        self.spin_target_acc.valueChanged.connect(self.slider_target_acc.setValue)
        self.spin_target_acc.valueChanged.connect(self._on_target_acc_changed)

        target_layout.addWidget(self.slider_target_acc)
        target_layout.addWidget(self.spin_target_acc)
        layout_acc.addRow(tr("Precisión objetivo:"), target_layout)

        # Conectar selector de perfiles
        self.cmb_acc_profile.currentIndexChanged.connect(self._on_profile_selected)
        self._update_profile_combobox_from_value(getattr(config, "target_accuracy", 80))

        # Toggling enable/disable
        self.chk_adaptive.toggled.connect(self._on_adaptive_toggled)
        self._on_adaptive_toggled(self.chk_adaptive.isChecked())

        main_layout.addWidget(grp_accuracy)

        # 4. Grupo Visualización & Captura
        grp_vis = QGroupBox(tr("Visualización y Captura"))
        layout_vis = QVBoxLayout(grp_vis)

        # Modo de visualización
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel(tr("Modo de visualización:")))
        self.cmb_display_mode = QComboBox()
        self.cmb_display_mode.addItems([
            tr("Tablero independiente (reproducción interna)"),
            tr("Indicaciones superpuestas (overlay sobre pantalla)")
        ])
        mode_idx = 1 if getattr(config, "display_mode", "independent") == "overlay" else 0
        self.cmb_display_mode.setCurrentIndex(mode_idx)
        mode_layout.addWidget(self.cmb_display_mode)
        layout_vis.addLayout(mode_layout)

        self.chk_arrows = QCheckBox(tr("Mostrar flechas tácticas en el tablero"))
        self.chk_arrows.setChecked(config.show_arrows)
        layout_vis.addWidget(self.chk_arrows)

        self.chk_eval_bar = QCheckBox(tr("Mostrar barra de evaluación lateral"))
        self.chk_eval_bar.setChecked(config.show_eval_bar)
        layout_vis.addWidget(self.chk_eval_bar)

        self.chk_auto_scan = QCheckBox(tr("Escaneo automático en tiempo real"))
        self.chk_auto_scan.setChecked(config.auto_scan)
        layout_vis.addWidget(self.chk_auto_scan)

        # Intervalo de escaneo
        int_layout = QHBoxLayout()
        int_layout.addWidget(QLabel(tr("Intervalo de escaneo (ms):")))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(100, 2000)
        self.spin_interval.setSingleStep(50)
        self.spin_interval.setValue(config.scan_interval_ms)
        int_layout.addWidget(self.spin_interval)
        layout_vis.addLayout(int_layout)

        main_layout.addWidget(grp_vis)

        # 4. Botones Guardar / Cancelar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(tr("Cancelar"))
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet(Theme.get_button_style("neutral", self._theme))
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(tr("Guardar Cambios"))
        self.btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_save.setStyleSheet(Theme.get_button_style("primary", self._theme))
        self.btn_save.clicked.connect(self._save_and_accept)
        btn_layout.addWidget(self.btn_save)

        main_layout.addLayout(btn_layout)

    def _on_adaptive_toggled(self, checked: bool) -> None:
        """Habilita o deshabilita los controles de precisión según el checkbox."""
        self.cmb_acc_profile.setEnabled(checked)
        self.slider_target_acc.setEnabled(checked)
        self.spin_target_acc.setEnabled(checked)

    def _on_profile_selected(self, index: int) -> None:
        """Ajusta el slider y spinbox al valor del perfil predefinido."""
        profile_values = {1: 72, 2: 80, 3: 88, 4: 94}
        if index in profile_values:
            val = profile_values[index]
            self.spin_target_acc.blockSignals(True)
            self.slider_target_acc.setValue(val)
            self.spin_target_acc.setValue(val)
            self.spin_target_acc.blockSignals(False)

    def _on_target_acc_changed(self, val: int) -> None:
        """Actualiza el combo de perfiles cuando el usuario desliza o escribe manualmente."""
        self._update_profile_combobox_from_value(val)

    def _update_profile_combobox_from_value(self, val: int) -> None:
        """Sincroniza el índice del selector con el porcentaje."""
        value_to_idx = {72: 1, 80: 2, 88: 3, 94: 4}
        idx = value_to_idx.get(val, 0)
        self.cmb_acc_profile.blockSignals(True)
        self.cmb_acc_profile.setCurrentIndex(idx)
        self.cmb_acc_profile.blockSignals(False)

    def _save_and_accept(self) -> None:
        """Aplica los cambios al objeto BoardConfig."""
        self.config.name = self.txt_name.text().strip() or self.config.name

        ori_idx = self.cmb_orientation.currentIndex()
        ori_rev = {0: "auto", 1: "white", 2: "black"}
        self.config.orientation = ori_rev.get(ori_idx, "auto")

        theme_idx = self.cmb_theme.currentIndex()
        theme_rev = {0: "green", 1: "wood", 2: "blue", 3: "mono"}
        self.config.board_theme = theme_rev.get(theme_idx, "green")

        self.config.elo = self.spin_elo.value()

        style_idx = self.cmb_style.currentIndex()
        style_rev = {0: "balanced", 1: "aggressive", 2: "defensive", 3: "tactical", 4: "positional"}
        self.config.style = style_rev.get(style_idx, "balanced")

        effort_idx = self.cmb_effort.currentIndex()
        effort_rev = {0: "low", 1: "medium", 2: "high", 3: "very_high"}
        self.config.effort = effort_rev.get(effort_idx, "medium")

        self.config.show_arrows = self.chk_arrows.isChecked()
        self.config.show_eval_bar = self.chk_eval_bar.isChecked()
        self.config.auto_scan = self.chk_auto_scan.isChecked()
        self.config.scan_interval_ms = self.spin_interval.value()
        self.config.display_mode = "overlay" if self.cmb_display_mode.currentIndex() == 1 else "independent"

        # Simulación y Precisión Objetivo
        self.config.enable_target_accuracy = self.chk_adaptive.isChecked()
        self.config.target_accuracy = self.spin_target_acc.value()
        self.config.target_accuracy_tolerance = 5

        self.accept()
