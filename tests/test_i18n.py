"""Idioma de la interfaz: inglés como fuente y español al lado.

Los tests del resto de módulos comprueban los textos en español (ver
``support.py``); aquí se verifica el valor por defecto inglés, la
precedencia al arrancar, el cambio en caliente y la persistencia.
"""

from __future__ import annotations

import os
import unittest
from unittest import mock

from support import qt_stub  # noqa: F401  (arranque headless del stub)

from omm.i18n import (
    DEFAULT_LANGUAGE, format_int, get_language, init_language,
    resolve_language, set_language, tr, trn,
)
from omm.main_window import OpenCodeModelManager
from omm.registry import action_note
from omm.search import SCOPE_CONFIGURED, Filters
from omm.ui.panels import FilterPanel, HeaderBar


class _Stored:
    """QSettings mínimo: devuelve el idioma guardado o el valor por defecto."""

    def __init__(self, language):
        self._language = language

    def value(self, _key, default=None):
        return default if self._language is None else self._language


class LanguageTestCase(unittest.TestCase):
    def setUp(self):
        self._previous = get_language()

    def tearDown(self):
        set_language(self._previous)


class TestTranslationHelpers(LanguageTestCase):
    def test_english_is_the_default(self):
        set_language(DEFAULT_LANGUAGE)
        self.assertEqual(get_language(), "en")
        self.assertEqual(tr("Save", es="Guardar"), "Save")
        self.assertEqual(tr("Tool calling"), "Tool calling")

    def test_spanish_is_returned_when_selected(self):
        set_language("es")
        self.assertEqual(tr("Save", es="Guardar"), "Guardar")
        self.assertEqual(tr("Untranslated text"), "Untranslated text")

    def test_plurals_follow_the_language(self):
        set_language("en")
        self.assertEqual(
            trn(1, "{count} model", "{count} models",
                es_one="{count} modelo", es_many="{count} modelos")
            .format(count=1),
            "1 model",
        )
        self.assertEqual(
            trn(2, "{count} model", "{count} models",
                es_one="{count} modelo", es_many="{count} modelos")
            .format(count=2),
            "2 models",
        )
        set_language("es")
        self.assertEqual(
            trn(1, "{count} model", "{count} models",
                es_one="{count} modelo", es_many="{count} modelos")
            .format(count=1),
            "1 modelo",
        )
        self.assertEqual(
            trn(2, "{count} model", "{count} models",
                es_one="{count} modelo", es_many="{count} modelos")
            .format(count=2),
            "2 modelos",
        )

    def test_thousands_separator_follows_the_language(self):
        set_language("en")
        self.assertEqual(format_int(1234567), "1,234,567")
        set_language("es")
        self.assertEqual(format_int(1234567), "1.234.567")

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(set_language("fr"), "en")
        self.assertEqual(set_language(""), "en")
        self.assertEqual(set_language(None), "en")


class TestStartupPrecedence(LanguageTestCase):
    def test_environment_wins_over_the_stored_choice(self):
        with mock.patch.dict(os.environ, {"OMM_LANG": "es"}):
            self.assertEqual(init_language(_Stored("en")), "es")

    def test_stored_choice_is_used_without_environment(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OMM_LANG", None)
            self.assertEqual(init_language(_Stored("es")), "es")
            self.assertEqual(init_language(_Stored(None)), "en")

    def test_resolve_language_precedence(self):
        self.assertEqual(resolve_language(None, None), "en")
        self.assertEqual(resolve_language("es", "en"), "es")
        self.assertEqual(resolve_language(None, "es"), "es")
        self.assertEqual(resolve_language("fr", "es"), "es")
        self.assertEqual(resolve_language("EN", None), "en")


class TestLiveRetranslation(LanguageTestCase):
    def test_header_and_filters_switch_without_losing_state(self):
        set_language("en")
        header = HeaderBar()
        filters = FilterPanel()
        header.search_edit.setText("acme")
        filters.chip_paid.setChecked(True)

        self.assertEqual(header.filters_btn.text(), "Filters")
        self.assertEqual(header.sort_combo.itemText(1), "Provider")
        self.assertEqual(filters.chip_free.text(), "Free")
        self.assertEqual(filters.clear_btn.text(), "Clear filters")

        set_language("es")
        header.retranslate()
        filters.retranslate()

        self.assertEqual(header.filters_btn.text(), "Filtros")
        self.assertEqual(header.sort_combo.itemText(1), "Proveedor")
        self.assertEqual(filters.chip_free.text(), "Gratis")
        self.assertEqual(filters.clear_btn.text(), "Limpiar filtros")
        self.assertEqual(header.search_edit.text(), "acme")
        self.assertTrue(filters.chip_paid.isChecked())
        self.assertEqual(header.language_combo.currentData(), "es")

    def test_save_button_tracks_language_and_dirty_state(self):
        window = object.__new__(OpenCodeModelManager)
        window.save_btn = qt_stub.QPushButton("")
        window._is_dirty = lambda: False

        set_language("en")
        window._update_save_button()
        self.assertEqual(window.save_btn.text(), "Save")

        window._is_dirty = lambda: True
        window._update_save_button()
        self.assertEqual(window.save_btn.text(), "Save ●")

        set_language("es")
        window._update_save_button()
        self.assertEqual(window.save_btn.text(), "Guardar ●")

    def test_change_language_persists_the_choice(self):
        settings = qt_stub.QSettings("OpenCodeTools", "OpenCodeModelManager")
        window = object.__new__(OpenCodeModelManager)
        window.settings = settings
        window.retranslate_ui = lambda: None

        window.change_language("es")
        self.assertEqual(get_language(), "es")
        self.assertEqual(settings.value("language"), "es")

        window.change_language("fr")
        self.assertEqual(get_language(), "en")
        self.assertEqual(settings.value("language"), "en")


class TestTranslatedDomainText(LanguageTestCase):
    def test_filter_summary_is_translated(self):
        set_language("en")
        summary = Filters(scope=SCOPE_CONFIGURED).summary()
        self.assertIn("registered in OpenCode", summary)
        set_language("es")
        summary = Filters(scope=SCOPE_CONFIGURED).summary()
        self.assertIn("registrados en OpenCode", summary)

    def test_action_note_is_translated(self):
        set_language("en")
        note = action_note("Acme", True, "/tmp/opencode.json")
        self.assertIn("Edit", note)
        self.assertIn("Remove", note)
        set_language("es")
        note = action_note("Acme", True, "/tmp/opencode.json")
        self.assertIn("Editar", note)
        self.assertIn("Quitar", note)


if __name__ == "__main__":
    unittest.main()
