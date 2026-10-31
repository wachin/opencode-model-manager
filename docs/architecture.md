# Architecture

[Back to the README](../README.md)

The package is imported from `opencode_model_manager.py`, which remains
the usual entry point and only boots the GUI.

| Module | Responsibility |
|---|---|
| `omm/catalog.py` | `ProviderEntry`/`ModelEntry` dataclasses, seed, Models.dev parser, cache with metadata, provenance, `adopt()` |
| `omm/search.py` | `Filters`, text matching, scope/protocol/chip filters and the four sort orders |
| `omm/registry.py` | Catalog ↔ configuration boundary: `add_catalog_model_to_config`, `add_provider_to_config`, removals, `tree_data`, `provider_union`, `model_detail_rows`, `action_note` (why a control does not act), validations |
| `omm/main_window.py` | Window, state (data, not widgets), signals between panels, save flow |
| `omm/ui/panels.py` | Header, lazy tree, results (with empty notice), filters, card, overview |
| `omm/ui/dialogs.py` | Provider dialog (form + import JSON), model dialog and preview |
| `omm/workers.py` | `CatalogLoadWorker` and `ProbeWorker` (`QThread`): they never mutate GUI state, they deliver it by signal |
| `omm/probe.py` | Connection test with stdlib only: URL per protocol, metadata and cleartext-key rejection, no redirects, DNS/TLS/timeout/HTTP classification, key redaction and an injectable `opener` for the tests |
| `omm/theme.py` | Light/dark palettes (with a `QPalette` role map) and QSS; no Qt dependencies |

Design rules the code keeps:

- Catalog data and `opencode.json` are different layers; the boundary is
  `omm/registry.py`.
- The GUI holds data, not widgets, as the source of truth.
- Network work runs in `QThread`; results travel in signals.
- The connection probe never mutates the window; it returns a result the
  window decides how to show.
