"""Sistema visual: paletas claro/oscuro y hoja de estilo de la aplicación.

Estilo deliberadamente sobrio para escritorio Linux: superficies planas,
bordes sutiles, tipografía clara, acentos usados con moderación. Se aplica
sobre la base Fusion, respetando la fuente del sistema cuando existe.
"""

from __future__ import annotations

from dataclasses import dataclass

MONO_FAMILY = "Monospace"


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    surface_alt: str
    border: str
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    on_accent: str
    success: str
    danger: str
    selected: str
    tree_alt: str

    @property
    def tokens(self) -> dict:
        return {k: str(v) for k, v in self.__dict__.items()}

    def roles(self) -> dict:
        """Colores por rol de QPalette.

        La hoja de estilos sólo pinta los selectores que declara; todo lo
        demás (popups de QComboBox, diálogos y cuadros de mensaje, ramas del
        árbol, texto desactivado, el fondo de la propia ventana) sale de la
        paleta. Sin este mapa, en un escritorio oscuro el tema claro heredaba
        el oscuro del sistema.
        """
        return {
            "Window": self.background,
            "WindowText": self.text,
            "Base": self.surface,
            "AlternateBase": self.tree_alt,
            "Text": self.text,
            "Button": self.surface_alt,
            "ButtonText": self.text,
            "ToolTipBase": self.surface,
            "ToolTipText": self.text,
            "PlaceholderText": self.text_muted,
            "BrightText": self.danger,
            "Highlight": self.accent,
            "HighlightedText": self.on_accent,
            "Link": self.accent,
            "Disabled.Text": self.text_muted,
            "Disabled.WindowText": self.text_muted,
            "Disabled.ButtonText": self.text_muted,
            "Disabled.Highlight": self.border,
            "Disabled.HighlightedText": self.text_muted,
        }


LIGHT = Palette(
    background="#f5f6f8",
    surface="#ffffff",
    surface_alt="#eceef2",
    border="#d9dce2",
    text="#23282f",
    text_muted="#5f6775",
    accent="#0a6cc8",
    accent_hover="#0959a6",
    on_accent="#ffffff",
    success="#187a5c",
    danger="#c03333",
    selected="#dcebfd",
    tree_alt="#fafbfc",
)

DARK = Palette(
    background="#16181d",
    surface="#1e2228",
    surface_alt="#262b33",
    border="#333a45",
    text="#dde3ec",
    text_muted="#98a1b0",
    accent="#4c9dff",
    accent_hover="#6db0ff",
    on_accent="#10161f",
    success="#39b58c",
    danger="#e0655f",
    selected="#2b3a50",
    tree_alt="#1b1f25",
)


