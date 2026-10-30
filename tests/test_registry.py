"""Pruebas de la capa catálogo ↔ opencode.json (omm.registry).

Aquí vive lo delicado: lo que estas funciones escriben es la configuración
real del usuario. Se comprueba que solo escriben datos fiables, que
preservan lo desconocido y que nunca escriben secretos.
"""

from __future__ import annotations

import json
import unittest

from support import catalog as _catalog  # noqa: F401  (arranque headless)

from omm.catalog import ModelEntry, Pricing, ProviderEntry
from omm.registry import (
    add_catalog_model_to_config, add_provider_to_config, config_providers,
    configured_full_ids, model_detail_rows, provider_from_config,
    provider_union, remove_model_from_config, remove_provider_from_config,
    set_default_model, tree_data, validate_config, validate_provider_spec,
)


def provider(pid="acme", name="Acme AI", npm="@ai-sdk/openai-compatible",
             api="https://api.acme.test/v1", env=(), **kw):
    return ProviderEntry(
        id=pid, name=name, npm=npm, api=api, env=list(env),
        source="models.dev", **kw
    )


def model(pid="acme", mid="acme-coder", pname="Acme AI", **kw):
    kw.setdefault("npm", "@ai-sdk/openai-compatible")
    kw.setdefault("base_url", "https://api.acme.test/v1")
    kw.setdefault("protocol", "openai-compatible")
    return ModelEntry(id=mid, name=kw.pop("name", mid), provider_id=pid,
                      provider_name=pname, **kw)


def sample_config():
    return {
        "$schema": "https://opencode.ai/config.json",
        "provider": {
            "acme": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Acme AI",
                "env": ["ACME_API_KEY"],
                "options": {"baseURL": "https://api.acme.test/v1"},
                "models": {
                    "acme-coder": {
                        "name": "Acme Coder",
                        "modelID": "acme-coder-v1",
                        "limit": {"context": 400_000, "output": 64_000},
                        "variants": {"fast": {"temperature": 0.2}},
                    },
                },
            },
            "mystery": {
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": "https://mystery.test/v1"},
                "models": {"solo-config": {"name": "Solo Config"}},
            },
        },
        "model": "acme/acme-coder",
    }


class TestConfigViews(unittest.TestCase):
    def test_configured_full_ids_lists_only_registered_models(self):
        self.assertEqual(
            configured_full_ids(sample_config()),
            frozenset({"acme/acme-coder", "mystery/solo-config"}),
        )

    def test_config_providers_tolerates_garbage(self):
        self.assertEqual(config_providers({}), {})
        self.assertEqual(config_providers({"provider": []}), {})

    def test_provider_from_config_reads_base_url_env_and_models(self):
        entry = provider_from_config("acme", sample_config()["provider"]["acme"])
        self.assertEqual(entry.name, "Acme AI")
        self.assertEqual(entry.api, "https://api.acme.test/v1")
        self.assertEqual(entry.env, ["ACME_API_KEY"])
        self.assertEqual(entry.protocol, "openai-compatible")
        coder = entry.models["acme-coder"]
        self.assertEqual(coder.context, 400_000)
        self.assertEqual(coder.output_limit, 64_000)
        self.assertEqual(coder.source, "config")

    def test_provider_from_config_keeps_raw_for_unknown_properties(self):
        entry = provider_from_config("acme", sample_config()["provider"]["acme"])
        variants = entry.models["acme-coder"].raw["variants"]
        self.assertEqual(variants["fast"]["temperature"], 0.2)

    def test_provider_from_config_survives_non_dict_entries(self):
        self.assertEqual(provider_from_config("x", None).models, {})
        self.assertEqual(provider_from_config("x", {"models": ["roto"]}).models, {})


