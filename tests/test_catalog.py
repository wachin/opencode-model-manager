"""Pruebas del catálogo: análisis de Models.dev, caché en disco y modo offline.

Ningún test toca la red: se sustituye ``CatalogStore.fetch`` por un stub.
"""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from dataclasses import fields
from pathlib import Path

from support import catalog, qt_stub  # noqa: F401

from omm.catalog import (
    CatalogStore, ModelEntry, ProviderEntry, is_local_url, normalize_base_url,
    parse_models_dev, resolve_protocol, seed_providers,
)

PAYLOAD = {
    "acme": {
        "id": "acme",
        "name": "Acme AI",
        "npm": "@ai-sdk/openai-compatible",
        "api": "https://api.acme.test/v1",
        "env": ["ACME_API_KEY"],
        "doc": "https://docs.acme.test",
        "source": "https://acme.test/pricing",
        "models": {
            "acme-big": {
                "id": "acme-big",
                "name": "Acme Big",
                "description": "Modelo generalista con contexto largo",
                "type": "chat",
                "reasoning": True,
                "tool_call": True,
                "attachment": True,
                "limit": {"context": 1_000_000, "output": 32_000},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
                "cost": {"input": 2.5, "output": 10.0},
                "release_date": "2026-01-02",
                "status": "beta",
                "supportet_parameters": ["temperature"],
            },
            "acme-free": {
                "id": "acme-free",
                "name": "Acme Free",
                "limit": {"context": 8192},
                "cost": {"input": 0, "output": 0},
            },
            "broken-entry": "no-es-un-objeto",
        },
    },
    "ollama-like": {
        "id": "ollama-like",
        "name": "Ollama Like",
        "npm": "@ai-sdk/openai-compatible",
        "api": "http://localhost:11434/v1",
        "models": {"llama-local": {"id": "llama-local", "name": "Llama Local"}},
    },
    "malformed": {"name": "Sin modelos"},
}


class TestParsing(unittest.TestCase):
    def test_documented_fields_are_mapped(self):
        providers = parse_models_dev(PAYLOAD)
        model = providers["acme"].models["acme-big"]

        self.assertEqual(model.provider_name, "Acme AI")
        self.assertEqual(model.context, 1_000_000)
        self.assertEqual(model.output_limit, 32_000)
        self.assertEqual(model.protocol, "openai-compatible")
        self.assertEqual(model.base_url, "https://api.acme.test/v1")
        self.assertTrue(model.reasoning)
        self.assertTrue(model.tool_call)
        self.assertTrue(model.vision)
        self.assertEqual(model.input_modalities, ["text", "image"])
        self.assertEqual(model.pricing.input, 2.5)
        self.assertEqual(model.status, "beta")

    def test_malformed_entries_are_skipped_not_fatal(self):
        providers = parse_models_dev(PAYLOAD)
        self.assertNotIn("malformed", providers)
        self.assertNotIn("broken-entry", providers["acme"].models)
        self.assertIn("acme-free", providers["acme"].models)

    def test_unknown_metadata_survives_in_raw(self):
        model = parse_models_dev(PAYLOAD)["acme"].models["acme-big"]
        self.assertEqual(
            model.raw["supportet_parameters"], ["temperature"]
        )
        self.assertEqual(model.source, "models.dev")

    def test_missing_data_is_none_not_invented(self):
        model = parse_models_dev(PAYLOAD)["acme"].models["acme-free"]
        self.assertIsNone(model.output_limit)
        self.assertIsNone(model.reasoning)
        self.assertIsNone(model.tool_call)
        self.assertEqual(model.input_modalities, [])

    def test_search_text_covers_names_endpoint_and_description(self):
        model = parse_models_dev(PAYLOAD)["acme"].models["acme-big"]
        for needle in ("acme big", "api.acme.test", "contexto largo", "acme-big"):
            with self.subTest(needle=needle):
                self.assertIn(needle, model.search_text)

    def test_free_variant_and_pricing(self):
        providers = parse_models_dev(PAYLOAD)
        self.assertTrue(providers["acme"].models["acme-free"].pricing.is_free)
        self.assertFalse(providers["acme"].models["acme-big"].pricing.is_free)
        freeish = ProviderEntry(id="openrouter", name="OpenRouter")
        freeish.models["x:free"] = ModelEntry(
            id="x:free", name="X (free)", provider_id="openrouter"
        )
        self.assertTrue(freeish.models["x:free"].free_variant)


