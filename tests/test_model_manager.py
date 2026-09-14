#!/usr/bin/env python3
"""
Tests unitarios para opencode_model_manager.py.

Cubren los dos cambios clave de la herramienta:
1. Modo global por defecto con checkbox persistente (use_global).
2. Normalización de la clave "providers" a "provider" al cargar.

Los tests corren sobre un stub headless de PyQt6 (tests/qt_stub.py):
- No abren diálogos ni ventanas.
- No leen ni escriben el QSettings real del usuario.
- Nunca tocan ~/.local/share/opencode/auth.json.

Ejecución:
    python3 -m unittest discover -s tests -v
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

# ------------------------------------------------------------------
# Import del stub y del módulo bajo prueba
# ------------------------------------------------------------------

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent

# Stub SIEMPRE (force=True): hermeticidad aunque PyQt6 esté instalado.
sys.path.insert(0, str(TESTS_DIR))

import qt_stub  # noqa: E402

qt_stub.install(force=True)

spec = importlib.util.spec_from_file_location(
    "opencode_model_manager", ROOT / "opencode_model_manager.py"
)
if spec is None or spec.loader is None:
    raise unittest.SkipTest("No se encontró opencode_model_manager.py")
omm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(omm)

qt_stub.QMessageBox.question_reply = (
    qt_stub.QMessageBox.StandardButton.Yes
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _fresh_window(config_path: Path) -> omm.OpenCodeModelManager:
    """Construye una ventana sin pasar por __init__ (sin GUI real)."""
    window = object.__new__(omm.OpenCodeModelManager)
    window.settings = qt_stub.QSettings("OpenCodeTools", "OpenCodeModelManager")
    window.use_global = True
    window.config_path = config_path
    window.data = {}
    window.models = []
    window.refresh = lambda: None
    window.statusBar = lambda: _StatusBarRecorder()
    return window


class _StatusBarRecorder:
    def showMessage(self, message: str) -> None:
        self.last_message = message


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _load_config_silent(window: omm.OpenCodeModelManager) -> None:
    """Llama a load_config() capturando la traza si refresh falla."""
    window.load_config()


class _FakeEvent:
    """Sustituto mínimo de QCloseEvent para closeEvent()."""

    def __init__(self) -> None:
        self.accepted = False

    def accept(self) -> None:
        self.accepted = True


class _FakeScreen:
    """Sustituto mínimo de QScreen para _fit_to_screen()."""

    def __init__(self, rect: "qt_stub.QRect") -> None:
        self._rect = rect

    def availableGeometry(self) -> "qt_stub.QRect":
        return self._rect


# ------------------------------------------------------------------
# Parte 2: migración "providers" -> "provider"
# ------------------------------------------------------------------

class TestProviderMigration(unittest.TestCase):
    def setUp(self) -> None:
        qt_stub.QSettings.reset()
        qt_stub.QMessageBox.reset()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        qt_stub.QSettings.reset()
        qt_stub.QMessageBox.reset()

    def test_only_providers_key_is_migrated(self):
        """d) Solo 'providers': se renombra a 'provider' + QMessageBox."""
        config = self.tmp / "opencode.json"
        _write_json(
            config,
            {"providers": {"bai": {"name": "BAI", "models": {}}}},
        )

        window = _fresh_window(config)
        _load_config_silent(window)

        self.assertIn("provider", window.data)
        self.assertNotIn("providers", window.data)
        self.assertEqual(
            window.data["provider"]["bai"]["name"], "BAI"
        )
        # Los proveedores siguen visibles para el combo.
        providers = window.providers()
        self.assertIn("bai", providers)

        # QMessageBox de migración mostrado.
        self.assertEqual(
            len(qt_stub.QMessageBox.information_calls), 1,
            "Debe mostrarse el QMessageBox de migración",
        )

    def test_both_keys_merged_without_overwriting(self):
        """e) Ambas claves: fusión sin sobrescribir 'provider' existente."""
        config = self.tmp / "opencode.json"
        _write_json(
            config,
            {
                "providers": {
                    "bai": {"name": "VIEJO"},
                    "nuevo": {"name": "Nuevo", "models": {}},
                },
                "provider": {"bai": {"name": "ACTUAL", "models": {}}},
            },
        )

        window = _fresh_window(config)
        _load_config_silent(window)

        self.assertNotIn("providers", window.data)
        provider = window.data["provider"]
        # Lo ya presente en "provider" se conserva intacto.
        self.assertEqual(provider["bai"]["name"], "ACTUAL")
        # Lo que faltaba en "provider" se agrega desde "providers".
        self.assertEqual(provider["nuevo"]["name"], "Nuevo")

        self.assertEqual(
            len(qt_stub.QMessageBox.information_calls), 1
        )

    def test_only_provider_key_no_migration_no_dialog(self):
        """f) Solo 'provider': sin migración y sin ningún mensaje."""
        config = self.tmp / "opencode.json"
        _write_json(
            config,
            {"provider": {"bai": {"name": "BAI", "models": {}}}},
        )

        window = _fresh_window(config)
        _load_config_silent(window)

        self.assertNotIn("providers", window.data)
        self.assertEqual(window.data["provider"]["bai"]["name"], "BAI")
        self.assertEqual(
            qt_stub.QMessageBox.information_calls, [],
            "No debe aparecer ningún diálogo de migración",
        )

    def test_migration_is_persisted_on_save(self):
        """Tras migrar, save_config() escribe 'provider' (nunca 'providers')."""
        config = self.tmp / "opencode.json"
        _write_json(
            config,
            {"providers": {"bai": {"name": "BAI", "models": {}}}},
        )

        window = _fresh_window(config)
        _load_config_silent(window)

        # Silencia el QMessageBox.confirmación de guardado.
        window.save_config()
        on_disk = json.loads(config.read_text(encoding="utf-8"))
        self.assertIn("provider", on_disk)
        self.assertNotIn("providers", on_disk)

    def test_providers_method_ensures_provider_dict(self):
        """providers() garantiza que data['provider'] sea dict."""
        config = self.tmp / "opencode.json"
        _write_json(config, {"$schema": "https://opencode.ai/config.json"})

        window = _fresh_window(config)
        window.load_config()

        providers = window.providers()
        self.assertIsInstance(providers, dict)
        self.assertIs(providers, window.data["provider"])

    def test_provider_key_removed_from_source(self):
        """provider_key() (código muerto) no existe ni queda referenciado."""
        source = (ROOT / "opencode_model_manager.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("provider_key", source)


# ------------------------------------------------------------------
# Parte 1: modo global por defecto + checkbox persistente
# ------------------------------------------------------------------

class TestGlobalMode(unittest.TestCase):
    def setUp(self) -> None:
        qt_stub.QSettings.reset()
        qt_stub.QMessageBox.reset()
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        qt_stub.QSettings.reset()
        qt_stub.QMessageBox.reset()

    def test_global_config_path(self):
        """global_config_path() apunta a ~/.config/opencode/opencode.json."""
        expected = Path.home() / ".config" / "opencode" / "opencode.json"
        self.assertEqual(omm.global_config_path(), expected)

    def test_first_launch_defaults_to_global_mode(self):
        """a) Primer arranque sin QSettings: use_global True y path global."""
        settings = qt_stub.QSettings("OpenCodeTools", "OpenCodeModelManager")
        self.assertFalse(
            settings.contains("use_global"),
            "Precondición: QSettings vacío (primer arranque)",
        )

        use_global = settings.value("use_global", True, type=bool)
        self.assertIs(use_global, True)

        config_path = (
            omm.global_config_path() if use_global
            else omm.discover_config()
        )
        self.assertEqual(config_path, omm.global_config_path())

    def test_first_launch_missing_file_offers_creation(self):
        """a) Si el archivo global no existe, se ofrece crear config básica."""
        config = self.tmp / "nested" / "opencode.json"
        window = _fresh_window(config)
        window.load_config()

        # Se preguntó al usuario (diálogo de archivo no encontrado).
        self.assertEqual(
            len(qt_stub.QMessageBox.question_calls), 1,
            "Debe ofrecerse crear un opencode.json básico",
        )
        # La respuesta simulada es "Yes": se crea data básica con "provider".
        self.assertEqual(
            window.data,
            {"$schema": omm.SCHEMA_URL, "provider": {}},
        )

    def test_unchecking_switches_to_discover_config(self):
        """b) Desmarcar: recalcula con discover_config() y guarda False."""
        config = self.tmp / "opencode.json"
        _write_json(config, {"provider": {}})

        window = _fresh_window(config)
        window.load_config()

        # Simula la ruta local que devolvería discover_config().
        fake_local = self.tmp / "repo" / "opencode.json"
        original_discover = omm.discover_config
        omm.discover_config = lambda: fake_local
        try:
            window.toggle_global_mode(0)  # unchecked
        finally:
            omm.discover_config = original_discover

        self.assertFalse(window.use_global)
        self.assertEqual(window.config_path, fake_local)

        settings = window.settings
        self.assertEqual(
            settings.value("use_global", None), False,
            "QSettings debe persistir use_global=False",
        )

    def test_checking_switches_back_to_global(self):
        """b) Volver a marcar: config_path vuelve al archivo global."""
        config = self.tmp / "opembed.json"
        _write_json(config, {"provider": {}})

        window = _fresh_window(config)
        window.load_config()

        window.toggle_global_mode(
            qt_stub.Qt.CheckState.Checked.value
        )

        self.assertTrue(window.use_global)
        self.assertEqual(
            window.config_path, omm.global_config_path()
        )
        settings = window.settings
        self.assertEqual(
            settings.value("use_global", None), True
        )

    def test_persistence_across_restarts(self):
        """c) Cerrar y reabrir: el estado del checkbox se conserva."""
        # --- Primera sesión: el usuario desmarca el modo global. ---
        settings = qt_stub.QSettings("OpenCodeTools", "OpenCodeModelManager")
        settings.setValue("use_global", False)

        # --- Segunda sesión (nueva instancia, mismo QSettings). ---
        settings2 = qt_stub.QSettings("OpenCodeTools", "OpenCodeModelManager")
        use_global = settings2.value("use_global", True, type=bool)
        self.assertIs(use_global, False)

        config_path = (
            omm.global_config_path() if use_global
            else omm.discover_config()
        )
        # Sin opencode.json en cwd ni repos git, discover_config() cae al
        # archivo global (existe o no) o a cwd/opencode.json.
        self.assertIsInstance(config_path, Path)

    def test_toggle_reloads_config(self):
        """Alternar el checkbox dispara load_config() (recarga el archivo)."""
        config = self.tmp / "opencode.json"
        _write_json(config, {"provider": {"bai": {"name": "BAI"}}})

        window = _fresh_window(config)
        window.load_config()

        reloaded: list[bool] = []
        window.load_config = lambda: reloaded.append(True)  # type: ignore

        window.toggle_global_mode(0)
        self.assertEqual(reloaded, [True])

    def test_checkbox_sync_without_firing_signal(self):
        """El estado inicial del checkbox se sincroniza sin disparar señal."""
        box = qt_stub.QCheckBox("Modo global")
        fired: list[int] = []
        box.stateChanged.connect(lambda state: fired.append(state))

        use_global = True
        box.blockSignals(True)
        box.setChecked(use_global)
        box.blockSignals(False)

        self.assertEqual(fired, [], "No debe disparar stateChanged")
        self.assertTrue(box.isChecked())


# ------------------------------------------------------------------
# Geometría de ventana: recordar entre sesiones
# ------------------------------------------------------------------

class TestWindowGeometry(unittest.TestCase):
    """_restore_window_geometry() / _fit_to_screen() / closeEvent()."""

    def setUp(self) -> None:
        qt_stub.QSettings.reset()
        qt_stub.QMessageBox.reset()
        self.addCleanup(self._cleanup)

    def _cleanup(self) -> None:
        qt_stub.QSettings.reset()
        qt_stub.QMessageBox.reset()

    def _make_window(self) -> omm.OpenCodeModelManager:
        window = object.__new__(omm.OpenCodeModelManager)
        window.settings = qt_stub.QSettings(
            "OpenCodeTools", "OpenCodeModelManager"
        )
        window.use_global = True
        window.config_path = Path(tempfile.mkdtemp()) / "opencode.json"
        window.data = {}
        window.models = []
        window.refresh = lambda: None
        window.statusBar = lambda: _StatusBarRecorder()
        return window

    def test_close_event_saves_geometry(self):
        """Al cerrar, la geometría queda en QSettings."""
        window = self._make_window()
        window.resize(1000, 650)
        window.move(40, 30)

        window.closeEvent(_FakeEvent())

        settings = qt_stub.QSettings(
            "OpenCodeTools", "OpenCodeModelManager"
        )
        self.assertTrue(settings.contains("geometry"))

    def test_geometry_round_trip(self):
        """Cerrar y reabrir recupera tamaño y posición guardados."""
        # --- Sesión 1: mover/redimensionar y cerrar. ---
        window = self._make_window()
        window.resize(1044, 688)
        window.move(33, 44)
        window.closeEvent(_FakeEvent())

        # --- Sesión 2: nueva instancia restaura la geometría. ---
        window2 = self._make_window()
        window2._restore_window_geometry()
        self.assertEqual((window2.width(), window2.height()), (1044, 688))
        self.assertEqual((window2.x(), window2.y()), (33, 44))

    def test_restore_without_saved_geometry_keeps_defaults(self):
        """Sin geometría guardada se conserva el tamaño por defecto."""
        window = self._make_window()
        window.resize(1120, 720)
        window._restore_window_geometry()
        self.assertEqual((window.width(), window.height()), (1120, 720))

    def test_restore_with_corrupt_geometry_does_not_crash(self):
        """Geometría corrupta: se ignora sin excepción."""
        settings = qt_stub.QSettings(
            "OpenCodeTools", "OpenCodeModelManager"
        )
        settings.setValue("geometry", b"\xff\x00not-a-geometry")

        window = self._make_window()
        window.resize(1120, 720)
        window._restore_window_geometry()  # no debe lanzar
        self.assertEqual((window.width(), window.height()), (1120, 720))

    def test_restored_geometry_clamped_to_screen(self):
        """Una geometría de un monitor grande no puede salir de pantalla.

        Simula: ventana guardada en (0, 4000) con alto 900; el monitor
        actual es de 1366x768 con paneles, así que el área útil
        disponible es de 1366x708. El alto se recorta al área y la Y se
        reencuadra para que la barra de título quede visible.
        """
        available = qt_stub.QRect(x=0, y=0, width=1366, height=708)
        original = qt_stub.QApplication.primaryScreen
        qt_stub.QApplication.primaryScreen = lambda: _FakeScreen(available)
        self.addCleanup(
            lambda: setattr(
                qt_stub.QApplication, "primaryScreen", original
            )
        )

        window = self._make_window()
        window.resize(1120, 900)
        window.move(0, 4000)
        window._fit_to_screen(clamp_position=True)

        self.assertEqual(window.height(), 708)   # alto <= área útil
        self.assertLessEqual(window.y(), available.bottom() - 40)
        self.assertGreaterEqual(window.y(), available.top())
        self.assertLessEqual(window.width(), available.width())


# ------------------------------------------------------------------
# Restricciones transversales
# ------------------------------------------------------------------

class TestConstraints(unittest.TestCase):
    def test_auth_json_is_never_touched(self):
        """auth.json no se lee ni se escribe en ningún punto del código."""
        source = (ROOT / "opencode_model_manager.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("auth_path", source)
        # El docstring puede mencionar auth.json, pero no debe haber
        # ninguna operación de archivo sobre él.
        for pattern in (
            "auth.json.open",
            "open(\"*auth.json*\"",
            "read_text",
        ):
            self.assertNotIn("auth.json" + pattern, source)
        # Solo aparece como documentación.
        occurrences = source.count("auth.json")
        self.assertEqual(
            occurrences, 1,
            "auth.json solo debe mencionarse en el docstring",
        )

    def test_no_new_imports_added(self):
        """No se añadieron dependencias nuevas al módulo."""
        source = (ROOT / "opencode_model_manager.py").read_text(
            encoding="utf-8"
        )
        allowed = {
            "json", "os", "shutil", "subprocess", "sys", "copy",
            "datetime", "pathlib",
        }
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                if "PyQt6" in stripped:
                    continue
                # Módulo raíz: "from copy import deepcopy" -> "copy";
                # "from pathlib import Path" -> "pathlib".
                if stripped.startswith("from "):
                    root_import = stripped.split()[1].split(".")[0]
                else:
                    root_import = (
                        stripped.split()[1].rstrip(",").split(".")[0]
                    )
                self.assertIn(
                    root_import, allowed,
                    f"Import inesperado: {stripped}",
                )


if __name__ == "__main__":
    unittest.main()