class TestTree(unittest.TestCase):
    def test_providers_are_alphabetical_by_visible_name(self):
        providers = {
            "zebra": provider(pid="zebra", name="Zebra Labs"),
            "acme": provider(),
        }
        names = [r["name"] for r in tree_data(providers, sample_config())]
        self.assertEqual(names, sorted(names, key=str.lower))

    def test_models_inside_a_provider_are_alphabetical(self):
        providers = {"acme": provider(models={
            "z": model(mid="z", name="Zeta"),
            "a": model(mid="a", name="Alpha"),
        })}
        rows = {r["id"]: r for r in tree_data(providers, {})}
        self.assertEqual([m["name"] for m in rows["acme"]["models"]],
                         ["Alpha", "Zeta"])

    def test_union_includes_config_only_providers_and_marks_them(self):
        providers = {"acme": provider()}
        rows = {r["id"]: r for r in tree_data(providers, sample_config())}
        self.assertIn("mystery", rows, "Un proveedor registrado a mano debe aparecer")
        self.assertTrue(rows["acme"]["configured"])
        self.assertTrue(rows["mystery"]["configured"])

    def test_model_rows_distinguish_registered_from_catalog_only(self):
        providers = {
            "acme": provider(models={
                "acme-coder": model(mid="acme-coder", name="Acme Coder"),
                "acme-new": model(mid="acme-new", name="Acme New"),
            })
        }
        rows = {r["id"]: r for r in tree_data(providers, sample_config())}
        flags = {m["id"]: m["configured"] for m in rows["acme"]["models"]}
        self.assertEqual(flags, {"acme-coder": True, "acme-new": False})
        self.assertEqual(rows["acme"]["count"], 2)

    def test_catalog_provider_without_config_is_not_configured(self):
        providers = {"novo": provider(pid="novo", name="Novo AI")}
        rows = {r["id"]: r for r in tree_data(providers, sample_config())}
        self.assertFalse(rows["novo"]["configured"])
        self.assertEqual(rows["novo"]["count"], 0)

    def test_tree_falls_back_to_catalog_protocol_and_endpoint(self):
        rows = {r["id"]: r for r in tree_data({"acme": provider()}, {})}
        self.assertEqual(rows["acme"]["protocol"], "openai-compatible")
        self.assertEqual(rows["acme"]["base_url"], "https://api.acme.test/v1")

    def test_provider_union_prefers_config_name(self):
        providers = {"acme": provider(name="Acme AI")}
        rows = provider_union(providers, sample_config())
        names = {pid: name for pid, name, _c, _p, _cfg in rows}
        self.assertEqual(names["acme"], "Acme AI")


class TestDetailRows(unittest.TestCase):
    def rows(self, **kw):
        entry = model(**kw)
        return dict(model_detail_rows(entry, provider(), None, None))

    def test_missing_data_is_not_invented(self):
        rows = self.rows()
        self.assertEqual(rows["Ventana de contexto"], "Desconocido")
        self.assertEqual(rows["Salida máxima (tokens)"], "Desconocido")
        self.assertEqual(rows["Tool calling"], "Desconocido")
        self.assertEqual(rows["Razonamiento"], "Desconocido")
        self.assertEqual(rows["Modalidades de entrada"], "Desconocido")
        self.assertEqual(rows["Precio"], "Sin datos de precio")
        self.assertEqual(rows["Streaming"], "Desconocido")
        self.assertEqual(rows["Configuración en OpenCode"],
                         "Solo en catálogo (no registrado)")

    def test_known_data_is_rendered(self):
        rows = self.rows(
            context=1_048_576, output_limit=65_536,
            input_modalities=["text", "image"], output_modalities=["text"],
            tool_call=True, reasoning=False, status="active",
            pricing=Pricing(input=2.5, output=10.0),
        )
        self.assertEqual(rows["Ventana de contexto"], "1.05 M")
        self.assertEqual(rows["Salida máxima (tokens)"], "66k")
        self.assertEqual(rows["Modalidades de entrada"], "text, image")
        self.assertEqual(rows["Tool calling"], "Sí")
        self.assertEqual(rows["Razonamiento"], "No")
        self.assertEqual(rows["Visión"], "Sí")
        self.assertEqual(rows["Precio"],
                         "Entrada $2.50 / salida $10.00 (USD/M tokens)")
        self.assertEqual(rows["Estado"], "active")

    def test_free_pricing_is_labelled_as_free(self):
        rows = self.rows(pricing=Pricing(input=0, output=0))
        self.assertEqual(rows["Precio"], "Gratis")

    def test_endpoint_prefers_configured_base_url(self):
        entry = model()
        rows = dict(model_detail_rows(
            entry, provider(api="https://catalog.test/v1"), {},
            {"options": {"baseURL": "https://registrado.test/v1"}},
        ))
        self.assertEqual(rows["API / Base URL"], "https://registrado.test/v1")

    def test_unregistered_marker_disappears_when_registered(self):
        rows = dict(model_detail_rows(
            model(), provider(), {"name": "x"}, {"name": "Acme AI"}
        ))
        self.assertEqual(rows["Configuración en OpenCode"], "Registrado")

    def test_config_only_model_still_produces_rows(self):
        cfg = sample_config()["provider"]["acme"]["models"]["acme-coder"]
        rows = dict(model_detail_rows(None, None, cfg, {"id": "acme", "name": "Acme AI"}))
        self.assertEqual(rows["ID del modelo"], "")
        self.assertEqual(rows["Ventana de contexto"], "400k")
        self.assertEqual(rows["Configuración en OpenCode"], "Registrado")

    def test_provider_and_model_ids_are_always_shown(self):
        rows = dict(model_detail_rows(model(), provider(), None, None))
        self.assertEqual(rows["ID del proveedor"], "acme")
        self.assertEqual(rows["ID del modelo"], "acme-coder")
        self.assertEqual(rows["Protocolo API"],
                         "openai-compatible · @ai-sdk/openai-compatible")

    def test_the_provider_id_survives_an_unknown_model(self):
        """Modelo ausente del catálogo y de opencode.json: la ficha todavía
        tiene que decir en qué proveedor está mirando."""
        rows = dict(model_detail_rows(None, provider(), None, None))
        self.assertEqual(rows["ID del proveedor"], "acme")
        self.assertEqual(rows["Proveedor"], "Acme AI")


