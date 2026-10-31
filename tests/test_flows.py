"""Flujos de ventana: árbol plegado, búsqueda, registro, guardado y atajos.

Corren con el stub de PyQt6 sobre un HOME temporal, de modo que ningún test
lee ni escribe la configuración real del usuario (ni su auth.json).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from support import qt_stub  # noqa: F401  (arranque headless del stub)
from omm.catalog import CatalogStore, parse_models_dev
from omm.main_window import (
    PAGE_DETAILS, PAGE_OVERVIEW, PAGE_RESULTS, OpenCodeModelManager,
)
from omm.registry import configured_full_ids
from omm.search import SCOPE_CONFIGURED, SORT_CONTEXT
from omm.ui.panels import ROLE_MID, ROLE_PID

CATALOG = {
    "acme": {
        "id": "acme", "name": "Acme AI", "npm": "@ai-sdk/openai-compatible",
        "api": "https://api.acme.test/v1", "env": ["ACME_API_KEY"],
        "models": {
            "acme-coder": {
                "id": "acme-coder", "name": "Acme Coder",
                "description": "modelo para programar",
                "limit": {"context": 400_000, "output": 32_000},
                "tool_call": True, "reasoning": True,
                "modalities": {"input": ["text"], "output": ["text"]},
                "cost": {"input": 1.0, "output": 4.0},
            },
            "acme-lite": {
                "id": "acme-lite", "name": "Acme Lite",
                "modalities": {"input": ["text", "image"]},
                "cost": {"input": 0, "output": 0},
            },
        },
    },
    "zeta": {
        "id": "zeta", "name": "Zeta Labs", "npm": "@ai-sdk/anthropic",
        "api": "https://api.zeta.test/v1",
        "models": {"zeta-big": {"id": "zeta-big", "name": "Zeta Big",
                                  "limit": {"context": 1_000_000}}},
    },
}

CONFIG = {
    "$schema": "https://opencode.ai/config.json",
    "provider": {
        "acme": {
            "npm": "@ai-sdk/openai-compatible",
            "name": "Acme AI",
            "options": {"baseURL": "https://api.acme.test/v1"},
            "models": {
                "acme-coder": {"name": "Acme Coder",
                               "limit": {"context": 100_000, "output": 4_000},
                               "options": {"temperature": 0.1}},
                "acme-legacy": {"name": "Acme Legacy", "modelID": "legacy-1"},
            },
        },
    },
    "model": "acme/acme-coder",
}

REGISTERED = frozenset({"acme/acme-coder", "acme/acme-legacy"})
SECRET = "sk-NO-DEBE-SALIR"


class _Clipboard:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class _App:
    def __init__(self, clipboard: _Clipboard) -> None:
        self._clipboard = clipboard

    def clipboard(self) -> _Clipboard:
        return self._clipboard


class _WindowCase(unittest.TestCase):
    """Ventana real construida sobre un HOME desechable."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="omm-flow-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self.home = self.tmp / "home"
        (self.home / ".config" / "opencode").mkdir(parents=True)
        self.config_path = self.home / ".config" / "opencode" / "opencode.json"
        self.config_path.write_text(json.dumps(CONFIG), encoding="utf-8")

        self.auth_path = self.home / ".local" / "share" / "opencode" / "auth.json"
        self.auth_path.parent.mkdir(parents=True)
        self.auth_path.write_text(
            json.dumps({"acme": {"type": "api", "key": SECRET}}), encoding="utf-8"
        )
        self.auth_bytes = self.auth_path.read_bytes()

        patcher = mock.patch.dict(os.environ, {
            "HOME": str(self.home),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.tmp / "cache"),
        })
        patcher.start()
        self.addCleanup(patcher.stop)
        # OPENCODE_CONFIG manda la búsqueda al archivo REAL del usuario
        # (discover_config lo mira primero). Un test no debe leerlo nunca:
        # patch.dict lo devuelve tal cual al parar.
        os.environ.pop("OPENCODE_CONFIG", None)

        qt_stub.QSettings.reset()
        qt_stub.QMessageBox.reset()

        self.window = OpenCodeModelManager()
        store = CatalogStore(directory=self.tmp / "catalog")
        store.providers = parse_models_dev(CATALOG)
        self.window.catalog = store
        self.window.update_tree()

    # -- utilidades -------------------------------------------------------
    def page(self) -> int:
        return self.window.workspace.currentIndex()

    def tree_items(self):
        tree = self.window.tree
        return [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]

    def item_by_pid(self, pid: str):
        return next(i for i in self.tree_items() if i.data(0, ROLE_PID) == pid)

    def search(self, text: str) -> None:
        self.window.header.search_edit.setText(text)
        self.window.on_search_changed(text)

    def result_names(self) -> list[str]:
        """Nombres visibles en la lista de resultados (sin sufijos de meta)."""
        return [
            self.window.results.item(i).text().split(" · ")[0]
            for i in range(self.window.results.count())
        ]

    def written(self) -> dict:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def answer(self, yes: bool) -> None:
        qt_stub.QMessageBox.question_reply = (
            qt_stub.QMessageBox.StandardButton.Yes if yes
            else qt_stub.QMessageBox.StandardButton.No
        )


# ---------------------------------------------------------------------------
# Zona derecha: árbol proveedor → modelos
# ---------------------------------------------------------------------------

