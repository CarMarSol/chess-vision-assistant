"""
Diálogo Asistente de Inicio y Selección de Modos para Chess Vision Assistant.
Permite configurar el número de tableros activos (1 a 4), asignar modo de visualización
(Independiente o Superpuesto) y definir regiones de pantalla antes de iniciar el seguimiento.
"""

from __future__ import annotations
from chess_vision.i18n import tr, board_name
from typing import Optional, Dict, Tuple
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QRadioButton, QButtonGroup, QGroupBox, QWidget, QScrollArea
)

from chess_vision.config import AppConfig
from chess_vision.ui.theme import Theme


class InitialSetupDialog(QDialog):
    """
    Asistente guiado inicial y configurador de modos para Chess Vision Assistant.
    """
    region_requested = Signal(str)  # emite board_id

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None, theme: Optional[str] = None):
        super().__init__(parent)
        self.config = config
        self._theme = theme or getattr(config, "theme", "dark") or "dark"
        self.setWindowTitle(tr("🎯 Asistente de Inicio / Modos de Tablero"))
        self.setMinimumWidth(560)
        self.resize(600, 680)

        self._board_groups: Dict[str, Dict] = {}
        self._temp_regions: Dict[str, Optional[Tuple[int, int, int, int]]] = {
            b.id: b.region for b in self.config.boards
        }

        t = Theme.get_tokens(self._theme)
        self.setStyleSheet(f"""
            {Theme.get_application_stylesheet(self._theme)}
            QDialog {{
                background-color: {t["bg_dialog"]};
                color: {t["text_primary"]};
            }}
            QGroupBox {{
                background-color: {t["bg_surface"]};
            }}
            QRadioButton {{
                color: {t["text_primary"]};
                font-size: 12px;
                padding: 3px 0;
            }}
            QRadioButton:checked {{
                color: {t["accent_blue"]};
                font-weight: bold;
            }}
        """)

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(14)
        main_layout.setContentsMargins(18, 18, 18, 18)

        # Encabezado informativo
        header_lbl = QLabel(
            tr("<b>Bienvenido a Chess Vision Assistant</b><br>"
            "Selecciona el número de tableros a seguir y el modo de visualización deseado.")
        )
        header_lbl.setStyleSheet("color: #a0aec0; font-size: 13px; line-height: 1.4;")
        main_layout.addWidget(header_lbl)

        self.lbl_piece_notice = QLabel(tr("Los diseños de piezas exóticos pueden no reconocerse. Prueba piezas cburnett o consulta el manual para adaptar las referencias con tu IA."))
        self.lbl_piece_notice.setObjectName("pieceDesignNotice")
        self.lbl_piece_notice.setWordWrap(True)
        self.lbl_piece_notice.setStyleSheet("color: #a0aec0; font-size: 12px;")
        main_layout.addWidget(self.lbl_piece_notice)

        # Selector de tableros
        count_layout = QHBoxLayout()
        count_lbl = QLabel(tr("Número de tableros simultáneos:"))
        count_lbl.setStyleSheet("font-weight: bold; font-size: 13px; color: #e2e8f0;")
        count_layout.addWidget(count_lbl)

        self.cmb_count = QComboBox()
        self.cmb_count.addItems([tr("1 Tablero"), tr("2 Tableros"), tr("3 Tableros"), tr("4 Tableros")])
        self.cmb_count.setCurrentIndex(max(0, min(3, self.config.active_board_count - 1)))
        self.cmb_count.currentIndexChanged.connect(self._on_count_changed)
        count_layout.addWidget(self.cmb_count)
        count_layout.addStretch()
        main_layout.addLayout(count_layout)

        # Área con scroll para la configuración de cada tablero
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        self.boards_layout = QVBoxLayout(scroll_content)
        self.boards_layout.setSpacing(10)
        self.boards_layout.setContentsMargins(0, 0, 0, 0)

        for i in range(4):
            cfg = self.config.boards[i]
            grp = QGroupBox(tr('Tablero {value0}: {value1}', value0=i + 1, value1=board_name(cfg.name)))
            grp_layout = QVBoxLayout(grp)
            grp_layout.setSpacing(8)

            # Selector de modo
            btn_group = QButtonGroup(grp)
            rb_independent = QRadioButton(tr("Tablero independiente (reproducción interna en ventana)"))
            rb_overlay = QRadioButton(tr("Indicaciones superpuestas (flechas directamente sobre tu pantalla)"))
            btn_group.addButton(rb_independent)
            btn_group.addButton(rb_overlay)

            current_mode = getattr(cfg, "display_mode", "independent")
            if current_mode == "overlay":
                rb_overlay.setChecked(True)
            else:
                rb_independent.setChecked(True)

            grp_layout.addWidget(rb_independent)
            grp_layout.addWidget(rb_overlay)

            # Fila de selección de región
            region_row = QHBoxLayout()
            lbl_reg_info = QLabel(tr("Región: ") + (tr('({value0}, {value1}, {value2}x{value3})', value0=cfg.region[0], value1=cfg.region[1], value2=cfg.region[2], value3=cfg.region[3]) if cfg.region else tr("Sin asignar")))
            lbl_reg_info.setStyleSheet("color: #718096; font-size: 11px;")
            
            btn_reg = QPushButton(tr("✂ Seleccionar región"))
            btn_reg.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_reg.setStyleSheet(Theme.get_button_style("primary", self._theme))
            btn_reg.clicked.connect(lambda _, b_id=cfg.id: self._request_region(b_id))

            region_row.addWidget(btn_reg)
            region_row.addWidget(lbl_reg_info)
            region_row.addStretch()
            grp_layout.addLayout(region_row)

            self.boards_layout.addWidget(grp)
            self._board_groups[cfg.id] = {
                "group_box": grp,
                "rb_independent": rb_independent,
                "rb_overlay": rb_overlay,
                "lbl_reg": lbl_reg_info,
                "btn_reg": btn_reg,
            }

        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll, stretch=1)

        self._on_count_changed(self.cmb_count.currentIndex())

        # Botonera inferior
        btn_bar = QHBoxLayout()
        self.btn_cancel = QPushButton(tr("Cancelar"))
        self.btn_cancel.setObjectName("btnCancel")
        self.btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_cancel.setStyleSheet(Theme.get_button_style("neutral", self._theme))
        self.btn_cancel.clicked.connect(self.reject)
        btn_bar.addWidget(self.btn_cancel)

        btn_bar.addStretch()

        self.btn_start = QPushButton(tr("🚀 Iniciar Seguimiento"))
        self.btn_start.setObjectName("btnStart")
        self.btn_start.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_start.setStyleSheet(Theme.get_button_style("primary", self._theme))
        self.btn_start.clicked.connect(self._apply_and_start)
        btn_bar.addWidget(self.btn_start)

        main_layout.addLayout(btn_bar)

    def _on_count_changed(self, index: int) -> None:
        """Muestra u oculta los grupos de tableros según el número seleccionado."""
        count = index + 1
        for i in range(4):
            b_id = self.config.boards[i].id
            item = self._board_groups.get(b_id)
            if item:
                item["group_box"].setVisible(i < count)

    def _request_region(self, board_id: str) -> None:
        """Emite señal solicitando captura de región para el tablero."""
        self.region_requested.emit(board_id)

    def set_board_region(self, board_id: str, region: Tuple[int, int, int, int]) -> None:
        """Actualiza la región visual y temporal para un tablero."""
        self._temp_regions[board_id] = region
        item = self._board_groups.get(board_id)
        if item and region:
            item["lbl_reg"].setText(tr('Región: ({value0}, {value1}, {value2}x{value3})', value0=region[0], value1=region[1], value2=region[2], value3=region[3]))
            item["lbl_reg"].setStyleSheet("color: #48bb78; font-weight: bold; font-size: 11px;")

    def _apply_and_start(self) -> None:
        """Aplica la configuración seleccionada al AppConfig y cierra el diálogo."""
        active_count = self.cmb_count.currentIndex() + 1
        self.config.active_board_count = active_count

        for i in range(4):
            cfg = self.config.boards[i]
            item = self._board_groups.get(cfg.id)
            if item:
                cfg.display_mode = "overlay" if item["rb_overlay"].isChecked() else "independent"
                if self._temp_regions.get(cfg.id):
                    cfg.region = self._temp_regions[cfg.id]

        self.config.save()
        self.accept()