class TestAddCatalogModel(unittest.TestCase):
    def test_writes_provider_block_from_catalog_data(self):
        data = {}
        ref = add_catalog_model_to_config(
            data, model(), provider(env=["ACME_API_KEY"])
        )
        self.assertEqual(ref, "acme/acme-coder")
        pdata = data["provider"]["acme"]
        self.assertEqual(pdata["npm"], "@ai-sdk/openai-compatible")
        self.assertEqual(pdata["name"], "Acme AI")
        self.assertEqual(pdata["options"]["baseURL"], "https://api.acme.test/v1")
        self.assertEqual(pdata["env"], ["ACME_API_KEY"])
        self.assertIn("acme-coder", pdata["models"])

    def test_never_writes_credentials(self):
        entry = model(raw={"api_key": "sk-supersecreto", "options": {"apiKey": "x"}})
        data = {}
        add_catalog_model_to_config(data, entry, provider())
        blob = json.dumps(data)
        for marker in ("sk-supersecreto", "api_key", "apiKey", "API_KEY"):
            self.assertNotIn(marker, blob)

    def test_writes_only_reliable_fields(self):
        data = {}
        add_catalog_model_to_config(data, model(), provider())
        entry = data["provider"]["acme"]["models"]["acme-coder"]
        self.assertEqual(set(entry), {"name"})

    def test_writes_known_capabilities_only(self):
        entry = model(context=200_000, tool_call=True, reasoning=None,
                      input_modalities=["text"], pricing=Pricing(input=1.0))
        data = {}
        add_catalog_model_to_config(data, entry, provider())
        written = data["provider"]["acme"]["models"]["acme-coder"]
        self.assertEqual(written["limit"], {"context": 200_000})
        self.assertEqual(written["tool_call"], True)
        self.assertNotIn("reasoning", written)
        self.assertEqual(written["cost"], {"input": 1.0})
        self.assertEqual(written["modalities"], {"input": ["text"]})

    def test_preserves_existing_model_properties(self):
        data = sample_config()
        add_catalog_model_to_config(
            data, model(name="Acme Coder 2", context=128_000), provider()
        )
        written = data["provider"]["acme"]["models"]["acme-coder"]
        self.assertEqual(written["modelID"], "acme-coder-v1")
        self.assertEqual(written["variants"]["fast"]["temperature"], 0.2)
        self.assertEqual(written["limit"], {"context": 128_000, "output": 64_000})
        self.assertEqual(written["name"], "Acme Coder 2")

    def test_is_idempotent(self):
        first, second = {}, {}
        entry = model(context=200_000)
        add_catalog_model_to_config(first, entry, provider())
        add_catalog_model_to_config(second, entry, provider())
        add_catalog_model_to_config(second, entry, provider())
        self.assertEqual(first, second)

    def test_does_not_register_other_catalog_models(self):
        data = {}
        add_catalog_model_to_config(
            data, model(), provider(models={"otro": model(mid="otro")})
        )
        self.assertEqual(list(data["provider"]["acme"]["models"]), ["acme-coder"])

    def test_keeps_existing_provider_edits_untouched(self):
        data = sample_config()
        add_catalog_model_to_config(data, model(mid="nuevo"), provider())
        self.assertEqual(
            data["provider"]["acme"]["options"],
            {"baseURL": "https://api.acme.test/v1"},
        )
        self.assertEqual(data["model"], "acme/acme-coder")

    def test_replaces_a_provider_block_that_is_not_a_dict(self):
        data = {"provider": {"acme": "basura"}}
        add_catalog_model_to_config(data, model(), provider())
        self.assertIsInstance(data["provider"]["acme"], dict)
        self.assertIn("acme-coder", data["provider"]["acme"]["models"])