class TestProviderTree(_WindowCase):
    def test_workspace_is_left_and_tree_is_right(self):
        splitter = self.window.splitter
        self.assertIs(splitter.widget(0), self.window.workspace)
        self.assertIsNot(splitter.widget(1), self.window.workspace)
        self.assertEqual(splitter.sizes(), [860, 300])

    def test_every_provider_starts_collapsed(self):
        items = self.tree_items()
        self.assertEqual(len(items), 2)
        self.assertTrue(all(not item.isExpanded() for item in items))
        self.assertEqual(self.window.tree._loaded_ids, set())

    def test_labels_mark_registered_providers_and_count_models(self):
        self.assertEqual(
            [item.text(0) for item in self.tree_items()],
            ["● Acme AI  (3)", "Zeta Labs  (1)"],
        )

    def test_children_are_loaded_when_expanding(self):
        top = self.item_by_pid("acme")
        top.setExpanded(True)
        self.assertEqual(
            [top.child(j).text(0) for j in range(top.childCount())],
            ["✓ Acme Coder", "✓ Acme Legacy", "Acme Lite"],
        )
        self.assertEqual(self.window.tree._loaded_ids, {"acme"})

    def test_expanding_twice_does_not_duplicate_children(self):
        top = self.item_by_pid("acme")
        top.setExpanded(True)
        self.window.tree._load_children(top)
        self.assertEqual(top.childCount(), 3)

    def test_clicking_a_provider_opens_its_detail(self):
        self.item_by_pid("acme").setExpanded(True)
        self.window.tree._on_clicked(self.item_by_pid("zeta"), 0)
        self.assertEqual(self.page(), PAGE_DETAILS)
        self.assertEqual(self.window._current_kind, "provider")
        self.assertEqual(self.window.details.title.text(), "Zeta Labs")
        self.assertEqual(self.window.details.add_btn.text(), "Agregar modelo")

    def test_clicking_a_model_opens_the_model_detail(self):
        top = self.item_by_pid("acme")
        top.setExpanded(True)
        lite = top.child(2)
        self.window.tree._on_clicked(lite, 0)
        self.assertEqual(self.window._current_entry, ("acme", "acme-lite"))
        self.assertEqual(self.window.details.badge.text(), "Solo en el catálogo")

    def test_expansions_survive_a_tree_rebuild(self):
        self.item_by_pid("acme").setExpanded(True)
        self.window.show_model("acme", "acme-lite")
        self.window.register_current_model()
        top = self.item_by_pid("acme")
        self.assertTrue(top.isExpanded())
        self.assertEqual(top.childCount(), 3)

    def test_registering_marks_the_model_in_the_tree(self):
        self.window.show_model("zeta", "zeta-big")
        self.window.register_current_model()
        top = self.item_by_pid("zeta")
        top.setExpanded(True)
        self.assertEqual([top.child(j).text(0) for j in range(top.childCount())],
                         ["✓ Zeta Big"])


# ---------------------------------------------------------------------------
# La ficha se reconstruye: nada de filas heredadas de la vista anterior
# ---------------------------------------------------------------------------

class TestDetailsCardIsClean(_WindowCase):
    """Cada fila de la ficha entra con addLayout(), así que su item exterior
    no es un widget. Un bucle de limpieza que sólo mire item.widget() no
    borra nada y el usuario ve dos textos superpuestos."""

    def card_labels(self) -> list[str]:
        return [
            label.text()
            for label in self.window.details.card.findChildren(qt_stub.QLabel)
        ]

    def test_rows_are_sublayouts_without_widgets_at_the_top_level(self):
        self.window.show_model("acme", "acme-coder")
        grid = self.window.details.grid
        self.assertGreater(grid.count(), 0)
        for i in range(grid.count()):
            item = grid.itemAt(i)
            self.assertIsNone(item.widget())
            self.assertIsNotNone(item.layout())

    def test_the_card_holds_exactly_the_visible_rows(self):
        self.window.show_model("acme", "acme-coder")
        grid = self.window.details.grid
        # Dos etiquetas por fila (clave y valor) y nada más dentro de la tarjeta.
        self.assertEqual(len(self.card_labels()), grid.count() * 2)

    def test_changing_the_selection_leaves_no_ghost_rows(self):
        self.window.show_model("acme", "acme-coder")
        self.window.show_provider("zeta")
        labels = self.card_labels()
        grid = self.window.details.grid
        self.assertEqual(len(labels), grid.count() * 2)
        self.assertNotIn("Acme Coder", labels)
        self.assertNotIn("acme-coder", labels)
        self.assertNotIn("https://api.acme.test/v1", labels)

    def test_a_third_view_does_not_accumulate_either(self):
        for pid, mid in (("acme", "acme-coder"), ("acme", "acme-lite"),
                         ("zeta", "zeta-big")):
            self.window.show_model(pid, mid)
            grid = self.window.details.grid
            self.assertEqual(len(self.card_labels()), grid.count() * 2)

    def test_repeating_the_same_view_is_idempotent(self):
        self.window.show_model("acme", "acme-coder")
        first = self.card_labels()
        self.window.show_provider("zeta")
        self.window.show_model("acme", "acme-coder")
        self.assertEqual(self.card_labels(), first)


# ---------------------------------------------------------------------------
# Búsqueda y filtros
# ---------------------------------------------------------------------------

class TestSearchFlows(_WindowCase):
    def test_search_finds_everything_even_with_the_tree_collapsed(self):
        self.search("acme")
        self.assertEqual(self.page(), PAGE_RESULTS)
        self.assertEqual(self.window.results.count(), 3)
        self.assertEqual(self.window.tree._loaded_ids, set())

    def test_count_label_shows_the_number_of_matches(self):
        self.search("acme")
        self.assertTrue(
            self.window.header.count_label.text().startswith("3 coincidencias")
        )

    def test_search_covers_endpoint_description_and_registered_ids(self):
        for text, expected in (
            ("zeta.test", ["Zeta Big"]),
            ("programar", ["Acme Coder"]),
            ("legacy", ["Acme Legacy"]),
            ("openai-compatible", ["Acme Coder", "Acme Legacy", "Acme Lite"]),
        ):
            with self.subTest(text=text):
                self.search(text)
                self.assertEqual(self.result_names(), expected)

    def test_no_results_shows_an_empty_list_and_zero_count(self):
        self.search("no-existe")
        self.assertEqual(self.page(), PAGE_RESULTS)
        self.assertEqual(self.window.results.count(), 0)
        self.assertTrue(
            self.window.header.count_label.text().startswith("0 coincidencias")
        )

    def test_filters_combine_with_the_search_text(self):
        self.search("acme")
        self.window.filter_panel.chip_paid.setChecked(True)
        self.assertEqual(self.result_names(), ["Acme Coder"])
        self.assertIn("de pago", self.window.header.count_label.text())

    def test_chips_are_independent_and_stackable(self):
        self.window.filter_panel.chip_reasoning.setChecked(True)
        self.assertEqual(self.result_names(), ["Acme Coder"])
        self.window.filter_panel.chip_reasoning.setChecked(False)
        self.window.filter_panel.chip_vision.setChecked(True)
        self.assertEqual(self.result_names(), ["Acme Lite"])
        self.window.filter_panel.chip_multimodal.setChecked(True)
        self.window.filter_panel.chip_free.setChecked(True)
        self.assertEqual(self.result_names(), ["Acme Lite"])

    def test_scope_filter_uses_the_registered_models(self):
        index = self.window.filter_panel.scope_combo.findData(SCOPE_CONFIGURED)
        self.window.filter_panel.scope_combo.setCurrentIndex(index)
        self.assertEqual(sorted(self.result_names()),
                         ["Acme Coder", "Acme Legacy"])

    def test_sort_by_context_puts_the_largest_first(self):
        self.search("acme")
        self.window.on_sort_changed(SORT_CONTEXT, False)
        self.assertEqual(self.result_names()[0], "Acme Coder")

    def test_clear_button_resets_everything_to_the_overview(self):
        self.search("acme")
        self.window.filter_panel.chip_paid.setChecked(True)
        self.window.filter_panel.clear_btn.clicked.emit()
        self.assertEqual(self.page(), PAGE_OVERVIEW)
        self.assertEqual(self.window.header.search_edit.text(), "")
        self.assertFalse(self.window.filter_panel.chip_paid.isChecked())
        self.assertEqual(self.window.header.count_label.text(), "")

    def test_escape_clears_the_search_and_then_the_filter_panel(self):
        self.window.header.filters_btn.setChecked(True)
        self.assertTrue(self.window.filter_wrap.isVisible())
        self.search("acme")
        self.window.escape_pressed()
        self.assertEqual(self.window.header.search_edit.text(), "")
        self.assertEqual(self.page(), PAGE_OVERVIEW)
        self.window.escape_pressed()
        self.assertFalse(self.window.filter_wrap.isVisible())

    def test_a_catalog_entry_is_never_registered_by_searching(self):
        self.search("acme")
        self.search("zeta")
        self.assertEqual(configured_full_ids(self.window.data), REGISTERED)
        self.assertEqual(self.written(), CONFIG)
        self.assertEqual(self.auth_path.read_bytes(), self.auth_bytes)


