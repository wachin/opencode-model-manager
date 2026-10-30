"""Pruebas del motor de búsqueda: texto, filtros combinables y orden."""

from __future__ import annotations

import unittest

from support import search as _search_module  # noqa: F401

from omm.catalog import parse_models_dev
from omm.search import (
    PROTOCOL_ANY, PROTOCOL_OTHER, SCOPE_ALL, SCOPE_CONFIGURED,
    SCOPE_UNCONFIGURED, SORT_CONTEXT, SORT_NAME, SORT_PRICE, SORT_PROVIDER,
    Filters, catalog_pairs, matches_text, search,
)

FIXTURE = {
    "acme": {
        "id": "acme", "name": "Acme AI", "npm": "@ai-sdk/openai-compatible",
        "api": "https://api.acme.test/v1", "source": "https://acme.test",
        "models": {
            "acme-coder": {
                "id": "acme-coder", "name": "Acme Coder",
                "description": "modelo para programar",
                "reasoning": True, "tool_call": True,
                "limit": {"context": 400_000, "output": 64_000},
                "modalities": {"input": ["text"], "output": ["text"]},
                "cost": {"input": 1.0, "output": 4.0},
            },
            "acme-vision": {
                "id": "acme-vision", "name": "Acme Vision",
                "attachment": True, "tool_call": False,
                "limit": {"context": 32_000},
                "modalities": {"input": ["text", "image"], "output": ["text"]},
                "cost": {"input": 0, "output": 0},
            },
            "acme-unknown": {"id": "acme-unknown", "name": "Acme Unknown"},
        },
    },
    "local-ai": {
        "id": "local-ai", "name": "Local AI", "npm": "@ai-sdk/openai-compatible",
        "api": "http://localhost:11434/v1",
        "models": {
            "llama-local": {
                "id": "llama-local", "name": "Llama Local",
                "limit": {"context": 128_000},
                "cost": {"input": 0, "output": 0},
            },
        },
    },
    "claude-house": {
        "id": "claude-house", "name": "Claude House",
        "npm": "@ai-sdk/anthropic", "api": "https://api.claudehouse.test",
        "models": {
            "opus": {
                "id": "opus", "name": "Opus", "reasoning": True,
                "tool_call": True, "attachment": True,
                "limit": {"context": 200_000},
                "cost": {"input": 15.0, "output": 75.0},
            },
        },
    },
}


def universe():
    return parse_models_dev(FIXTURE)


def pairs(filters_configured=None, providers=None):
    return catalog_pairs(providers or universe()), filters_configured


def run(filters: Filters, providers=None, configured=None):
    return search(
        catalog_pairs(providers or universe()),
        filters,
        configured if configured is not None else frozenset(),
    )