class TestAddProvider(unittest.TestCase):
    def spec(self, **kw):
        base = {
            "id": "nuevo", "name": "Nuevo AI",
            "npm": "@ai-sdk/openai-compatible",
            "baseURL": "https://nuevo.test/v1", "env": ["NUEVO_KEY"],
            "headers": {"X-Tenant": "acme"},
        }
        base.update(kw)
        return base

    def test_creates_the_expected_block(self):
        data = {}
        self.assertEqual(add_provider_to_config(data, self.spec()), "nuevo")
        pdata = data["provider"]["nuevo"]
        self.assertEqual(pdata["name"], "Nuevo AI")
        self.assertEqual(pdata["options"]["baseURL"], "https://nuevo.test/v1")
        self.assertEqual(pdata["options"]["headers"], {"X-Tenant": "acme"})
        self.assertEqual(pdata["env"], ["NUEVO_KEY"])

    def test_preserves_unknown_properties_of_an_existing_provider(self):
        data = {"provider": {"nuevo": {"name": "Viejo", "disabled": True,
                                        "options": {"timeout": 30}}}}
        add_provider_to_config(data, self.spec(name="Nuevo AI"))
        pdata = data["provider"]["nuevo"]
        self.assertTrue(pdata["disabled"])
        self.assertEqual(pdata["options"]["timeout"], 30)
        self.assertEqual(pdata["name"], "Nuevo AI")

    def test_keeps_existing_model_customizations(self):
        data = {"provider": {"nuevo": {"models": {
            "m1": {"name": "Mi nombre", "modelID": "m1-priv"}
        }}}}
        spec = self.spec(models={"m1": {"name": "Catálogo"}, "m2": {}})
        add_provider_to_config(data, spec)
        models = data["provider"]["nuevo"]["models"]
        self.assertEqual(models["m1"]["modelID"], "m1-priv")
        self.assertEqual(models["m1"]["name"], "Mi nombre")
        self.assertIn("m2", models)

    def test_ignores_private_keys_from_the_import_dialog(self):
        data = {}
        add_provider_to_config(data, self.spec(_raw_json="{...}", version=2))
        pdata = data["provider"]["nuevo"]
        self.assertNotIn("_raw_json", pdata)
        self.assertEqual(pdata["version"], 2)

    def test_new_models_get_their_metadata_written(self):
        data = {}
        spec = self.spec(models={"m1": {
            "name": "M1", "modelID": "m1-x",
            "limit": {"context": 1000}, "cost": {"input": 1},
            "modalities": {"input": ["text"]},
        }})
        add_provider_to_config(data, spec)
        m1 = data["provider"]["nuevo"]["models"]["m1"]
        self.assertEqual(m1["modelID"], "m1-x")
        self.assertEqual(m1["limit"], {"context": 1000})
        self.assertEqual(m1["cost"], {"input": 1})


class TestRemovals(unittest.TestCase):
    def test_remove_model_clears_default_references(self):
        data = sample_config()
        data["small_model"] = "acme/acme-coder"
        self.assertTrue(remove_model_from_config(data, "acme", "acme-coder"))
        self.assertNotIn("acme-coder", data["provider"]["acme"]["models"])
        self.assertNotIn("model", data)
        self.assertNotIn("small_model", data)

    def test_remove_model_keeps_other_defaults(self):
        data = sample_config()
        data["model"] = "mystery/solo-config"
        self.assertTrue(remove_model_from_config(data, "acme", "acme-coder"))
        self.assertEqual(data["model"], "mystery/solo-config")

    def test_remove_model_reports_unknown_targets(self):
        data = sample_config()
        self.assertFalse(remove_model_from_config(data, "acme", "no-existe"))
        self.assertFalse(remove_model_from_config(data, "no-existe", "x"))
        self.assertIn("acme-coder", data["provider"]["acme"]["models"])

    def test_remove_provider_drops_its_models_and_defaults(self):
        data = sample_config()
        data["small_model"] = "acme/acme-coder"
        self.assertTrue(remove_provider_from_config(data, "acme"))
        self.assertNotIn("acme", data["provider"])
        self.assertNotIn("model", data)
        self.assertNotIn("small_model", data)
        self.assertIn("mystery", data["provider"])

    def test_remove_provider_reports_unknown_target(self):
        data = sample_config()
        self.assertFalse(remove_provider_from_config(data, "fantasma"))
        self.assertEqual(set(data["provider"]), {"acme", "mystery"})

    def test_set_default_model_sets_and_clears(self):
        data = {}
        set_default_model(data, "acme/acme-coder")
        set_default_model(data, "acme/acme-coder", small=True)
        self.assertEqual(data, {"model": "acme/acme-coder",
                                "small_model": "acme/acme-coder"})
        set_default_model(data, None)
        self.assertEqual(data, {"small_model": "acme/acme-coder"})