# ---------------------------------------------------------------------------
# Alta, edición y baja desde el panel de detalle
# ---------------------------------------------------------------------------

class TestRegistrationFlows(_WindowCase):
    def test_register_writes_only_trusted_catalog_data(self):
        self.window.show_model("acme", "acme-lite")
        self.window.details_add()
        entry = self.window.data["provider"]["acme"]["models"]["acme-lite"]
        self.assertEqual(entry["name"], "Acme Lite")
        self.assertEqual(entry["cost"], {"input": 0, "output": 0})
        self.assertEqual(entry["modalities"], {"input": ["text", "image"]})
        self.assertNotIn("api_key", json.dumps(entry).lower())

    def test_register_creates_the_provider_block_when_missing(self):
        self.window.show_model("zeta", "zeta-big")
        self.window.details_add()
        pdata = self.window.data["provider"]["zeta"]
        self.assertEqual(pdata["npm"], "@ai-sdk/anthropic")
        self.assertEqual(pdata["options"]["baseURL"], "https://api.zeta.test/v1")
        self.assertIn("zeta-big", pdata["models"])

    def test_register_keeps_properties_of_the_already_registered_model(self):
        self.window.show_model("acme", "acme-coder")
        self.window.details_add()
        entry = self.window.data["provider"]["acme"]["models"]["acme-coder"]
        self.assertEqual(entry["options"], {"temperature": 0.1})
        self.assertEqual(entry["limit"], {"context": 400_000, "output": 32_000})

    def test_buttons_follow_the_registration_state(self):
        self.window.show_model("acme", "acme-lite")
        self.assertTrue(self.window.details.add_btn.isEnabled())
        self.assertFalse(self.window.details.edit_btn.isEnabled())
        self.assertFalse(self.window.details.remove_btn.isEnabled())
        self.window.register_current_model()
        self.assertFalse(self.window.details.add_btn.isEnabled())
        self.assertTrue(self.window.details.edit_btn.isEnabled())
        self.assertTrue(self.window.details.remove_btn.isEnabled())

    def test_status_message_points_to_connect_for_credentials(self):
        self.window.show_model("acme", "acme-lite")
        self.window.register_current_model()
        self.assertIn("/connect", self.window.statusBar().last_message)

    def test_set_as_default_needs_a_registered_model(self):
        self.window.show_model("zeta", "zeta-big")
        qt_stub.QMessageBox.information_calls.clear()
        self.window.details_set_default()
        self.assertTrue(qt_stub.QMessageBox.information_calls)
        self.assertEqual(self.window.data.get("model"), "acme/acme-coder")

    def test_set_as_default_updates_model_and_small_model(self):
        self.window.show_model("acme", "acme-lite")
        self.window.register_current_model()
        self.window.details_set_default()
        self.assertEqual(self.window.data["model"], "acme/acme-lite")
        self.window.details_set_default(small=True)
        self.assertEqual(self.window.data["small_model"], "acme/acme-lite")

    def test_copy_id_and_endpoint(self):
        clipboard = _Clipboard()
        original = qt_stub.QApplication._instance
        qt_stub.QApplication._instance = _App(clipboard)
        self.addCleanup(setattr, qt_stub.QApplication, "_instance", original)
        self.window.show_model("acme", "acme-coder")
        self.window.details_copy_id()
        self.assertEqual(clipboard.text, "acme/acme-coder")
        self.window.details_copy_endpoint()
        self.assertEqual(clipboard.text, "https://api.acme.test/v1")

    def test_copy_endpoint_without_known_url_reports_in_the_status_bar(self):
        self.window.catalog.providers["zeta"].api = ""
        self.window.show_provider("zeta")
        self.window.details_copy_endpoint()
        self.assertIn("endpoint", self.window.statusBar().last_message)

    def test_delete_needs_confirmation_and_keeps_the_catalog(self):
        self.window.show_model("zeta", "zeta-big")
        self.window.register_current_model()
        self.answer(False)
        self.window.show_model("zeta", "zeta-big")
        self.window.details_remove()
        self.assertIn("zeta-big", self.window.data["provider"]["zeta"]["models"])

        self.answer(True)
        self.window.details_remove()
        self.assertNotIn("zeta-big", self.window.data["provider"]["zeta"]["models"])
        self.assertIsNotNone(self.window.catalog.model("zeta", "zeta-big"))
        self.assertEqual(self.auth_path.read_bytes(), self.auth_bytes)

    def test_deleting_the_default_model_clears_the_reference(self):
        self.answer(True)
        self.window.show_model("acme", "acme-coder")
        self.window.details_remove()
        self.assertNotIn("model", self.window.data)

    def test_deleting_a_provider_removes_all_its_models(self):
        self.answer(True)
        self.window.show_provider("acme")
        self.window.details_remove()
        self.assertNotIn("acme", self.window.data["provider"])
        self.assertNotIn("model", self.window.data)
        self.assertIsNotNone(self.window.catalog.provider("acme"))
        self.assertEqual(self.auth_path.read_bytes(), self.auth_bytes)

    def test_delete_on_an_unregistered_model_does_nothing(self):
        self.answer(True)
        self.window.show_model("acme", "acme-lite")
        self.window.details_remove()
        self.assertNotIn("acme-lite", self.window.data["provider"]["acme"]["models"])
        self.assertIn("acme-coder", self.window.data["provider"]["acme"]["models"])