def build_stylesheet(p: Palette) -> str:
    """QSS completo a partir de una paleta.

    El ORDEN importa: «QWidget» y «QMainWindow» son selectores de tipo con la
    misma especificidad, así que gana el que aparece después. La regla
    genérica con `background: transparent` va por tanto ANTES de las reglas de
    superficie; al revés dejaba la ventana y los contenedores sin pintar y el
    tema del escritorio asomaba debajo (tema claro sobre escritorio oscuro).
    """
    return f"""
    QWidget {{ color: {p.text}; background: transparent; }}

    /* Superficies de primer nivel: ventana, diálogos y contenedores propios. */
    QMainWindow, QDialog, QWidget#workspace, QScrollArea#filterWrap {{
        background: {p.background}; color: {p.text};
    }}
    QWidget#headerBar, QWidget#sidebar, QStatusBar, QMenuBar,
    QMenu, QMessageBox, QDialogButtonBox {{
        background: {p.surface}; color: {p.text};
    }}
    QLabel#hintLabel, QLabel#pathLabel, QLabel#mutedLabel {{
        color: {p.text_muted};
    }}
    QLabel#hintLabel {{ font-size: 11px; }}

    QToolTip {{
        background: {p.surface}; color: {p.text};
        border: 1px solid {p.border}; padding: 4px 6px;
    }}

    /* ---------- cabecera ---------- */
    QWidget#headerBar {{ border-bottom: 1px solid {p.border}; }}
    QLabel#appTitle {{ font-size: 16px; font-weight: 700; }}
    QLabel#pathLabel {{ font-size: 11px; }}

    QLineEdit {{
        background: {p.surface}; border: 1px solid {p.border};
        border-radius: 6px; padding: 6px 8px;
        selection-background-color: {p.accent};
        selection-color: {p.on_accent};
    }}
    QLineEdit:focus {{ border: 1px solid {p.accent}; }}
    QLineEdit#searchBox {{ padding: 7px 10px; }}

    QComboBox {{
        background: {p.surface}; border: 1px solid {p.border};
        border-radius: 6px; padding: 5px 8px;
    }}
    QComboBox QAbstractItemView {{
        background: {p.surface}; color: {p.text};
        border: 1px solid {p.border};
        selection-background-color: {p.selected};
        selection-color: {p.text};
    }}

    QPushButton {{
        background: {p.surface_alt}; color: {p.text};
        border: 1px solid {p.border}; border-radius: 6px;
        padding: 6px 12px; font-weight: 600;
    }}
    QPushButton:hover {{ background: {p.border}; }}
    QPushButton:pressed {{ background: {p.selected}; }}
    QPushButton:disabled {{ color: {p.text_muted}; }}
    QPushButton#primary {{
        background: {p.accent}; color: {p.on_accent};
        border: 1px solid {p.accent};
    }}
    QPushButton#primary:hover {{ background: {p.accent_hover}; }}
    QPushButton#danger {{
        background: transparent; color: {p.danger};
        border: 1px solid {p.danger};
    }}
    QPushButton#danger:hover {{ background: {p.danger}; color: {p.on_accent}; }}
    QPushButton#ghost {{ border: none; background: transparent; color: {p.text_muted}; }}
    QPushButton#ghost:hover {{ color: {p.text}; }}

    QToolButton {{
        background: transparent; border: 1px solid {p.border};
        border-radius: 6px; padding: 5px 9px; color: {p.text};
    }}
    QToolButton:hover {{ background: {p.surface_alt}; }}
    QToolButton:checked {{ background: {p.selected}; border-color: {p.accent}; }}

    /* ---------- panel central ---------- */
    QFrame#card {{
        background: {p.surface}; border: 1px solid {p.border};
        border-radius: 8px;
    }}
    /* FilterPanel hereda de QWidget, no de QFrame: el selector antiguo
       (QFrame#filterPanel) nunca llegó a pintarse. */
    QWidget#filterPanel {{
        background: {p.surface}; border: 1px solid {p.border};
        border-radius: 8px;
    }}
    QLabel {{ font-size: 13px; }}
    QLabel#sectionTitle {{ font-size: 14px; font-weight: 700; }}
    QLabel#detailValue {{ font-size: 13px; }}
    QLabel#detailValueMono {{
        font-family: {MONO_FAMILY}; font-size: 12px;
        color: {p.text};
    }}

    /* ---------- resultados ---------- */
    QListWidget, QTreeWidget {{
        background: {p.surface};
        border: 1px solid {p.border};
        border-radius: 8px;
        font-size: 13px;
        outline: 0;
    }}
    /* Popups de QComboBox y cualquier vista compartida: sin esto heredan el
       fondo del sistema y el texto puede quedar del mismo color. */
    QAbstractItemView {{
        background: {p.surface}; color: {p.text};
        border: 1px solid {p.border};
        selection-background-color: {p.selected};
        selection-color: {p.text};
        outline: 0;
    }}
    QMenu::item {{ padding: 4px 12px; }}
    QMenu::item:selected, QMenu::item:hover {{ background: {p.selected}; color: {p.text}; }}
    QListWidget::item, QTreeWidget::item {{
        padding: 4px 6px;
        border: none;
    }}
    QListWidget::item:hover, QTreeView::item:hover {{ background: {p.surface_alt}; }}
    QListWidget::item:selected {{ background: {p.selected}; color: {p.text}; }}
    QTreeView::item:selected {{ background: {p.selected}; color: {p.text}; }}
    QTreeView::item:selected:active {{ background: {p.selected}; }}
    QTreeView::branch {{ background: {p.surface}; }}
    QTreeWidget {{ alternate-background-color: {p.tree_alt}; }}
    QHeaderView {{ background: {p.surface}; }}
    QHeaderView::section {{
        background: {p.surface_alt}; color: {p.text_muted};
        border: none; border-bottom: 1px solid {p.border};
        padding: 4px;
    }}

    /* ---------- barra lateral derecha ---------- */
    QWidget#sidebar {{ border-left: 1px solid {p.border}; }}
    QTreeWidget#providerTree {{
        background: {p.surface}; border: none; border-radius: 0;
        font-size: 12px;
    }}

    QTextEdit, QPlainTextEdit {{
        background: {p.surface_alt}; color: {p.text};
        border: 1px solid {p.border}; border-radius: 6px;
        font-family: {MONO_FAMILY}; font-size: 12px;
    }}

    QGroupBox {{
        font-weight: 700; margin-top: 10px; padding-top: 6px;
        border: 1px solid {p.border}; border-radius: 8px;
        background: {p.surface};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; left: 10px; padding: 0 4px;
        color: {p.text_muted};
    }}

    QCheckBox, QRadioButton {{ spacing: 6px; }}
    QCheckBox::indicator, QRadioButton::indicator {{ width: 15px; height: 15px; }}

    /* Pestañas del diálogo de proveedor: sin estas reglas el panel queda
       transparente y, sobre un escritorio oscuro, sale negro por dentro. */
    QTabWidget::pane {{
        background: {p.background}; border: 1px solid {p.border};
        border-radius: 6px; top: -1px;
    }}
    QTabWidget > QStackedWidget {{ background: {p.background}; }}
    QTabBar::tab {{
        background: {p.surface_alt}; color: {p.text_muted};
        border: 1px solid {p.border}; border-bottom: none;
        padding: 5px 12px;
        border-top-left-radius: 6px; border-top-right-radius: 6px;
    }}
    QTabBar::tab:selected {{ background: {p.background}; color: {p.text}; }}
    QTabBar::tab:hover {{ color: {p.text}; }}

    QStatusBar {{ background: {p.surface}; color: {p.text_muted}; border-top: 1px solid {p.border}; }}
    QStatusBar::item {{ border: none; }}

    QSplitter::handle {{ background: {p.border}; width: 2px; }}

    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {p.border}; border-radius: 4px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar:horizontal {{
        background: transparent; height: 10px; margin: 0;
    }}
    QScrollBar::handle:horizontal {{
        background: {p.border}; border-radius: 4px; min-width: 24px;
    }}

    QLabel#emptyState {{ color: {p.text_muted}; font-size: 13px; }}
    """