class TestValidation(unittest.TestCase):
    def test_valid_spec_has_no_errors(self):
        self.assertEqual(validate_provider_spec({
            "id": "nuevo", "name": "Nuevo", "npm": "@ai-sdk/openai-compatible",
            "baseURL": "https://nuevo.test/v1", "env": ["NUEVO_KEY"],
            "headers": {"a": "b"}, "models": {"m": {"name": "M"}},
        }), [])

    def test_spec_rejects_missing_or_structured_ids(self):
        self.assertTrue(any("id" in e for e in validate_provider_spec({"name": "x"})))
        self.assertTrue(any("id" in e.lower() for e in validate_provider_spec({"id": "con espacio"})))
        self.assertTrue(validate_provider_spec({"id": "a/b"}))

    def test_spec_rejects_non_http_base_url(self):
        for bad in ("ftp://nuevo.test", "nuevo.test/v1", "javascript:alert(1)"):
            with self.subTest(baseURL=bad):
                self.assertTrue(validate_provider_spec(
                    {"id": "n", "baseURL": bad}
                ), f"Debe rechazar {bad!r}")

    def test_spec_accepts_missing_base_url_for_local_providers(self):
        self.assertEqual(validate_provider_spec({"id": "n"}), [])

    def test_spec_rejects_bad_headers_env_and_models(self):
        self.assertTrue(validate_provider_spec({"id": "n", "headers": ["a"]}))
        self.assertTrue(validate_provider_spec({"id": "n", "headers": {"a": 1}}))
        self.assertTrue(validate_provider_spec({"id": "n", "env": "NUEVO_KEY"}))
        self.assertTrue(validate_provider_spec({"id": "n", "models": ["sin id"]}))
        self.assertTrue(validate_provider_spec({"id": "n", "models": 5}))
        self.assertFalse(validate_provider_spec(
            {"id": "n", "models": [{"id": "m"}]}
        ))

    def test_config_rejects_non_object_provider_section(self):
        self.assertIn('"provider" debe ser un objeto.',
                      validate_config({"provider": []}))

    def test_config_rejects_bad_limits_and_base_urls(self):
        errors = validate_config({"provider": {"a": {
            "options": {"baseURL": "ftp://a.test"},
            "models": {"m": {"limit": {"context": "mucho"}}},
        }}})
        self.assertTrue(any("baseURL" in e for e in errors))
        self.assertTrue(any("limit.context" in e for e in errors))

    def test_config_rejects_malformed_default_references(self):
        self.assertTrue(any("proveedor/modelo" in e
                            for e in validate_config({"model": "sin-barra"})))
        self.assertEqual(validate_config({"model": {"providerID": "a", "model": "b"}}), [])
        self.assertTrue(validate_config({"model": {"providerID": "a"}}))

    def test_config_accepts_the_written_shape(self):
        data = {}
        add_catalog_model_to_config(data, model(context=200_000), provider(env=["K"]))
        add_provider_to_config(data, {
            "id": "nuevo", "name": "Nuevo", "npm": "@ai-sdk/openai-compatible",
            "baseURL": "http://localhost:11434/v1", "models": {"l": {}},
        })
        set_default_model(data, "acme/acme-coder")
        self.assertEqual(validate_config(data), [])


class TestConfiguredIdsAfterRegister(unittest.TestCase):
    def test_registration_flips_the_configured_set(self):
        data = {}
        entry = model()
        self.assertNotIn(entry.full_id, configured_full_ids(data))
        add_catalog_model_to_config(data, entry, provider())
        self.assertIn(entry.full_id, configured_full_ids(data))
        remove_model_from_config(data, entry.provider_id, entry.id)
        self.assertNotIn(entry.full_id, configured_full_ids(data))


if __name__ == "__main__":
    unittest.main()