class _FakeDialog:
    """Sustituye a los diálogos: define qué devolverán exec()/get_*()."""

    accepted = True
    result: object = None
    spec_errors: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        type(self).last_args = (args, kwargs)

    def exec(self) -> int:
        if not type(self).accepted:
            return qt_stub.QDialog.DialogCode.Rejected
        return qt_stub.QDialog.DialogCode.Accepted

    def get_spec(self):
        return type(self).result

    def errors_for(self, spec):
        return list(type(self).spec_errors)

    def get_data(self):
        return type(self).result


class TestDialogFlows(_WindowCase):
    def test_add_provider_writes_a_validated_spec(self):
        dialog = type("P", (_FakeDialog,), {"result": {
            "id": "nuevo", "name": "Nuevo AI",
            "npm": "@ai-sdk/openai-compatible",
            "baseURL": "http://localhost:11434/v1", "env": ["NUEVO_KEY"],
            "headers": {"X-Tenant": "acme"}, "models": {"m": {"name": "M"}},
        }})
        with mock.patch("omm.main_window.ProviderDialog", dialog):
            self.window.add_provider()
        pdata = self.window.data["provider"]["nuevo"]
        self.assertEqual(pdata["options"]["baseURL"], "http://localhost:11434/v1")
        self.assertEqual(pdata["options"]["headers"], {"X-Tenant": "acme"})
        self.assertIn("/connect", self.window.statusBar().last_message)

    def test_add_provider_refuses_an_invalid_spec(self):
        dialog = type("P", (_FakeDialog,), {
            "result": {"id": "nuevo", "baseURL": "ftp://nope"},
            "spec_errors": ["La Base URL debe empezar por http://"],
        })
        with mock.patch("omm.main_window.ProviderDialog", dialog):
            self.window.add_provider()
        self.assertTrue(qt_stub.QMessageBox.warning_calls)
        self.assertNotIn("nuevo", self.window.data.get("provider", {}))

    def test_cancelling_a_dialog_changes_nothing(self):
        dialog = type("P", (_FakeDialog,), {"accepted": False, "result": None})
        before = json.dumps(self.window.data)
        with mock.patch("omm.main_window.ProviderDialog", dialog):
            self.window.add_provider()
        self.assertEqual(json.dumps(self.window.data), before)

    def test_add_model_registers_id_name_and_limits(self):
        dialog = type("M", (_FakeDialog,), {
            "result": ("modelo-nuevo", "Modelo Nuevo", "real-model-id",
                       {"context": 32_000}),
        })
        with mock.patch("omm.main_window.ModelDialog", dialog):
            self.window.add_model("acme")
        entry = self.window.data["provider"]["acme"]["models"]["modelo-nuevo"]
        self.assertEqual(entry, {"name": "Modelo Nuevo",
                                 "modelID": "real-model-id",
                                 "limit": {"context": 32_000}})

    def test_add_model_rejects_a_duplicated_id(self):
        dialog = type("M", (_FakeDialog,), {
            "result": ("acme-coder", "Choque", "", {}),
        })
        qt_stub.QMessageBox.warning_calls.clear()
        with mock.patch("omm.main_window.ModelDialog", dialog):
            self.window.add_model("acme")
        self.assertTrue(qt_stub.QMessageBox.warning_calls)
        self.assertEqual(
            self.window.data["provider"]["acme"]["models"]["acme-coder"]["name"],
            "Acme Coder",
        )

    def test_add_model_needs_a_registered_provider(self):
        qt_stub.QMessageBox.information_calls.clear()
        self.window.add_model("zeta")
        self.assertTrue(qt_stub.QMessageBox.information_calls)

    def test_edit_model_can_rename_and_keeps_extra_properties(self):
        dialog = type("M", (_FakeDialog,), {
            "result": ("acme-coder-v2", "Acme Coder", "acme-coder", {"output": 8_000}),
        })
        self.window.show_model("acme", "acme-coder")
        with mock.patch("omm.main_window.ModelDialog", dialog):
            self.window.edit_model()
        models = self.window.data["provider"]["acme"]["models"]
        self.assertNotIn("acme-coder", models)
        self.assertEqual(models["acme-coder-v2"]["options"], {"temperature": 0.1})
        self.assertEqual(models["acme-coder-v2"]["limit"],
                         {"context": 100_000, "output": 8_000})
        self.assertEqual(self.window.data["model"], "acme/acme-coder-v2")


# ---------------------------------------------------------------------------
# Guardado, respaldos y detección de cambios externos
# ---------------------------------------------------------------------------

class TestSaveFlows(_WindowCase):
    def backup_dir(self) -> Path:
        return self.config_path.parent / "opencode-backups"

    def test_save_writes_valid_json_with_backups(self):
        self.window.show_model("acme", "acme-lite")
        self.window.register_current_model()
        self.assertTrue(self.window.save_config())
        on_disk = self.written()
        self.assertIn("acme-lite", on_disk["provider"]["acme"]["models"])
        self.assertTrue(self.config_path.with_suffix(".json.backup").exists())
        self.assertEqual(len(list(self.backup_dir().glob("*.backup.json"))), 1)
        self.assertFalse(list(self.config_path.parent.glob("*.tmp")))

    def test_save_keeps_unknown_top_level_keys(self):
        self.window.data["instructions"] = ["usa es"]
        self.window.save_config(quiet=True)
        self.assertEqual(self.written()["instructions"], ["usa es"])

    def test_confirmation_says_credentials_were_not_touched(self):
        qt_stub.QMessageBox.information_calls.clear()
        self.window.save_config()
        title = qt_stub.QMessageBox.information_calls[-1][1]
        self.assertEqual(title, "Guardado")
        self.assertIn("/connect", qt_stub.QMessageBox.information_calls[-1][2])
        self.assertEqual(self.auth_path.read_bytes(), self.auth_bytes)

    def test_invalid_config_is_not_written(self):
        self.window.data["model"] = "sin-barra"
        before = self.config_path.read_bytes()
        qt_stub.QMessageBox.critical_calls.clear()
        self.assertFalse(self.window.save_config())
        self.assertTrue(qt_stub.QMessageBox.critical_calls)
        self.assertEqual(self.config_path.read_bytes(), before)

    def test_external_edit_is_not_overwritten_silently(self):
        external = dict(CONFIG)
        external["instructions"] = ["cambio externo"]
        self.config_path.write_text(json.dumps(external), encoding="utf-8")

        self.answer(False)
        self.window.data["small_model"] = "acme/acme-coder"
        self.assertFalse(self.window.save_config())
        self.assertEqual(self.written().get("instructions"), ["cambio externo"])
        self.assertNotIn("small_model", self.written())

        self.answer(True)
        self.assertTrue(self.window.save_config())
        self.assertEqual(self.written()["small_model"], "acme/acme-coder")

    def test_saving_twice_creates_two_dated_backups(self):
        self.window.save_config(quiet=True)
        stamp = self.window.data.setdefault("provider", {})
        stamp["otro"] = {"npm": "@ai-sdk/openai-compatible",
                         "options": {"baseURL": "https://otro.test/v1"}}
        self.window.save_config(quiet=True)
        self.assertEqual(len(list(self.backup_dir().glob("*.backup.json"))), 2)

    def test_manual_backup_button_copies_the_current_file(self):
        qt_stub.QMessageBox.information_calls.clear()
        self.window.create_backup()
        self.assertTrue(qt_stub.QMessageBox.information_calls)
        self.assertEqual(len(list(self.backup_dir().glob("*.json"))), 1)

    def test_reload_picks_up_what_is_on_disk(self):
        self.window.show_model("acme", "acme-lite")
        self.window.register_current_model()  # sin guardar
        self.window.load_config()
        self.assertNotIn("acme-lite", self.window.data["provider"]["acme"]["models"])


