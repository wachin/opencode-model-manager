"""Arranque real de la aplicación con PyQt6 auténtico (offscreen).

Los tests unitarios corren contra un stub; este módulo comprueba lo que el
stub no puede demostrar: que la ventana se construye con Qt real, que las
señales y el árbol perezoso funcionan de verdad y que el flujo
buscar → registrar → guardar termina sin bloqueos ni trazas.

Se omite si PyQt6 no está instalado o si el plataforma offscreen no arranca.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import ROOT

CONFIG = {
    "$schema": "https://opencode.ai/config.json",
    "provider": {
        "acme": {
            "npm": "@ai-sdk/openai-compatible",
            "name": "Acme AI",
            "options": {"baseURL": "https://api.acme.test/v1"},
            "models": {"acme-coder": {"name": "Acme Coder"}},
        },
    },
    "model": "acme/acme-coder",
}

SECRET = "sk-NADEBE-MOVERSE"

# Caché de Models.dev que la aplicación cargará en el arranque (offline).
CATALOG_PAYLOAD = {
    "acme": {
        "id": "acme", "name": "Acme AI", "npm": "@ai-sdk/openai-compatible",
        "api": "https://api.acme.test/v1", "env": ["ACME_API_KEY"],
        "models": {
            "acme-coder": {
                "id": "acme-coder", "name": "Acme Coder",
                "description": "modelo para programar",
                "limit": {"context": 400_000, "output": 32_000},
                "tool_call": True,
                "cost": {"input": 1.0, "output": 4.0},
            },
            "acme-lite": {
                "id": "acme-lite", "name": "Acme Lite",
                "modalities": {"input": ["text", "image"]},
                "cost": {"input": 0, "output": 0},
            },
        },
    },
}

DRIVER = r"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.environ["OMM_ROOT"])

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from omm.main_window import OpenCodeModelManager
from omm.ui.dialogs import ProviderDialog

config_path = Path(os.environ["OMM_CONFIG"])
app = QApplication.instance() or QApplication(sys.argv)
app.setStyle("Fusion")

window = OpenCodeModelManager()
window.show()

# El catálogo llega por señal desde el QThread: hay que bombear el bucle,
# igual que en uso real, antes de poder verlo en pantalla.
deadline = time.monotonic() + 10.0
while window.catalog.loaded_source == "seed" and time.monotonic() < deadline:
    app.processEvents()
    time.sleep(0.01)

report = {}
report["title"] = window.windowTitle()
report["catalog_source"] = window.catalog.loaded_source
report["pages"] = window.workspace.count()
report["providers"] = window.tree.topLevelItemCount()
report["all_collapsed"] = all(
    not window.tree.topLevelItem(i).isExpanded()
    for i in range(window.tree.topLevelItemCount())
)

# --- tema: el claro no puede heredar el fondo del escritorio ---------------
# Se fuerza una paleta de sistema oscura (el caso del informe del usuario) y
# se mide la ventana pintada: si el QSS dejara huecos sin superficie, asoma
# este fondo oscuro.
from PyQt6.QtGui import QColor, QPalette  # noqa: E402
from omm.theme import DARK, LIGHT  # noqa: E402

base = app.palette()
for role_name in ("Window", "Base", "Text", "WindowText", "Button", "ButtonText"):
    base.setColor(getattr(QPalette.ColorRole, role_name), QColor("#101010"))
app.setPalette(base)

def _role_keys_resolve(key):
    group, _, role = key.rpartition(".")
    if group and not hasattr(QPalette.ColorGroup, group):
        return False
    return hasattr(QPalette.ColorRole, role)


report["roles_missing_in_real_qt"] = [
    key for key in LIGHT.roles() if not _role_keys_resolve(key)
]

w, h = window.width(), window.height()
POINTS = {
    "header": (6, 6),
    "workspace": (w // 3, h - 60),
    "status": (w // 3, h - 8),
}


def shoot(mode):
    window._theme_mode = mode
    window.apply_theme()
    app.processEvents()
    image = window.grab().toImage()
    wanted = LIGHT if mode == "light" else DARK
    dialog = ProviderDialog(window)
    dialog.resize(680, 520)
    dialog.show()
    app.processEvents()
    pane = dialog.grab().toImage().pixelColor(20, 120).name()
    dialog.close()
    dialog.deleteLater()
    return {
        "pixels": {
            name: image.pixelColor(x, y).name() for name, (x, y) in POINTS.items()
        },
        "dialog_pane": pane,
        "sheet_has_surface": wanted.surface in app.styleSheet(),
        "app_window": app.palette().color(
            QPalette.ColorGroup.Active, QPalette.ColorRole.Window
        ).name(),
        "overview_muted": wanted.text_muted in window.overview.body.text(),
    }


report["light"] = shoot("light")
report["dark"] = shoot("dark")
window._theme_mode = "light"
window.apply_theme()

window.header.search_edit.setText("acme")
window.on_search_changed("acme")
report["results"] = window.results.count()
report["page_after_search"] = window.workspace.currentIndex()
report["count_label"] = window.header.count_label.text()

window.filter_panel.chip_free.setChecked(True)
report["results_free"] = window.results.count()
report["still_collapsed"] = all(
    not window.tree.topLevelItem(i).isExpanded()
    for i in range(window.tree.topLevelItemCount())
)

top = None
for i in range(window.tree.topLevelItemCount()):
    if window.tree.topLevelItem(i).data(0, 257) == "acme":
        top = window.tree.topLevelItem(i)
if top is not None:
    top.setExpanded(True)
    report["children_after_expand"] = top.childCount()

window.show_model("acme", "acme-lite")
report["registered_before"] = "acme-lite" in (
    window.data.get("provider", {}).get("acme", {}).get("models", {})
)
window.register_current_model()
report["registered_after"] = "acme-lite" in (
    window.data.get("provider", {}).get("acme", {}).get("models", {})
)

# El botón de modelo ligero tiene que estar vivo tras registrar (wiring real).
report["small_enabled"] = window.details.small_btn.isEnabled()
window.details.small_btn.click()
report["small_after"] = window.data.get("small_model")

# Sin coincidencias: la lista se queda vacía y el aviso debe verse.
window.header.search_edit.setText("nada-de-esto-existe")
window.on_search_changed("nada-de-esto-existe")
report["empty_rows"] = window.results.count()
report["empty_notice"] = window.results._empty.isVisible()

window.details_copy_id()
window.save_config(quiet=True)

report["on_disk"] = json.loads(config_path.read_text(encoding="utf-8"))
report["backups"] = sorted(p.name for p in (config_path.parent / "opencode-backups").iterdir())
report["tmp_left"] = [p.name for p in config_path.parent.glob("*.tmp")]

QTimer.singleShot(50, window.close)
QTimer.singleShot(250, app.quit)
code = app.exec()
print("REPORT:" + json.dumps(report))
sys.exit(code)
"""


