"""
Sistema Integral de Temas UI/UX para Chess Vision Assistant.
Soporta Modo Oscuro (Obsidian Studio) y Modo Claro (Apple / Linear Studio) con tokens semánticos,
microinteracciones, hojas de estilos QSS unificadas y diseño visual de alto rendimiento.
"""

from __future__ import annotations
from typing import Dict, Any


class Theme:
    """
    Gestor central de paletas, tokens semánticos y hojas de estilo QSS.
    """

    DARK = "dark"
    LIGHT = "light"

    # Tokens Semánticos para Modo Oscuro (Obsidian Studio)
    DARK_TOKENS = {
        "bg_app": "#0b0e14",
        "bg_surface": "#151b26",
        "bg_card": "#1a2232",
        "bg_card_hover": "#212c40",
        "bg_toolbar": "#10151f",
        "bg_statusbar": "#0b0e14",
        "bg_input": "#18202e",
        "bg_input_focus": "#1e283b",
        "bg_dialog": "#121722",
        "border_subtle": "#1c2433",
        "border_default": "#263245",
        "border_strong": "#334155",
        "border_focus": "#3b82f6",
        "text_primary": "#f8fafc",
        "text_secondary": "#94a3b8",
        "text_muted": "#64748b",
        "accent_blue": "#2563eb",
        "accent_blue_hover": "#3b82f6",
        "accent_emerald": "#10b981",
        "accent_amber": "#f59e0b",
        "accent_purple": "#8b5cf6",
        "accent_red": "#ef4444",
        "accent_neon": "#39ff14",
        "board_view_bg": "#151b26",
        "board_coord": "#8290a4",
        "scrollbar_handle": "#2e3b52",
        "scrollbar_bg": "#101520",
    }

    # Tokens Semánticos para Modo Claro (Apple / Linear Studio)
    LIGHT_TOKENS = {
        "bg_app": "#f8fafc",
        "bg_surface": "#ffffff",
        "bg_card": "#ffffff",
        "bg_card_hover": "#f1f5f9",
        "bg_toolbar": "#ffffff",
        "bg_statusbar": "#f8fafc",
        "bg_input": "#ffffff",
        "bg_input_focus": "#f8fafc",
        "bg_dialog": "#ffffff",
        "border_subtle": "#f1f5f9",
        "border_default": "#e2e8f0",
        "border_strong": "#cbd5e1",
        "border_focus": "#2563eb",
        "text_primary": "#0f172a",
        "text_secondary": "#475569",
        "text_muted": "#94a3b8",
        "accent_blue": "#2563eb",
        "accent_blue_hover": "#1d4ed8",
        "accent_emerald": "#059669",
        "accent_amber": "#d97706",
        "accent_purple": "#7c3aed",
        "accent_red": "#dc2626",
        "accent_neon": "#16a34a",
        "board_view_bg": "#f8fafc",
        "board_coord": "#64748b",
        "scrollbar_handle": "#cbd5e1",
        "scrollbar_bg": "#f1f5f9",
    }

    @classmethod
    def get_tokens(cls, theme: str) -> Dict[str, str]:
        """Retorna el diccionario de tokens según el tema seleccionado."""
        if str(theme).lower() == cls.LIGHT:
            return cls.LIGHT_TOKENS
        return cls.DARK_TOKENS

    @classmethod
    def get_application_stylesheet(cls, theme: str) -> str:
        """
        Genera la hoja de estilos QSS global para la aplicación completa.
        Configura tipografía moderna, ventanas, barras, menús, scrollbars y widgets estándar.
        """
        t = cls.get_tokens(theme)
        is_dark = (str(theme).lower() != cls.LIGHT)

        menu_sel_bg = "#2563eb" if is_dark else "#2563eb"
        menu_sel_fg = "#ffffff"

        qss = f"""
            /* Tipografía y Ventana Base */
            QMainWindow, QDialog {{
                background-color: {t["bg_app"]};
                color: {t["text_primary"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }}

            QWidget {{
                color: {t["text_primary"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            }}

            /* Barra de Herramientas Superior */
            QToolBar {{
                background-color: {t["bg_toolbar"]};
                border-bottom: 1px solid {t["border_default"]};
                spacing: 6px;
                padding: 6px 10px;
            }}

            QToolBar::separator {{
                width: 1px;
                background-color: {t["border_default"]};
                margin: 4px 6px;
            }}

            /* Barra de Estado Inferior */
            QStatusBar {{
                background-color: {t["bg_statusbar"]};
                color: {t["text_secondary"]};
                border-top: 1px solid {t["border_default"]};
                font-size: 11px;
                padding: 3px 8px;
            }}

            /* Tooltips */
            QToolTip {{
                background-color: {t["bg_surface"]};
                color: {t["text_primary"]};
                border: 1px solid {t["border_strong"]};
                border-radius: 5px;
                padding: 5px 8px;
                font-size: 11px;
            }}

            /* Menús Contextuales */
            QMenu {{
                background-color: {t["bg_surface"]};
                color: {t["text_primary"]};
                border: 1px solid {t["border_default"]};
                border-radius: 8px;
                padding: 6px;
            }}
            QMenu::item {{
                padding: 6px 24px 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }}
            QMenu::item:selected {{
                background-color: {menu_sel_bg};
                color: {menu_sel_fg};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {t["border_subtle"]};
                margin: 4px 6px;
            }}

            /* ComboBox */
            QComboBox {{
                background-color: {t["bg_input"]};
                color: {t["text_primary"]};
                border: 1px solid {t["border_default"]};
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 600;
                min-height: 20px;
            }}
            QComboBox:hover {{
                border-color: {t["border_focus"]};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 18px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {t["bg_surface"]};
                color: {t["text_primary"]};
                border: 1px solid {t["border_default"]};
                border-radius: 6px;
                selection-background-color: {t["accent_blue"]};
                selection-color: #ffffff;
                padding: 4px;
                outline: none;
            }}

            /* SpinBox & LineEdit */
            QLineEdit, QSpinBox {{
                background-color: {t["bg_input"]};
                color: {t["text_primary"]};
                border: 1px solid {t["border_default"]};
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QLineEdit:focus, QSpinBox:focus {{
                border: 1px solid {t["border_focus"]};
                background-color: {t["bg_input_focus"]};
            }}

            /* Sliders */
            QSlider::groove:horizontal {{
                height: 6px;
                background: {t["border_default"]};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {t["accent_blue"]};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {t["text_primary"]};
                border: 2px solid {t["accent_blue"]};
                width: 14px;
                height: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 8px;
            }}
            QSlider::handle:horizontal:hover {{
                background: #ffffff;
                border-color: {t["accent_blue_hover"]};
            }}

            /* Scrollbars */
            QScrollBar:vertical {{
                background: {t["scrollbar_bg"]};
                width: 8px;
                border-radius: 4px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {t["scrollbar_handle"]};
                min-height: 24px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {t["accent_blue"]};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}

            /* GroupBox */
            QGroupBox {{
                border: 1px solid {t["border_default"]};
                border-radius: 8px;
                margin-top: 14px;
                padding: 12px 8px 8px 8px;
                font-weight: bold;
                font-size: 12px;
                color: {t["text_primary"]};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 6px;
                color: {t["accent_blue"]};
            }}
        """
        return qss

    @classmethod
    def get_single_board_card_style(cls, theme: str) -> str:
        """Estilo para la tarjeta del contenedor del tablero individual."""
        t = cls.get_tokens(theme)
        return f"""
            QFrame#SingleBoardCard {{
                background-color: {t["bg_surface"]};
                border: 1px solid {t["border_default"]};
                border-radius: 10px;
            }}
        """

    @classmethod
    def get_button_style(cls, btn_type: str, theme: str) -> str:
        """
        Retorna los estilos QSS altamente cuidados para cada botón con microinteracciones de hover y pressed.
        Tipos soportados:
          - 'primary': Botón héroe azul brillante
          - 'secondary': Botón cian/teal de acción técnica (recortar/escanear)
          - 'config': Botón estilo pizarra/slate con acento
          - 'resync': Botón azul suave de sincronización
          - 'overlay_active': Botón overlay activado con pill brillante
          - 'overlay_inactive': Botón overlay desactivado neutro
          - 'neutral': Botón neutro refinado (girar, reiniciar, pausar)
          - 'theme_toggle': Botón llamativo para conmutar Claro/Oscuro
        """
        t = cls.get_tokens(theme)
        is_dark = (str(theme).lower() != cls.LIGHT)

        base = "QPushButton { border-radius: 6px; padding: 5px 11px; font-size: 11px; font-weight: 600; text-align: center; } QPushButton:focus { outline: none; } "

        if btn_type == "primary":
            if is_dark:
                return base + """
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #1d4ed8);
                        border: 1px solid #60a5fa;
                        color: #ffffff;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #60a5fa, stop:1 #2563eb);
                        border-color: #93c5fd;
                    }
                    QPushButton:pressed {
                        background: #1e40af;
                        border-color: #1d4ed8;
                    }
                """
            else:
                return base + """
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
                        border: 1px solid #1d4ed8;
                        color: #ffffff;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3b82f6, stop:1 #2563eb);
                        border-color: #1e40af;
                    }
                    QPushButton:pressed {
                        background: #1e3a8a;
                        border-color: #1e3a8a;
                    }
                """

        elif btn_type == "secondary":
            if is_dark:
                return base + """
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3182ce, stop:1 #2b6cb0);
                        border: 1px solid #4299e1;
                        color: #ffffff;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4299e1, stop:1 #3182ce);
                        border-color: #63b3ed;
                    }
                    QPushButton:pressed {
                        background: #1e4e8c;
                    }
                """
            else:
                return base + """
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3182ce, stop:1 #2b6cb0);
                        border: 1px solid #2b6cb0;
                        color: #ffffff;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4299e1, stop:1 #3182ce);
                        border-color: #1e4e8c;
                    }
                    QPushButton:pressed {
                        background: #1e4e8c;
                    }
                """

        elif btn_type == "config":
            if is_dark:
                return base + f"""
                    QPushButton {{
                        background-color: #172235;
                        border: 1px solid #2d3e5b;
                        color: #60a5fa;
                    }}
                    QPushButton:hover {{
                        background-color: #1e2d47;
                        border-color: #60a5fa;
                        color: #ffffff;
                    }}
                    QPushButton:pressed {{
                        background-color: #0f172a;
                    }}
                """
            else:
                return base + f"""
                    QPushButton {{
                        background-color: #eff6ff;
                        border: 1px solid #bfdbfe;
                        color: #1d4ed8;
                    }}
                    QPushButton:hover {{
                        background-color: #dbeafe;
                        border-color: #3b82f6;
                        color: #1e40af;
                    }}
                    QPushButton:pressed {{
                        background-color: #bfdbfe;
                    }}
                """

        elif btn_type == "resync":
            if is_dark:
                return base + f"""
                    QPushButton {{
                        background-color: #182438;
                        border: 1px solid #283a5c;
                        color: #93c5fd;
                    }}
                    QPushButton:hover {{
                        background-color: #233454;
                        border-color: #3b82f6;
                        color: #ffffff;
                    }}
                    QPushButton:pressed {{
                        background-color: #101826;
                    }}
                """
            else:
                return base + f"""
                    QPushButton {{
                        background-color: #f0fdf4;
                        border: 1px solid #bbf7d0;
                        color: #15803d;
                    }}
                    QPushButton:hover {{
                        background-color: #dcfce7;
                        border-color: #22c55e;
                        color: #166534;
                    }}
                    QPushButton:pressed {{
                        background-color: #bbf7d0;
                    }}
                """

        elif btn_type == "overlay_active":
            if is_dark:
                return base + """
                    QPushButton {
                        background-color: #1e3a8a;
                        border: 1px solid #3b82f6;
                        color: #bfdbfe;
                    }
                    QPushButton:hover {
                        background-color: #2563eb;
                        color: #ffffff;
                        border-color: #60a5fa;
                    }
                    QPushButton:pressed {
                        background-color: #1d4ed8;
                    }
                """
            else:
                return base + """
                    QPushButton {
                        background-color: #dbeafe;
                        border: 1px solid #3b82f6;
                        color: #1e40af;
                    }
                    QPushButton:hover {
                        background-color: #bfdbfe;
                        border-color: #2563eb;
                        color: #1e3a8a;
                    }
                    QPushButton:pressed {
                        background-color: #93c5fd;
                    }
                """

        elif btn_type == "overlay_inactive":
            if is_dark:
                return base + f"""
                    QPushButton {{
                        background-color: #1a2232;
                        border: 1px solid {t["border_default"]};
                        color: {t["text_secondary"]};
                    }}
                    QPushButton:hover {{
                        background-color: #232d42;
                        border-color: {t["border_strong"]};
                        color: {t["text_primary"]};
                    }}
                    QPushButton:pressed {{
                        background-color: #131926;
                    }}
                """
            else:
                return base + f"""
                    QPushButton {{
                        background-color: #f1f5f9;
                        border: 1px solid {t["border_default"]};
                        color: {t["text_secondary"]};
                    }}
                    QPushButton:hover {{
                        background-color: #e2e8f0;
                        border-color: {t["border_strong"]};
                        color: {t["text_primary"]};
                    }}
                    QPushButton:pressed {{
                        background-color: #cbd5e1;
                    }}
                """

        elif btn_type == "theme_toggle":
            if is_dark:
                return base + """
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2b2310, stop:1 #1a1e28);
                        border: 1px solid #eab308;
                        color: #fde047;
                        padding: 5px 12px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3d3115, stop:1 #242938);
                        border-color: #facc15;
                        color: #ffffff;
                    }
                    QPushButton:pressed {
                        background: #1c170a;
                    }
                """
            else:
                return base + """
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f5f3ff, stop:1 #ede9fe);
                        border: 1px solid #8b5cf6;
                        color: #6d28d9;
                        padding: 5px 12px;
                    }
                    QPushButton:hover {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ede9fe, stop:1 #ddd6fe);
                        border-color: #7c3aed;
                        color: #4c1d95;
                    }
                    QPushButton:pressed {
                        background: #ddd6fe;
                    }
                """

        else:  # neutral
            if is_dark:
                return base + f"""
                    QPushButton {{
                        background-color: #192130;
                        border: 1px solid {t["border_default"]};
                        color: {t["text_primary"]};
                    }}
                    QPushButton:hover {{
                        background-color: #232e42;
                        border-color: {t["border_strong"]};
                        color: #ffffff;
                    }}
                    QPushButton:pressed {{
                        background-color: #121824;
                    }}
                """
            else:
                return base + f"""
                    QPushButton {{
                        background-color: #f1f5f9;
                        border: 1px solid {t["border_default"]};
                        color: {t["text_primary"]};
                    }}
                    QPushButton:hover {{
                        background-color: #e2e8f0;
                        border-color: {t["border_strong"]};
                        color: #0f172a;
                    }}
                    QPushButton:pressed {{
                        background-color: #cbd5e1;
                    }}
                """

    @classmethod
    def get_sync_badge_style(cls, status_type: str, theme: str) -> str:
        """
        Retorna el estilo tipo píldora para la etiqueta de sincronización.
        status_type: 'ready', 'paused', 'desync', 'scanning'
        """
        is_dark = (str(theme).lower() != cls.LIGHT)

        if status_type == "ready":
            if is_dark:
                return "background-color: #064e3b; color: #34d399; border: 1px solid #059669; border-radius: 11px; padding: 2px 10px; font-weight: bold; font-size: 11px;"
            else:
                return "background-color: #d1fae5; color: #065f46; border: 1px solid #10b981; border-radius: 11px; padding: 2px 10px; font-weight: bold; font-size: 11px;"

        elif status_type == "paused":
            if is_dark:
                return "background-color: #451a03; color: #fde047; border: 1px solid #b45309; border-radius: 11px; padding: 2px 10px; font-weight: bold; font-size: 11px;"
            else:
                return "background-color: #fef3c7; color: #92400e; border: 1px solid #f59e0b; border-radius: 11px; padding: 2px 10px; font-weight: bold; font-size: 11px;"

        elif status_type == "scanning":
            if is_dark:
                return "background-color: #172554; color: #60a5fa; border: 1px solid #2563eb; border-radius: 11px; padding: 2px 10px; font-weight: bold; font-size: 11px;"
            else:
                return "background-color: #eff6ff; color: #1d4ed8; border: 1px solid #3b82f6; border-radius: 11px; padding: 2px 10px; font-weight: bold; font-size: 11px;"

        else:  # desync / warning
            if is_dark:
                return "background-color: #450a0a; color: #f87171; border: 1px solid #dc2626; border-radius: 11px; padding: 2px 10px; font-weight: bold; font-size: 11px;"
            else:
                return "background-color: #fee2e2; color: #991b1b; border: 1px solid #ef4444; border-radius: 11px; padding: 2px 10px; font-weight: bold; font-size: 11px;"

    @classmethod
    def get_move_card_style(cls, theme: str, is_adaptive: bool = False, is_subtle_loss: bool = False) -> str:
        """Estilo interactivo para las tarjetas Multi-PV."""
        t = cls.get_tokens(theme)
        is_dark = (str(theme).lower() != cls.LIGHT)

        if is_subtle_loss:
            if is_dark:
                return """
                    QFrame#MoveCard, QFrame#AdaptiveCard {
                        background-color: #2b1f06;
                        border: 2px solid #F59E0B;
                        border-radius: 8px;
                        padding: 6px;
                    }
                    QFrame#MoveCard:hover, QFrame#AdaptiveCard:hover {
                        background-color: #3b2a08;
                        border-color: #FBBF24;
                    }
                """
            else:
                return """
                    QFrame#MoveCard, QFrame#AdaptiveCard {
                        background-color: #fffbeb;
                        border: 2px solid #D97706;
                        border-radius: 8px;
                        padding: 6px;
                    }
                    QFrame#MoveCard:hover, QFrame#AdaptiveCard:hover {
                        background-color: #fef3c7;
                        border-color: #B45309;
                    }
                """
        elif is_adaptive:
            if is_dark:
                return """
                    QFrame#MoveCard, QFrame#AdaptiveCard {
                        background-color: #0b2413;
                        border: 2px solid #39FF14;
                        border-radius: 8px;
                        padding: 6px;
                    }
                    QFrame#MoveCard:hover, QFrame#AdaptiveCard:hover {
                        background-color: #12351c;
                        border-color: #61ff44;
                    }
                """
            else:
                return """
                    QFrame#MoveCard, QFrame#AdaptiveCard {
                        background-color: #f0fdf4;
                        border: 2px solid #39FF14;
                        border-radius: 8px;
                        padding: 6px;
                    }
                    QFrame#MoveCard:hover, QFrame#AdaptiveCard:hover {
                        background-color: #dcfce7;
                        border-color: #16a34a;
                    }
                """
        else:
            return f"""
                QFrame#MoveCard {{
                    background-color: {t["bg_card"]};
                    border: 1px solid {t["border_default"]};
                    border-radius: 8px;
                    padding: 6px;
                }}
                QFrame#MoveCard:hover {{
                    background-color: {t["bg_card_hover"]};
                    border-color: {t["accent_blue"]};
                }}
            """

    @classmethod
    def get_accuracy_widget_style(cls, theme: str) -> str:
        """Estilo para el widget contenedor de métricas de precisión CAPS."""
        t = cls.get_tokens(theme)
        return f"""
            QFrame#AccuracyWidget {{
                background-color: {t["bg_surface"]};
                border: 1px solid {t["border_default"]};
                border-radius: 8px;
                padding: 6px 8px;
            }}
        """