# ---------------------------------------------------------------------------
# Quitar proveedores
# ---------------------------------------------------------------------------

class TestProviderRemoval(_WindowCase):
    """El reporte del usuario: «le di a Quitar proveedor y no funciona».

    El mando sí quitaba el proveedor de la memoria, sin aviso y sin escribir
    el archivo, así que el árbol (que también muestra el catálogo) seguía
    igual. Aquí queda fijado el contrato: confirmación, aviso, nada en disco
    hasta «Guardar».
    """

    def remove_provider(self, pid: str) -> None:
        self.window.show_provider(pid)
        self.answer(True)
        self.window.details.remove_btn.click()

    def test_removal_asks_first_and_is_not_written_yet(self):
        self.remove_provider("acme")
        self.assertEqual(len(qt_stub.QMessageBox.question_calls), 1)
        self.assertNotIn("acme", self.window.providers())
        self.assertIn("acme", self.written()["provider"])
        message = self.window.statusBar().currentMessage()
        self.assertIn("aún no guardado", message)
        self.assertIn("Guardar", message)

    def test_the_save_button_admits_pending_changes(self):
        self.assertEqual(self.window.save_btn.text(), "Guardar")
        self.remove_provider("acme")
        self.assertEqual(self.window.save_btn.text(), "Guardar ●")
        self.assertIn("sin escribir", self.window.save_btn.toolTip())

        self.window.save_config(quiet=True)
        self.assertEqual(self.window.save_btn.text(), "Guardar")
        self.assertNotIn("acme", self.written()["provider"])

    def test_declining_the_confirmation_changes_nothing(self):
        self.window.show_provider("acme")
        self.answer(False)
        self.window.details.remove_btn.click()
        self.assertIn("acme", self.window.providers())
        self.assertEqual(self.window.save_btn.text(), "Guardar")
        self.assertIn("acme", self.written()["provider"])

    def test_a_catalog_only_provider_explains_the_greyed_button(self):
        self.window.show_provider("zeta")
        self.assertFalse(self.window.details.remove_btn.isEnabled())
        self.assertFalse(self.window.details.edit_btn.isEnabled())
        tip = self.window.details.remove_btn.toolTip()
        self.assertIn("catálogo", tip)
        self.assertIn("Abrir…", tip)
        self.assertIn("Modo global", tip)
        self.assertIn("catálogo", self.window.details.edit_btn.toolTip())

    def test_removing_the_provider_drops_its_default_model(self):
        self.assertEqual(self.window.data.get("model"), "acme/acme-coder")
        self.remove_provider("acme")
        self.assertNotIn("model", self.window.data)

    def test_reloading_forgets_the_pending_removal(self):
        """Ctrl+R descarta lo no guardado: el aviso tiene que ser verdad."""
        self.remove_provider("acme")
        self.window.load_config()
        self.assertIn("acme", self.window.providers())
        self.assertEqual(self.window.save_btn.text(), "Guardar")


# ---------------------------------------------------------------------------
# Por qué un mando no actúa con esta entrada
# ---------------------------------------------------------------------------