class TestProtocolHelpers(unittest.TestCase):
    def test_protocol_from_npm_package(self):
        cases = {
            "@ai-sdk/openai": "openai",
            "@ai-sdk/anthropic": "anthropic",
            "@ai-sdk/google": "google",
            "@ai-sdk/amazon-bedrock": "bedrock",
            "@ai-sdk/openai-compatible": "openai-compatible",
            "@openrouter/ai-sdk-provider": "other",
        }
        for npm, expected in cases.items():
            with self.subTest(npm=npm):
                self.assertEqual(resolve_protocol(npm, None), expected)

    def test_local_urls_are_openai_compatible_and_detected(self):
        self.assertTrue(is_local_url("http://127.0.0.1:1234/v1"))
        self.assertTrue(is_local_url("http://localhost:11434/v1"))
        self.assertFalse(is_local_url("https://api.acme.test/v1"))
        self.assertEqual(
            resolve_protocol(None, "http://localhost:11434/v1"),
            "openai-compatible",
        )

    def test_base_url_validation_rejects_non_http(self):
        for bad in ("", "   ", "ftp://acme.test", "https://", "javascript:alert(1)"):
            with self.subTest(bad=bad):
                self.assertIsNone(normalize_base_url(bad))
        self.assertEqual(normalize_base_url("https://api.b.ai/v1"), "https://api.b.ai/v1")


class TestStore(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def test_offline_starts_from_seed_without_cache(self):
        store = CatalogStore(directory=self.dir)
        self.assertFalse(store.load_cache())
        self.assertGreater(store.model_count, 0)
        self.assertIn("bai", store.providers)
        description = store.describe_source()
        self.assertIn("models.dev", description)
        self.assertIn("MIT", description)

    def test_refresh_writes_cache_and_reloads_offline(self):
        store = CatalogStore(directory=self.dir)
        original_fetch = CatalogStore.fetch
        CatalogStore.fetch = staticmethod(lambda *a, **kw: PAYLOAD)
        self.addCleanup(setattr, CatalogStore, "fetch", original_fetch)

        total = store.refresh()
        self.assertEqual(total, store.model_count)
        self.assertTrue((self.dir / "models_dev.json").exists())
        meta = json.loads((self.dir / "models_dev.meta.json").read_text())
        self.assertEqual(meta["license"], "MIT (sst/models.dev)")
        self.assertIn("fetched_at", meta)

        offline = CatalogStore(directory=self.dir)
        self.assertTrue(offline.load_cache())
        self.assertIn("acme", offline.providers)
        self.assertEqual(
            offline.providers["acme"].models["acme-big"].context, 1_000_000
        )
        self.assertIsNotNone(offline.last_updated)

    def test_models_dev_wins_over_seed_for_same_model(self):
        store = CatalogStore(directory=self.dir)
        seed_before = store.providers["bai"].models["deepseek-v4-flash"].source
        payload = {
            "bai": {
                "id": "bai", "name": "B.AI", "source": "https://b.ai",
                "models": {
                    "deepseek-v4-flash": {"id": "deepseek-v4-flash", "name": "DS", "limit": {"context": 1048576}},
                },
            }
        }
        store._merge_source(parse_models_dev(payload))
        model = store.providers["bai"].models["deepseek-v4-flash"]
        self.assertEqual(seed_before, "seed")
        self.assertEqual(model.source, "models.dev")
        self.assertEqual(model.context, 1_048_576)

    def test_failed_download_keeps_previous_data(self):
        store = CatalogStore(directory=self.dir)
        original_fetch = CatalogStore.fetch
        CatalogStore.fetch = staticmethod(
            lambda *a, **kw: (_ for _ in ()).throw(urllib.error.URLError("sin red"))
        )
        self.addCleanup(setattr, CatalogStore, "fetch", original_fetch)
        before = store.model_count
        with self.assertRaises(urllib.error.URLError):
            store.refresh()
        self.assertEqual(store.model_count, before)
        self.assertFalse((self.dir / "models_dev.json.tmp").exists())

    def test_lookup_helpers(self):
        store = CatalogStore(directory=self.dir)
        store._merge_source(parse_models_dev(PAYLOAD))
        self.assertIsNotNone(store.provider("acme"))
        self.assertIsNotNone(store.model("acme", "acme-big"))
        self.assertIsNone(store.model("acme", "no-existe"))
        self.assertIsNone(store.provider("no-existe"))
        self.assertEqual(len(store.all_models()), store.model_count)


class TestCatalogHasNoCredentials(unittest.TestCase):
    """El catálogo describe APIs; nunca almacena secretos."""

    def test_entry_fields_are_not_secrets(self):
        for entry_class in (ModelEntry, ProviderEntry):
            names = [field.name.lower() for field in fields(entry_class)]
            for marker in ("apikey", "api_key", "token", "secret", "password"):
                with self.subTest(cls=entry_class.__name__, marker=marker):
                    self.assertNotIn(marker, "".join(names))
                    self.assertFalse(any(marker in name for name in names))

    def test_seed_providers_are_local_data(self):
        providers = seed_providers()
        self.assertTrue(providers)
        for pid, entry in providers.items():
            self.assertEqual(entry.source, "seed")
            self.assertTrue(entry.npm)
            self.assertNotIn("key", {k.lower() for k in entry.raw})


if __name__ == "__main__":
    unittest.main()