def _offscreen_available() -> bool:
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    probe = subprocess.run(
        [sys.executable, "-c",
         "from PyQt6.QtWidgets import QApplication; QApplication([])"],
        env=env, capture_output=True, text=True, timeout=120,
    )
    return probe.returncode == 0


@unittest.skipUnless(_offscreen_available(), "PyQt6 offscreen no disponible")
class TestRealAppLaunch(unittest.TestCase):
    """Una única ejecución del binario real; todas las aserciones sobre ella."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="omm-launch-"))
        cls.home = cls.tmp / "home"
        (cls.home / ".config" / "opencode").mkdir(parents=True)
        cls.config = cls.home / ".config" / "opencode" / "opencode.json"
        cls.config.write_text(json.dumps(CONFIG), encoding="utf-8")
        cls.auth = cls.home / ".local" / "share" / "opencode" / "auth.json"
        cls.auth.parent.mkdir(parents=True)
        cls.auth.write_text(
            json.dumps({"acme": {"type": "api", "key": SECRET}}), encoding="utf-8"
        )
        cls.auth_bytes = cls.auth.read_bytes()

        cache = cls.tmp / "cache" / "opencode-model-manager"
        cache.mkdir(parents=True)
        (cache / "models_dev.json").write_text(
            json.dumps(CATALOG_PAYLOAD), encoding="utf-8"
        )
        (cache / "models_dev.meta.json").write_text(
            json.dumps({"fetched_at": "2026-10-30T00:00:00+00:00"}),
            encoding="utf-8",
        )

        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(cls.home),
            "USER": os.environ.get("USER", ""),
            "XDG_CONFIG_HOME": str(cls.home / ".config"),
            "XDG_CACHE_HOME": str(cls.tmp / "cache"),
            "XDG_DATA_HOME": str(cls.home / ".local" / "share"),
            "QT_QPA_PLATFORM": "offscreen",
            "OMM_ROOT": str(ROOT),
            "OMM_CONFIG": str(cls.config),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        driver = cls.tmp / "driver.py"
        driver.write_text(DRIVER, encoding="utf-8")
        try:
            cls.proc = subprocess.run(
                [sys.executable, str(driver)], env=env, capture_output=True,
                text=True, timeout=180, cwd=str(cls.tmp),
            )
        except subprocess.TimeoutExpired:  # pragma: no cover - fallo duro
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise AssertionError("La aplicación real no terminó (bloqueo).")
        cls.report = cls._parse(cls.proc.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def _parse(stdout: str) -> dict:
        for line in stdout.splitlines():
            if line.startswith("REPORT:"):
                return json.loads(line[len("REPORT:"):])
        return {}

    # -- arranque ---------------------------------------------------------
    def test_the_process_exits_cleanly(self):
        self.assertNotIn("Traceback", self.proc.stderr)
        self.assertEqual(self.proc.returncode, 0, self.proc.stderr[-800:])
        self.assertTrue(self.report, "El conductor no devolvió informe")

    def test_the_window_builds_with_real_qt(self):
        self.assertEqual(self.report["title"], "OpenCode API Manager")
        self.assertEqual(self.report["pages"], 3)
        self.assertGreaterEqual(self.report["providers"], 1)

    def test_the_offline_cache_reaches_the_ui_through_the_worker(self):
        """La caché se carga en un hilo y se publica por señal, sin red."""
        self.assertEqual(self.report["catalog_source"], "cache")

    def test_the_tree_starts_fully_collapsed(self):
        self.assertTrue(self.report["all_collapsed"])

    # -- búsqueda con Qt real --------------------------------------------
    def test_search_returns_results_without_touching_the_tree(self):
        self.assertEqual(self.report["page_after_search"], 1)
        self.assertGreaterEqual(self.report["results"], 2)
        self.assertIn("coincidencia", self.report["count_label"])

    def test_filter_chips_are_wired_to_real_signals(self):
        self.assertLessEqual(self.report["results_free"], self.report["results"])
        self.assertTrue(self.report["still_collapsed"])

    def test_expanding_loads_children_once(self):
        self.assertEqual(self.report["children_after_expand"], 2)

    # -- registro + guardado con Qt real ---------------------------------
    def test_registering_is_the_only_way_a_catalog_model_enters_the_config(self):
        self.assertFalse(self.report["registered_before"])
        self.assertTrue(self.report["registered_after"])
        self.assertIn(
            "acme-lite", self.report["on_disk"]["provider"]["acme"]["models"]
        )

    def test_saved_file_is_valid_and_keeps_the_previous_content(self):
        provider = self.report["on_disk"]["provider"]["acme"]
        self.assertEqual(provider["name"], "Acme AI")
        self.assertIn("acme-coder", provider["models"])
        self.assertEqual(self.report["on_disk"]["model"], "acme/acme-coder")

    def test_saving_left_a_backup_and_no_temporary_file(self):
        self.assertEqual(len(self.report["backups"]), 1)
        self.assertEqual(self.report["tmp_left"], [])

    # -- controles recién conectados con Qt real --------------------------
    def test_small_model_button_is_live_after_registering(self):
        self.assertTrue(self.report["small_enabled"])
        self.assertEqual(self.report["small_after"], "acme/acme-lite")
        self.assertEqual(self.report["on_disk"]["small_model"], "acme/acme-lite")

    def test_empty_result_shows_the_notice(self):
        self.assertEqual(self.report["empty_rows"], 0)
        self.assertTrue(self.report["empty_notice"])

    # -- tema con Qt real --------------------------------------------------
    def test_light_theme_does_not_inherit_a_dark_desktop(self):
        """Con paleta de sistema oscura, el tema claro tiene que salir claro."""
        self.assertEqual(self.report["roles_missing_in_real_qt"], [])
        light = self.report["light"]
        self.assertEqual(light["app_window"], "#f5f6f8")
        self.assertEqual(light["pixels"]["header"], "#ffffff")
        for name, hex_value in light["pixels"].items():
            self.assertGreater(
                _luminance(hex_value), 0.85, f"{name} sigue oscuro: {hex_value}"
            )
        self.assertTrue(light["sheet_has_surface"])
        self.assertTrue(light["overview_muted"])
        self.assertGreater(
            _luminance(light["dialog_pane"]), 0.85,
            f"el panel de pestañas del diálogo sale oscuro: "
            f"{light['dialog_pane']}",
        )

    def test_dark_theme_still_paints_dark(self):
        dark = self.report["dark"]
        self.assertEqual(dark["app_window"], "#16181d")
        self.assertEqual(dark["pixels"]["header"], "#1e2228")
        for name, hex_value in dark["pixels"].items():
            self.assertLess(
                _luminance(hex_value), 0.30, f"{name} salió clara: {hex_value}"
            )
        self.assertTrue(dark["sheet_has_surface"])
        self.assertLess(_luminance(dark["dialog_pane"]), 0.30)

    # -- credenciales ------------------------------------------------------
    def test_auth_json_is_never_read_or_written(self):
        self.assertEqual(self.auth.read_bytes(), self.auth_bytes)

    def test_nothing_secret_appears_in_the_written_config(self):
        blob = self.config.read_text(encoding="utf-8")
        self.assertNotIn(SECRET, blob)
        json.loads(blob)
        # El nombre de una variable de entorno (ACME_API_KEY) es lo correcto;
        # lo que nunca puede aparecer es el material de clave en sí.
        for value in _string_values(json.loads(blob)):
            self.assertNotIn(SECRET, value)
            self.assertFalse(
                value.lower().startswith("sk-"),
                f"Parece una API key en el archivo: {value}",
            )
        provider = json.loads(blob)["provider"]["acme"]
        self.assertNotIn("apiKey", provider["options"])
        self.assertEqual(provider["env"], ["ACME_API_KEY"])


def _luminance(hex_value: str) -> float:
    """Luminancia relativa (0 = negro, 1 = blanco) de un #rrggbb."""
    body = hex_value.lstrip("#")
    channels = [int(body[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
              for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _string_values(node):
    """Todos los valores de tipo cadena del árbol JSON."""
    if isinstance(node, dict):
        for value in node.values():
            yield from _string_values(value)
    elif isinstance(node, list):
        for value in node:
            yield from _string_values(value)
    elif isinstance(node, str):
        yield node


if __name__ == "__main__":
    unittest.main()