class TestEntryOriginIsExplained(_WindowCase):
    """El caso B.AI: la fila sigue en el árbol y «Quitar» está gris.

    La explicación sale de una sola frase y se pone en tres sitios: el tooltip
    de la fila del árbol (sin pulsar nada), una fila visible de la ficha (por si
    el tooltip de un botón deshabilitado no se muestra) y los propios botones.
    """

    def card_labels(self) -> list[str]:
        return [
            label.text()
            for label in self.window.details.card.findChildren(qt_stub.QLabel)
        ]

    def other_config(self, data: dict) -> Path:
        """Otro opencode.json (p. ej. el de un proyecto) + recarga."""
        other = self.tmp / "proyecto" / "opencode.json"
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_text(json.dumps(data), encoding="utf-8")
        os.environ["OPENCODE_CONFIG"] = str(other)
        self.addCleanup(os.environ.pop, "OPENCODE_CONFIG", None)
        self.window.load_config()
        return other

    # -- árbol ------------------------------------------------------------
    def test_a_catalog_row_says_it_cannot_be_deleted_here(self):
        tip = self.item_by_pid("zeta").toolTip(0)
        self.assertIn("catálogo de Models.dev", tip)
        self.assertIn("no se puede borrar", tip)
        self.assertIn(str(self.config_path), tip)

    def test_a_registered_row_says_the_opposite(self):
        tip = self.item_by_pid("acme").toolTip(0)
        self.assertIn(f"Registrado en {self.config_path}", tip)
        self.assertNotIn("no se puede borrar", tip)

    def test_model_rows_explain_themselves_too(self):
        for pid, mid, expected in (
            ("acme", "acme-coder", str(self.config_path)),
            ("zeta", "zeta-big", "catálogo de Models.dev"),
        ):
            top = self.item_by_pid(pid)
            self.window.tree._load_children(top)
            child = next(
                top.child(j) for j in range(top.childCount())
                if top.child(j).data(0, ROLE_MID) == mid
            )
            self.assertIn(expected, child.toolTip(0))

    # -- ficha ------------------------------------------------------------
    def test_the_card_repeats_the_explanation_without_hovering(self):
        self.window.show_provider("zeta")
        labels = self.card_labels()
        self.assertIn("Desde esta ventana", labels)
        self.assertIn("catálogo de Models.dev", " ".join(labels))

    def test_the_greyed_buttons_carry_the_same_words(self):
        self.window.show_provider("zeta")
        tip = self.window.details.remove_btn.toolTip()
        self.assertIn("no se puede borrar", tip)
        self.assertEqual(tip, self.window.details.edit_btn.toolTip())

    def test_a_model_view_is_explained_as_well(self):
        self.window.show_model("acme", "acme-coder")
        self.assertIn("Desde esta ventana", self.card_labels())
        self.assertNotIn(
            "no se puede borrar", self.window.details.remove_btn.toolTip()
        )

    # -- y si está en otro archivo ---------------------------------------
    def test_a_provider_registered_elsewhere_is_pointed_to_that_file(self):
        other = self.other_config({
            "provider": {"zeta": {"name": "Zeta", "models": {"zeta-big": {}}}},
        })
        self.window.show_provider("zeta")
        tip = self.window.details.remove_btn.toolTip()
        self.assertIn(str(other), tip)
        self.assertIn("no puede borrarlo", tip)
        self.assertIn(str(self.config_path), tip)
        self.assertFalse(self.window.details.remove_btn.isEnabled())
        self.assertIn(str(other), self.item_by_pid("zeta").toolTip(0))

    def test_a_model_registered_elsewhere_is_pointed_too(self):
        other = self.other_config({
            "provider": {"zeta": {"models": {"zeta-big": {}}}},
        })
        self.window.show_model("zeta", "zeta-big")
        tip = self.window.details.remove_btn.toolTip()
        self.assertIn(str(other), tip)
        self.assertIn(str(self.config_path), tip)

    def test_legacy_providers_key_in_the_other_file_is_understood(self):
        other = self.other_config({"providers": {"zeta": {"models": {}}}})
        self.assertIn(str(other), self.window.where_else("zeta"))

    def test_the_badge_stops_lying_when_it_lives_elsewhere(self):
        other = self.other_config({
            "provider": {"zeta": {"models": {"zeta-big": {}}}},
        })
        self.window.show_provider("zeta")
        self.assertEqual(
            self.window.details.badge.text(), "Registrado en otro archivo"
        )
        self.assertIn(
            f"Registrado en otro archivo: {other}", " ".join(self.card_labels())
        )
        self.window.show_model("zeta", "zeta-big")
        self.assertEqual(
            self.window.details.badge.text(), "Registrado en otro archivo"
        )

    def test_a_row_that_is_only_catalog_is_still_called_catalog(self):
        self.window.show_provider("zeta")
        self.assertEqual(self.window.details.badge.text(), "Solo catálogo")
        self.assertIn(
            "Solo en catálogo (no registrado)", " ".join(self.card_labels())
        )
        self.window.show_model("zeta", "zeta-big")
        self.assertEqual(self.window.details.badge.text(), "Solo en el catálogo")

    def test_a_registered_entry_keeps_its_normal_names(self):
        self.window.show_provider("acme")
        self.assertEqual(self.window.details.badge.text(), "Proveedor")
        self.assertIn("Registrado", " ".join(self.card_labels()))
        self.window.show_model("acme", "acme-coder")
        self.assertEqual(
            self.window.details.badge.text(), "Registrado en OpenCode"
        )

    # -- el atajo «Supr» no pasa por ningún botón gris --------------------
    def test_the_delete_key_says_the_same_thing_as_the_tooltip(self):
        self.window.show_provider("zeta")
        self.window.details_remove()
        message = self.window.statusBar().currentMessage()
        self.assertIn("catálogo de Models.dev", message)
        self.assertIn(str(self.config_path), message)
        self.assertEqual(qt_stub.QMessageBox.question_calls, [])

    def test_the_delete_key_points_at_the_other_file(self):
        other = self.other_config({
            "provider": {"zeta": {"models": {"zeta-big": {}}}},
        })
        self.window.show_provider("zeta")
        self.window.details_remove()
        message = self.window.statusBar().currentMessage()
        self.assertIn(str(other), message)
        self.assertIn("no lo borra de ahí", message)

        self.window.show_model("zeta", "zeta-big")
        self.window.details_remove()
        self.assertIn(str(other), self.window.statusBar().currentMessage())
        self.assertEqual(qt_stub.QMessageBox.question_calls, [])

    # -- lecturas ajenas --------------------------------------------------
    def test_the_open_file_is_never_relisted_as_foreign(self):
        self.assertEqual(self.window.other_config_files(), [])
        other = self.other_config({"provider": {}})
        paths = self.window.other_config_files()
        self.assertEqual([str(p) for p in paths], [str(other)])
        for path in paths:
            self.assertTrue(path.is_file())
            self.assertNotEqual(path.name, "auth.json")

    def test_unreadable_foreign_files_are_skipped_quietly(self):
        broken = self.tmp / "roto.json"
        broken.write_text("{ esto no es json", encoding="utf-8")
        self.assertEqual(
            OpenCodeModelManager._providers_in_file(broken), {}
        )
        lista = self.tmp / "lista.json"
        lista.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(
            OpenCodeModelManager._providers_in_file(lista), {}
        )
        self.assertEqual(
            OpenCodeModelManager._providers_in_file(self.tmp / "no-existe.json"),
            {},
        )

    def test_a_foreign_file_without_providers_contributes_nothing(self):
        self.other_config({"model": "otro/x", "lsp": True})
        self.assertEqual(self.window._foreign_providers, {})
        self.window.show_provider("zeta")
        self.assertNotIn("sino en", self.window.details.remove_btn.toolTip())


# ---------------------------------------------------------------------------
# Atajos de teclado (los slots que ejecutan)
# ---------------------------------------------------------------------------

class TestKeyboardFlows(_WindowCase):
    def test_setup_shortcuts_can_be_reapplied(self):
        self.window.setup_shortcuts()

    def test_ctrl_f_equivalent_focuses_the_search_box(self):
        self.window.focus_search()
        self.assertEqual(self.window.header.search_edit.text(), "")

    def test_delete_slot_removes_the_selected_registered_model(self):
        self.answer(True)
        self.window.show_model("acme", "acme-coder")
        self.window.details_remove()
        self.assertNotIn("acme-coder", self.window.data["provider"]["acme"]["models"])

    def test_escape_is_a_no_op_when_there_is_nothing_to_clear(self):
        self.window.escape_pressed()
        self.assertEqual(self.page(), PAGE_OVERVIEW)

    def test_shortcut_slots_keep_the_config_untouched_on_disk(self):
        before = self.config_path.read_bytes()
        self.window.focus_search()
        self.window.escape_pressed()
        self.assertEqual(self.config_path.read_bytes(), before)


# ---------------------------------------------------------------------------
# Cada mando de filtro tiene que provocar la búsqueda él solo
# (regresión: los combos y la casilla estaban sin conectar).
# ---------------------------------------------------------------------------