class TestTextSearch(unittest.TestCase):
    def test_matches_provider_name_model_id_description_and_endpoint(self):
        cases = {
            "acme": 3,             # nombre de proveedor + ids
            "claudehouse": 1,      # endpoint
            "programar": 1,        # descripción
            "llama-local": 1,      # id exacto del modelo
            "opus": 1,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                found, total = run(Filters(text=text))
                self.assertEqual(total, expected)
                self.assertEqual(len(found), expected)

    def test_words_are_combined_with_and(self):
        found, total = run(Filters(text="acme reasoning"))
        self.assertEqual(total, 0)  # "reasoning" no es texto libre: usa descripciones
        found, total = run(Filters(text="acme coder"))
        self.assertEqual(total, 1)
        self.assertEqual(found[0].id, "acme-coder")

    def test_is_case_insensitive_and_needs_all_terms(self):
        self.assertTrue(matches_text(
            universe()["acme"].models["acme-coder"], "ACME  CODER"
        ))
        self.assertFalse(matches_text(
            universe()["acme"].models["acme-coder"], "acme vision"
        ))

    def test_search_also_finds_models_without_any_metadata(self):
        found, total = run(Filters(text="unknown"))
        self.assertEqual(total, 1)


class TestFilters(unittest.TestCase):
    def test_flags_are_combinable(self):
        reasoning, _ = run(Filters(reasoning=True))
        self.assertEqual({m.id for m in reasoning}, {"acme-coder", "opus"})

        both, total = run(Filters(reasoning=True, tools=True, paid=True))
        self.assertEqual(total, 2)

        reasoning_and_local, total = run(Filters(reasoning=True, local_only=True))
        self.assertEqual(total, 0)

    def test_free_and_paid_are_mutually_exclusive_in_practice(self):
        free = {m.id for m, _ in [(m, None) for m in run(Filters(free=True))[0]]}
        self.assertEqual(free, {"acme-vision", "llama-local"})
        paid = {m.id for m in run(Filters(paid=True))[0]}
        self.assertEqual(paid, {"acme-coder", "opus"})

    def test_vision_tools_multimodal_and_large_context(self):
        self.assertEqual(
            {m.id for m in run(Filters(vision=True))[0]},
            {"acme-vision", "opus"},
        )
        self.assertEqual(
            {m.id for m in run(Filters(tools=True))[0]}, {"acme-coder", "opus"}
        )
        self.assertEqual(
            {m.id for m in run(Filters(multimodal=True))[0]},
            {"acme-vision"},  # "opus" tiene attachment pero no modalidades declaradas
        )
        self.assertEqual(
            {m.id for m in run(Filters(large_context=True))[0]},
            {"acme-coder", "opus"},
        )

    def test_coding_heuristic_matches_programming_models(self):
        self.assertIn("acme-coder", {m.id for m in run(Filters(coding=True))[0]})

    def test_protocol_and_local_filters(self):
        anthropic = {m.id for m in run(Filters(protocol="anthropic"))[0]}
        self.assertEqual(anthropic, {"opus"})
        local = {m.id for m in run(Filters(local_only=True))[0]}
        self.assertEqual(local, {"llama-local"})

    def test_scope_uses_the_configured_ids_set(self):
        configured = frozenset({"acme/acme-coder"})
        only_registered = run(Filters(scope=SCOPE_CONFIGURED), configured=configured)
        self.assertEqual([m.full_id for m in only_registered[0]], ["acme/acme-coder"])

        unregistered = run(Filters(scope=SCOPE_UNCONFIGURED), configured=configured)
        self.assertNotIn("acme/acme-coder", {m.full_id for m in unregistered[0]})
        self.assertEqual(unregistered[1], 4)

    def test_scope_all_is_the_default_and_is_not_active(self):
        self.assertFalse(Filters().is_active())
        self.assertTrue(Filters(protocol="anthropic").is_active())
        self.assertEqual(Filters().protocol, PROTOCOL_ANY)
        self.assertEqual(Filters().scope, SCOPE_ALL)

    def test_summary_describes_active_filters_in_spanish(self):
        summary = Filters(free=True, reasoning=True, scope=SCOPE_CONFIGURED).summary()
        self.assertIn("gratis", summary)
        self.assertIn("razonamiento", summary)
        self.assertIn("registrados en OpenCode", summary)


class TestSorting(unittest.TestCase):
    def test_alphabetic_ascending_and_descending(self):
        asc, _ = run(Filters(text="acme"))
        self.assertEqual([m.name for m in asc], sorted(m.name for m in asc))
        desc, _ = run(Filters(text="acme", descending=True))
        self.assertEqual([m.name for m in desc], sorted((m.name for m in desc), reverse=True))

    def test_context_sort_defaults_to_largest_and_unknowns_last(self):
        found, _ = run(Filters(sort=SORT_CONTEXT))
        self.assertEqual(found[0].id, "acme-coder")
        self.assertEqual(found[-1].id, "acme-unknown")

    def test_context_sort_descending_keeps_unknowns_last(self):
        found, _ = run(Filters(sort=SORT_CONTEXT, descending=True))
        self.assertEqual(found[0].id, "acme-vision")
        self.assertEqual(found[1].id, "llama-local")
        self.assertEqual(found[-1].id, "acme-unknown")

    def test_price_sort_keeps_models_without_price_at_the_end(self):
        found, _ = run(Filters(sort=SORT_PRICE))
        self.assertEqual(found[0].id, "acme-vision")  # 0 + 0
        self.assertEqual(found[-1].id, "acme-unknown")

    def test_provider_sort_groups_by_provider_name(self):
        found, _ = run(Filters(sort=SORT_PROVIDER))
        self.assertEqual(found[0].provider_name, "Acme AI")
        self.assertEqual(found[-1].provider_name, "Local AI")

    def test_default_sort_is_name(self):
        self.assertEqual(Filters().sort, SORT_NAME)


class TestResultCap(unittest.TestCase):
    def test_cap_limits_the_view_not_the_count(self):
        found, total = run(Filters(max_results=2))
        self.assertEqual(total, 5)
        self.assertEqual(len(found), 2)

    def test_hard_cap_default_is_generous(self):
        self.assertGreaterEqual(Filters().max_results, 1000)


class TestProtocolGroups(unittest.TestCase):
    """«Otros» debe cubrir los protocolos no listados, no solo "other"."""

    PAYLOAD = {
        "bedrock-co": {
            "id": "bedrock-co", "name": "Bedrock Co",
            "npm": "@aws-sdk/client-bedrock-runtime",
            "api": "https://bedrock.test",
            "models": {"titan": {"id": "titan", "name": "Titan"}},
        },
        "azure-co": {
            "id": "azure-co", "name": "Azure Co",
            "npm": "@ai-sdk/azure", "api": "https://azure.test",
            "models": {"jj": {"id": "jj", "name": "JJ"}},
        },
        "plain-co": {
            "id": "plain-co", "name": "Plain Co",
            "npm": "@ai-sdk/someother", "api": "https://plain.test",
            "models": {"plain-model": {"id": "plain-model", "name": "Plain"}},
        },
        "gpt-co": {
            "id": "gpt-co", "name": "GPT Co", "npm": "@ai-sdk/openai",
            "api": "https://gpt.test",
            "models": {"gpt-x": {"id": "gpt-x", "name": "GPT X"}},
        },
    }

    def ids(self, protocol: str) -> set[str]:
        found, _total = search(catalog_pairs(parse_models_dev(self.PAYLOAD)),
                               Filters(protocol=protocol))
        return {m.id for m in found}

    def test_named_protocol_matches_only_itself(self):
        self.assertEqual(self.ids("openai"), {"gpt-x"})

    def test_other_covers_every_unlisted_protocol(self):
        self.assertEqual(self.ids(PROTOCOL_OTHER), {"titan", "jj", "plain-model"})

    def test_any_protocol_returns_everything(self):
        self.assertEqual(
            self.ids(PROTOCOL_ANY), {"titan", "jj", "plain-model", "gpt-x"}
        )

    def test_other_is_named_in_the_status_summary(self):
        self.assertEqual(
            Filters(protocol=PROTOCOL_OTHER).summary(), "otros protocolos"
        )


if __name__ == "__main__":
    unittest.main()
