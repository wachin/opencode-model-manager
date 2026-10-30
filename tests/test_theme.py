"""Tema claro/oscuro: contraste medible y hoja de estilos sin huecos.

El fallo que originó estos tests fue real y silencioso: con un escritorio
oscuro, el tema claro salía con la cabecera, la ventana y la barra de estado
negras. Tres causas, cada una con su test:

  1. `QWidget { background: transparent }` declarado después de
     `QMainWindow { ... }` — misma especificidad, gana la última, y la ventana
     entera se quedaba sin superficie propia.
  2. Ninguna QPalette aplicada: lo que el QSS no cubre (popups, diálogos,
     cuadros de mensaje, texto desactivado) heredaba el tema del escritorio.
  3. Contenedores sin regla (`#workspace`, `#filterWrap`) o con una regla que
     nunca casaba (`QFrame#filterPanel` sobre un QWidget).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from support import ROOT, qt_stub  # noqa: F401
from test_flows import _WindowCase
from omm.theme import DARK, LIGHT, build_stylesheet
from omm.ui.panels import ROLE_MID, ROLE_PID

SOURCE_DIR = Path(ROOT) / "omm"

# Objetos que se pintan a través de otra regla (el tirador del splitter) y no
# necesitan fondo propio. Cualquier objeto nuevo que sí lo necesite tiene que
# aparecer en la hoja de estilos.
TRANSPARENT_BY_DESIGN = {"workspaceSplitter"}

# Cosas que no son widgets pintables: layouts, gadgets de Qt, ítems de modelo
# y diálogos nativos del sistema (los gestiona el gestor de ventanas).
NOT_A_WIDGET = {
    "QApplication", "QBrush", "QColor", "QFileDialog", "QFont", "QFormLayout",
    "QGridLayout", "QHBoxLayout", "QKeySequence", "QListWidgetItem",
    "QMessageBox", "QPalette", "QSettings", "QShortcut", "QSizePolicy",
    "QStyle", "QThread", "QTimer", "QTreeWidgetItem", "QVBoxLayout",
}


def _channels(hex_value: str) -> list:
    body = hex_value.lstrip("#")
    if len(body) == 3:
        body = "".join(ch * 2 for ch in body)
    return [int(body[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _luminance(hex_value: str) -> float:
    linear = [
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        for c in _channels(hex_value)
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    """Ratio WCAG (1..21) entre dos colores; 21 es negro sobre blanco."""
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class TestPaletteContrast(unittest.TestCase):
    """Un tema no es correcto porque sí: los contrastes tienen que aguantar."""

    def test_body_text_is_readable_on_every_surface(self):
        for palette in (LIGHT, DARK):
            for surface in ("background", "surface", "surface_alt", "selected"):
                self.assertGreaterEqual(
                    _contrast(palette.text, getattr(palette, surface)), 7.0,
                    f"{palette.text} sobre {surface} no alcanza AAA",
                )

    def test_secondary_text_meets_the_accessibility_minimum(self):
        for palette in (LIGHT, DARK):
            for surface in ("background", "surface", "surface_alt"):
                self.assertGreaterEqual(
                    _contrast(palette.text_muted, getattr(palette, surface)), 4.5,
                    f"texto atenuado sobre {surface}",
                )

    def test_accent_and_danger_keep_their_label_readable(self):
        for palette in (LIGHT, DARK):
            self.assertGreaterEqual(
                _contrast(palette.on_accent, palette.accent), 4.5,
                "etiqueta del botón primario",
            )
            self.assertGreaterEqual(
                _contrast(palette.danger, palette.surface), 4.5,
                "botón de quite sobre la superficie",
            )

    def test_the_tree_green_shows_on_its_background(self):
        """El verde de «modelo registrado» se pinta a mano: también contrasta."""
        for palette in (LIGHT, DARK):
            self.assertGreaterEqual(
                _contrast(palette.success, palette.surface), 4.5,
                "modelos registrados en el árbol",
            )

    def test_the_palettes_are_not_swapped(self):
        self.assertGreater(_luminance(LIGHT.background), 0.7)
        self.assertLess(_luminance(DARK.background), 0.2)
        self.assertLess(_luminance(LIGHT.text), 0.2)
        self.assertGreater(_luminance(DARK.text), 0.7)


class TestStylesheetRules(unittest.TestCase):
    """Estructura del QSS: orden, especificidad y huecos sin superficie."""

    def setUp(self) -> None:
        self.sheet = build_stylesheet(LIGHT)

    def test_the_generic_transparent_rule_comes_before_the_surfaces(self):
        """Regresión: así se colaba el fondo oscuro del escritorio."""
        generic = self.sheet.index("QWidget { color:")
        for selector in ("QMainWindow", "QWidget#workspace"):
            self.assertLess(generic, self.sheet.index(selector), selector)

    def test_every_container_has_its_own_surface(self):
        for selector in (
            "QMainWindow", "QDialog", "QStatusBar", "QMenu", "QMessageBox",
            "QWidget#workspace", "QScrollArea#filterWrap", "QWidget#headerBar",
            "QWidget#sidebar", "QWidget#filterPanel", "QFrame#card",
        ):
            self.assertIn(selector, self.sheet, f"falta la superficie {selector}")

    def test_no_object_name_is_left_without_a_rule(self):
        """Cada setObjectName() del código aparece en la hoja de estilos.

        Evita el bug original (`QFrame#filterPanel` sobre un QWidget) y
        cualquier panel futuro que se quede sin fondo.
        """
        declared = set()
        for module in sorted(SOURCE_DIR.rglob("*.py")):
            declared.update(re.findall(
                r'setObjectName\("([^"]+)"\)', module.read_text(encoding="utf-8")
            ))
        self.assertTrue(declared, "no se encontró ningún objectName")
        missing = {
            name for name in declared
            if f"#{name}" not in self.sheet and name not in TRANSPARENT_BY_DESIGN
        }
        self.assertEqual(missing, set(), "objetos sin regla de estilo")

    def test_the_sheet_carries_no_foreign_literal_colors(self):
        """Los colores salen de la paleta; un hex suelto no cambia de tema."""
        foreign = {
            value for value in (DARK.background, DARK.surface, DARK.text,
                                "#8892a0", "#1a8a5c")
            if value in self.sheet
        }
        self.assertEqual(foreign, set())

    def test_every_widget_class_used_by_the_ui_has_a_rule(self):
        """Cada tipo de widget que se construye en omm/ tiene su superficie.

        Un QTabWidget sin `::pane` salía negro por dentro en el diálogo de
        proveedor; esta comprobación evita que vuelva a colarse un contenedor
        nuevo sin pintar.
        """
        sources = list(SOURCE_DIR.rglob("*.py"))
        classes = set()
        for module in sources:
            text = module.read_text(encoding="utf-8")
            classes.update(re.findall(r"\b(Q[A-Z]\w+)\s*\(", text))
            classes.update(re.findall(r"class\s+\w+\((Q\w+)\)", text))
        missing = {
            name for name in classes
            if name not in NOT_A_WIDGET and name not in self.sheet
        }
        self.assertEqual(missing, set(), "widgets sin regla de estilo")

    def test_both_palettes_produce_a_complete_sheet(self):
        for palette in (LIGHT, DARK):
            sheet = build_stylesheet(palette)
            self.assertIn(palette.background, sheet)
            self.assertIn(palette.border, sheet)
            self.assertNotIn("None", sheet)


class TestRoleMap(unittest.TestCase):
    """Las claves de roles() son nombres de QPalette válidos."""

    def test_plain_keys_are_color_roles(self):
        roles = vars(qt_stub.QPalette.ColorRole)
        for key in LIGHT.roles():
            name = key.rpartition(".")[2]
            self.assertIn(name, roles, key)

    def test_dotted_keys_belong_to_the_disabled_group(self):
        for key in LIGHT.roles():
            if "." in key:
                self.assertTrue(key.startswith("Disabled."), key)

    def test_the_window_background_is_the_first_thing_painted(self):
        self.assertEqual(LIGHT.roles()["Window"], LIGHT.background)
        self.assertEqual(DARK.roles()["Window"], DARK.background)


class TestThemeReachesTheApplication(_WindowCase):
    """apply_theme() tiene que publicar en la app, no sólo en la ventana."""

    def setUp(self) -> None:
        self.app = qt_stub.QApplication()
        self.addCleanup(setattr, qt_stub.QApplication, "_instance", None)
        super().setUp()
        self.palette_role = qt_stub.QPalette.ColorRole
        self.group = qt_stub.QPalette.ColorGroup

    def color(self, role_name: str, group: str = "Active") -> str:
        role = getattr(self.palette_role, role_name)
        return self.app.palette().color(getattr(self.group, group), role).name()

    def set_mode(self, mode: str) -> None:
        self.window._theme_mode = mode
        self.window.apply_theme()

    def test_light_theme_sets_the_application_palette(self):
        self.set_mode("light")
        self.assertEqual(self.color("Window"), LIGHT.background)
        self.assertEqual(self.color("Base"), LIGHT.surface)
        self.assertEqual(self.color("Text"), LIGHT.text)
        self.assertEqual(self.color("ButtonText"), LIGHT.text)

    def test_disabled_group_is_not_left_to_the_desktop(self):
        self.set_mode("light")
        self.assertEqual(self.color("Text", "Disabled"), LIGHT.text_muted)

    def test_the_stylesheet_lives_on_the_application_so_dialogs_inherit_it(self):
        self.set_mode("light")
        self.assertIn(LIGHT.background, self.app.styleSheet())
        self.assertEqual(self.window.styleSheet(), "")

    def test_toggling_republishes_and_persists_the_choice(self):
        """auto → light → dark → auto, el orden del botón «Tema»."""
        self.assertEqual(self.window._theme_mode, "auto")
        self.window.toggle_theme()
        self.assertEqual(self.window._theme_mode, "light")
        self.assertEqual(self.color("Window"), LIGHT.background)
        self.window.toggle_theme()
        self.assertEqual(self.window._theme_mode, "dark")
        self.assertEqual(self.color("Window"), DARK.background)
        self.assertEqual(str(self.window.settings.value("theme")), "dark")
        # Una app nueva sobre el mismo QSettings recupera el tema elegido.
        reopened = qt_stub.QSettings("OpenCodeTools", "OpenCodeModelManager")
        self.assertEqual(str(reopened.value("theme", "auto")), "dark")

    def test_the_tree_green_follows_the_active_palette(self):
        self.set_mode("light")
        item = next(
            self.window.tree.topLevelItem(i)
            for i in range(self.window.tree.topLevelItemCount())
            if self.window.tree.topLevelItem(i).data(0, ROLE_PID) == "acme"
        )
        item.setExpanded(True)
        child = next(
            item.child(j) for j in range(item.childCount())
            if item.child(j).data(0, ROLE_MID) == "acme-coder"
        )
        self.assertEqual(child.foreground(0).color().name(), LIGHT.success)
        self.set_mode("dark")
        self.assertEqual(child.foreground(0).color().name(), DARK.success)

    def test_the_overview_text_uses_the_active_palette(self):
        self.set_mode("light")
        self.assertIn(LIGHT.text_muted, self.window.overview.body.text())
        self.assertNotIn("#8892a0", self.window.overview.body.text())
        self.set_mode("dark")
        body = self.window.overview.body.text()
        self.assertIn(DARK.text_muted, body)
        self.assertNotIn(LIGHT.text_muted, body)

    def test_auto_mode_picks_a_palette_without_leaving_gaps(self):
        self.set_mode("auto")
        self.assertIn(self.color("Window"), (LIGHT.background, DARK.background))
        self.assertIn(self.app.styleSheet(), (
            build_stylesheet(LIGHT), build_stylesheet(DARK)))


if __name__ == "__main__":
    unittest.main()