class TestFilterWiring(_WindowCase):
    def test_scope_combo_alone_refreshes_the_results(self):
        self.search("acme")
        self.assertEqual(sorted(self.result_names()),
                         ["Acme Coder", "Acme Legacy", "Acme Lite"])
        index = self.window.filter_panel.scope_combo.findData(SCOPE_CONFIGURED)
        self.window.filter_panel.scope_combo.setCurrentIndex(index)
        self.assertEqual(sorted(self.result_names()),
                         ["Acme Coder", "Acme Legacy"])

    def test_protocol_combo_alone_refreshes_the_results(self):
        index = self.window.filter_panel.protocol_combo.findData("anthropic")
        self.window.filter_panel.protocol_combo.setCurrentIndex(index)
        self.assertEqual(self.result_names(), ["Zeta Big"])

    def test_local_checkbox_alone_refreshes_the_results(self):
        self.search("acme")
        self.window.filter_panel.local_check.setChecked(True)
        self.assertEqual(self.result_names(), [])

    def test_nothing_local_in_the_catalog_leaves_an_explanatory_notice(self):
        self.window.filter_panel.local_check.setChecked(True)
        self.assertEqual(self.window.results.count(), 0)
        self.assertTrue(self.window.results._empty.isVisible())

    def test_results_with_matches_keep_the_notice_hidden(self):
        self.search("acme")
        self.assertFalse(self.window.results._empty.isVisible())

    def test_clearing_filters_does_not_retrigger_the_search_twice(self):
        self.search("acme")
        calls = []
        self.window.filter_panel.filters_changed.connect(
            lambda: calls.append(1)
        )
        self.window.filter_panel.scope_combo.setCurrentIndex(1)
        self.window.clear_all()
        self.assertEqual(len(calls), 1, "Limpiar no debe reemitir desde los combos")

    def test_enter_on_a_row_opens_the_model_details(self):
        self.search("acme")
        self.window.results.keyPressEvent(
            qt_stub.QKeyEvent(qt_stub.Qt.Key.Key_Return)
        )
        self.assertEqual(self.page(), PAGE_DETAILS)
        self.assertEqual(self.window._current_entry, ("acme", "acme-coder"))

    def test_small_model_button_writes_small_model(self):
        self.window.show_model("acme", "acme-coder")
        self.assertTrue(self.window.details.small_btn.isEnabled())
        self.window.details.small_btn.click()
        self.assertEqual(self.window.data.get("small_model"), "acme/acme-coder")
        self.assertEqual(self.written().get("small_model"), None)

    def test_small_model_survives_a_save(self):
        self.window.show_model("acme", "acme-coder")
        self.window.details.small_btn.click()
        self.window.save_config(quiet=True)
        self.assertEqual(self.written()["small_model"], "acme/acme-coder")

    def test_small_model_button_is_disabled_for_a_catalog_only_model(self):
        self.window.show_model("acme", "acme-lite")
        self.assertFalse(self.window.details.small_btn.isEnabled())

    def test_small_model_button_is_disabled_for_a_provider(self):
        self.window.show_provider("zeta")
        self.assertFalse(self.window.details.small_btn.isEnabled())


# ---------------------------------------------------------------------------
# Probar conexión
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Respuesta mínima: status, cabeceras, read() y close()."""

    def __init__(self, status: int = 200, payload=None) -> None:
        self.status = status
        self.code = status
        self.headers = {}
        self._body = json.dumps(payload or {}).encode("utf-8")

    def read(self, amount: int = -1) -> bytes:
        return self._body[:amount] if amount >= 0 else self._body

    def close(self) -> None:
        pass


class _Opener:
    """opener(request, timeout) fijo: ni red ni sorpresas, y guarda lo enviado."""

    def __init__(self, payload=None, status: int = 200) -> None:
        self.payload = payload or {"object": "list", "data": [
            {"id": "acme-coder"}, {"id": "acme-lite"}, {"id": "otro"},
        ]}
        self.status = status
        self.requests: list = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return _FakeResponse(self.status, self.payload)

    def header(self, name: str) -> str:
        return self.requests[-1].get_header(name) or ""

    def headers(self) -> dict:
        return {k.lower(): v for k, v in self.requests[-1].header_items()}


class TestConnectionProbe(_WindowCase):
    """«Probar conexión»: se prueba, se explica y no se filtra nada.

    El stub no ejecuta hilos: el test llama a ``run()`` a mano, igual que el
    worker haría al terminar. La red se sustituye por un opener fijo.
    """

    TEST_KEY = "sk-proba-NO-DEBE-SALIR"

    def setUp(self) -> None:
        super().setUp()
        self.opener = _Opener()
        self.window.probe_opener = self.opener

    # -- utilidades -------------------------------------------------------
    def card_labels(self) -> list[str]:
        return [
            label.text()
            for label in self.window.details.card.findChildren(qt_stub.QLabel)
        ]

    def status(self) -> str:
        return self.window.statusBar().currentMessage()

    def run_probe(self, with_key: bool = False) -> None:
        self.window.details_probe(with_key)
        worker = self.window.probe_worker
        self.assertIsNotNone(worker, "la prueba no llegó a lanzarse")
        worker.run()
        worker.finished.emit()

    def add_provider(self, pid: str, **fields) -> None:
        from omm.catalog import ProviderEntry
        self.window.catalog.providers[pid] = ProviderEntry(id=pid, **fields)
        self.window.update_tree()

    # -- el botón ---------------------------------------------------------
    def test_a_registered_provider_can_be_probed(self):
        self.window.show_provider("acme")
        self.assertTrue(self.window.details.probe_btn.isEnabled())
        self.assertIn("no gasta tokens", self.window.details.probe_btn.toolTip())

    def test_a_catalog_only_provider_can_be_probed_too(self):
        self.window.show_provider("zeta")
        self.assertTrue(self.window.details.probe_btn.isEnabled())

    def test_a_provider_without_endpoint_explains_the_greyed_button(self):
        self.add_provider("sinapi", name="Sin API", api="")
        self.window.show_provider("sinapi")
        self.assertFalse(self.window.details.probe_btn.isEnabled())
        self.assertIn("No hay URL", self.window.details.probe_btn.toolTip())

    def test_metadata_addresses_are_refused_before_any_request(self):
        self.add_provider(
            "nube", name="Nube", api="http://169.254.169.254/latest/meta-data/",
        )
        self.window.show_provider("nube")
        self.assertFalse(self.window.details.probe_btn.isEnabled())
        self.assertIn("metadatos", self.window.details.probe_btn.toolTip())
        self.window.details.probe_btn.click()
        self.window.details_probe(False)
        self.assertEqual(self.opener.requests, [])
        self.assertIn("metadatos", self.status())

    def test_an_unsupported_protocol_says_so(self):
        self.add_provider(
            "brt", name="Bedrock",
            npm="@aws-sdk/client-bedrock-runtime",
            api="https://bedrock-runtime.us-east-1.amazonaws.com",
        )
        self.window.show_provider("brt")
        self.assertFalse(self.window.details.probe_btn.isEnabled())
        self.assertIn("bedrock", self.window.details.probe_btn.toolTip())

    def test_the_key_button_is_hidden_without_the_variable(self):
        os.environ.pop("ACME_API_KEY", None)
        self.window.show_provider("acme")
        self.assertFalse(self.window.details.probe_key_btn.isVisible())

    def test_the_key_button_appears_when_the_variable_is_present(self):
        with mock.patch.dict(os.environ, {"ACME_API_KEY": self.TEST_KEY}):
            self.window.show_provider("acme")
            self.assertTrue(self.window.details.probe_key_btn.isVisible())
            self.assertTrue(self.window.details.probe_key_btn.isEnabled())
            tip = self.window.details.probe_key_btn.toolTip()
        self.assertIn("ACME_API_KEY", tip)
        self.assertIn("HTTPS", tip)
        self.assertNotIn(self.TEST_KEY, tip)

    def test_the_env_row_says_present_or_absent_but_never_the_value(self):
        os.environ.pop("ACME_API_KEY", None)
        self.window.show_provider("acme")
        self.assertIn("ACME_API_KEY (ausente)", self.card_labels())
        with mock.patch.dict(os.environ, {"ACME_API_KEY": self.TEST_KEY}):
            self.window.show_provider("acme")
        joined = " ".join(self.card_labels())
        self.assertIn("ACME_API_KEY (presente)", joined)
        self.assertNotIn(self.TEST_KEY, joined)

    # -- la prueba --------------------------------------------------------
    def test_the_result_is_rendered_in_the_card(self):
        self.window.show_provider("acme")
        self.window.details.probe_btn.click()
        self.assertEqual(self.window.details.probe_btn.text(), "Probando…")
        self.assertFalse(self.window.details.probe_btn.isEnabled())
        self.window.probe_worker.run()
        self.window.probe_worker.finished.emit()

        labels = self.card_labels()
        self.assertIn("Prueba de conexión", labels)
        report = next(
            text for text in labels if text.startswith("Endpoint operativo")
        )
        self.assertIn("tus modelos: 1/2", report)
        self.assertIn("faltan acme-legacy", report)
        self.assertIn("GET https://api.acme.test/v1/models", report)
        self.assertIn("Prueba de conexión: Endpoint operativo", self.status())
        self.assertEqual(self.window.details.probe_btn.text(), "Probar conexión")
        self.assertTrue(self.window.details.probe_btn.isEnabled())

    def test_the_anonymous_probe_sends_no_credentials(self):
        self.window.show_provider("acme")
        self.run_probe()
        headers = self.opener.headers()
        self.assertNotIn("authorization", headers)
        self.assertNotIn("x-api-key", headers)

    def test_the_probe_proves_the_model_in_the_card(self):
        self.window.show_model("acme", "acme-coder")
        self.run_probe()
        report = next(
            text for text in self.card_labels()
            if text.startswith("Endpoint operativo")
        )
        self.assertIn("tus modelos: 1/1", report)
        self.assertNotIn("faltan", report)

    def test_a_model_that_the_endpoint_does_not_list_is_named(self):
        self.opener.payload = {"data": [{"id": "acme-coder"}]}
        self.window.show_model("acme", "acme-legacy")
        self.run_probe()
        report = next(
            text for text in self.card_labels()
            if text.startswith("Endpoint operativo")
        )
        self.assertIn("faltan acme-legacy", report)

    def test_a_401_without_a_key_is_a_live_endpoint(self):
        self.opener.status = 401
        self.window.show_provider("acme")
        self.run_probe()
        self.assertIn("pide credenciales", " ".join(self.card_labels()))

    def test_probing_with_the_environment_key(self):
        self.opener.status = 401
        with mock.patch.dict(os.environ, {"ACME_API_KEY": self.TEST_KEY}):
            self.window.show_provider("acme")
            self.run_probe(with_key=True)
        self.assertEqual(self.opener.header("Authorization"), f"Bearer {self.TEST_KEY}")
        joined = " ".join(self.card_labels())
        self.assertIn("rechaza tu clave", joined)
        self.assertNotIn(self.TEST_KEY, joined)
        self.assertNotIn(self.TEST_KEY, self.status())

    def test_the_probe_never_touches_disk(self):
        before = self.config_path.read_bytes()
        with mock.patch.dict(os.environ, {"ACME_API_KEY": self.TEST_KEY}):
            self.window.show_provider("acme")
            self.run_probe(with_key=True)
        self.assertEqual(self.config_path.read_bytes(), before)
        self.assertEqual(self.auth_path.read_bytes(), self.auth_bytes)
        self.assertEqual(list(self.tmp.rglob("*.tmp")), [])

    def test_the_result_survives_navigation(self):
        self.window.show_provider("acme")
        self.run_probe()
        self.window.show_provider("zeta")
        self.assertNotIn("Prueba de conexión", self.card_labels())
        self.window.show_provider("acme")
        self.assertIn("Prueba de conexión", self.card_labels())

    def test_a_second_probe_is_refused_while_one_is_running(self):
        class Busy:
            @staticmethod
            def isRunning() -> bool:
                return True

        self.window.show_provider("acme")
        self.window.probe_worker = Busy()
        self.window.details_probe(False)
        self.assertIsInstance(self.window.probe_worker, Busy)
        self.assertIn("en curso", self.status())

    def test_without_an_open_card_the_shortcut_explains_itself(self):
        self.window.show_overview()
        self.window.details_probe(False)
        self.assertIsNone(self.window.probe_worker)
        self.assertIn("Abre primero", self.status())

    def test_the_report_never_leaks_the_key_even_if_the_endpoint_echoes_it(self):
        from omm.probe import probe_endpoint
        with mock.patch.dict(os.environ, {"ACME_API_KEY": self.TEST_KEY}):
            self.window.show_provider("acme")
            result = probe_endpoint(
                "https://api.acme.test/v1", "openai-compatible",
                api_key=self.TEST_KEY, env_name="ACME_API_KEY",
                opener=lambda request, timeout: (_ for _ in ()).throw(
                    urllib.error.URLError(f"no autorizado: {self.TEST_KEY}")
                ),
            )
        self.assertNotIn(self.TEST_KEY, result.report())


if __name__ == "__main__":
    unittest.main()
