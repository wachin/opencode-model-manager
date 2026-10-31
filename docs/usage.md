# Usage

[Back to the README](../README.md)

This page covers the interface, the catalog, search and filters, the model
card, the custom-provider dialog, the connection test and the keyboard
shortcuts. UI labels appear in Spanish, as the app shows them, usually
with an English gloss.

---

## Interface

Three zones, with a `QSplitter` between the workspace and the tree:

```
┌──────────────────────────────────────────────────────────────────┐
│ Header: title · file · search · Filters · actions                │
├───────────────────────────────────────┬──────────────────────────┤
│ Workspace (3 pages)                   │ Tree (right)             │
│  · Configuration overview             │  ● Acme AI  (3)          │
│  · Search/filter results              │    ✓ Acme Coder          │
│  · Selected model card                │    ✓ Acme Legacy         │
│                                       │      Acme Lite           │
│                                       │  Zeta Labs  (1)          │
└───────────────────────────────────────┴──────────────────────────┘
```

- **Header**: app name, path of the active `opencode.json`, search with a
  160 ms debounce, **Filtros** (“Filters”) button (collapsible), sort
  order, match counter and the action buttons (Open, Reload, Refresh
  catalog, +Provider, +Model, Preview, Theme, Copy file, Save).
- **Provider tree** (right column, draggable between 210 and 560 px):
  alphabetical order, **always collapsed on startup and when rebuilt
  after saving**; children are created only on expand, so thousands of
  models cost nothing. `●` and bold = provider registered in
  `opencode.json`; green `✓` = model already registered; no mark =
  catalog only. The number in parentheses is the model count.
- **Model card**: a click on a result or on the tree fills it; if there
  are no matches, the list shows the notice «Sin coincidencias con esta
  búsqueda y filtros.» (“No matches for this search and filters.”) instead
  of staying empty. The view is capped (up to 300 rows) but the counter
  always reports the real total.

---

## Model catalog

| Aspect | Detail |
|---|---|
| Remote source | `https://models.dev/api.json` (**MIT** license, sst/models.dev) |
| Local seed | B.AI, Ollama, LM Studio, llama-server and OpenRouter |
| On-disk cache | `$XDG_CACHE_HOME/opencode-model-manager/models_dev.json` + `models_dev.meta.json` (with `fetched_at`, `source` and `license`) |
| Startup | A thread loads the cache and publishes the catalog by signal; with no network you keep browsing offline |
| Update | **Refrescar catálogo** (“Refresh catalog”) button or `Ctrl+Shift+R` (downloads and rewrites the cache) |
| Provenance | Every provider/model reports `seed`, `models.dev`, `config` or `cache`; Models.dev wins over the seed |

Rules the code follows and the tests enforce:

- To **show** the catalog, no npm packages or provider code are
  downloaded or executed: only JSON is read.
- The request is an anonymous `urllib` call with
  `Accept-Encoding: gzip`: **no credentials**, no keys in headers or
  arguments.
- No entry is written to `opencode.json` just because it appears in the
  results: it has to be registered.
- From a catalog model, only reliable fields are copied into the
  configuration (`name`, `modelID`, `limit`, `cost`, `modalities` and the
  declared capabilities); if the source JSON contains anything resembling
  a key, it never reaches the file.

---

## Search and filters

Search covers: model and provider name, model ID, `modelID`, provider ID,
endpoint/`baseURL`, description, family, type and modalities.

| Group | Options |
|---|---|
| Scope | All · Registered in OpenCode · Not registered |
| Protocol | Any protocol · OpenAI-compatible · OpenAI · Anthropic · Google · Other |
| Location | **Locales** (“Local”) checkbox (Ollama, LM Studio, llama.cpp…) |
| Model (chips) | Free · Paid · Free tier · Code · Reasoning · Vision · Tool calling · Multimodal · Context ≥ 200k |
| Order | A → Z · Provider · Context · Price, with an ↑↓ button to reverse |

- **Every control applies instantly**: each combo, each checkbox and each
  chip triggers the search on its own; nothing else needs to be pressed.
- **“Other”** includes unlisted protocols (Bedrock, Azure or other SDKs),
  not only those literally named `other`.
- **Context** sorts from largest to smallest by default; models with an
  unknown context always end up last. **Price** sorts by the combined
  input/output cost, with `Gratis` (“Free”) as 0 and unpriced models last.
- A model is **not** marked as multimodal or vision-capable if the
  catalog does not declare its modalities: we prefer `Desconocido`
  (“Unknown”) to guessing.

---

## Model card: zero invented data

| Field | No data |
|---|---|
| Context window / Maximum output | `Desconocido` (“Unknown”) |
| Tool calling · Reasoning · Vision · Streaming · Modalities | `Desconocido` (“Unknown”) |
| Price | `Sin datos de precio` (“No price data”) (or `Gratis` if 0/0) |
| Status in OpenCode | `Registrado` (“Registered”) or `Solo en catálogo (no registrado)` (“Catalog only (not registered)”) |

The **API / Base URL** row uses the `baseURL` from your configuration when
it exists; only if the provider is not registered does it show the
catalog endpoint.

**Quitar de OpenCode** (“Remove from OpenCode”) deletes the entry from
`opencode.json` (with confirmation) but leaves the catalog entry intact,
so you can register it again whenever you want.

---

## Registering a custom provider

**+ Proveedor** button: a dialog with two tabs.

1. **Formulario** (“Form”) — provider ID (it must match the one you used
   in `/connect`), visible name, Base URL, protocol, AI SDK `npm`,
   authentication environment variable, custom headers (`Key: value` per
   line) and the initial model(s).
2. **Importar JSON** (“Import JSON”) — paste the `opencode.json` block,
   the bare provider object (with `"id"`) or a list, press **Validar**
   (“Validate”) and, if it is correct, **Aplicar al formulario** (“Apply
   to form”).

Validation rejects a missing ID, a Base URL that is not a valid
`http(s)` URL, an empty name, malformed headers, unknown keys and models
without an ID, and shows the exact reason in red before letting you
accept. Authentication is always left to `/connect` or the indicated
environment variable: **the form has no API key field**.

When registering a catalog model, whatever you had already written by hand
is preserved (`modelID`, `options`, `variants`, custom limits) and only
the new data is added.

---

## Testing a provider's connection

**Probar conexión** (“Test connection”, on the card, or `Ctrl+T`) checks
that the `baseURL` really responds. It is a **read** of the model list:
`GET /models`, or `/v1/models` when the `baseURL` does not already end in
that suffix — the case of a local server, for which the test does not
invent an extra `/v1`. It spends no tokens, writes nothing to
`opencode.json` or the cache, and sends no credentials unless you
explicitly ask it to.

The path is decided by the protocol: `/v1/models` for OpenAI and
OpenAI-compatible, and the same endpoint with `x-api-key` and
`anthropic-version` for Anthropic. For Bedrock, Azure or others the
button stays disabled and says so: their SDK defines the format, and a
404 there would mean nothing.

| Response | What the card reports |
|---|---|
| 200 with the list | `Endpoint operativo` (“Endpoint healthy”) · latency · how many models it announces and **which of yours appear** |
| 401 / 403 without a key | `Endpoint vivo: pide credenciales` (“Endpoint alive: asks for credentials”) — the route exists; the key is set with `/connect` |
| 401 / 403 with a key | `El endpoint existe, pero rechaza tu clave` (“The endpoint exists, but rejects your key”) |
| 404 / 405 | `No expone /v1/models` (“Does not expose /v1/models”) — the host responds; usually `/v1` is missing (or extra) |
| 429 | alive, but saturated |
| 5xx | the endpoint exists and fails on its side |
| DNS / closed port / timeout / TLS | the exact reason, no guessing |
| 3xx | `Redirige fuera de tu baseURL` (“Redirects outside your baseURL”) — the redirect is **not** followed |

**Probar con mi clave** (“Test with my key”) is a separate button and only
appears if the provider declares an environment variable and that
variable is defined in the process that launched the window (if you
export it in `.bashrc`, open the app from that terminal; otherwise the
notice explains it). The key is read from the environment **inside the
thread**, travels only over HTTPS or to loopback — never in cleartext to a
remote host — and is never shown, stored or written: the card only says
whether it authorizes you. The *Variables de entorno* (“Environment
variables”) row names each variable as `presente` (“present”) or
`ausente` (“absent”), never its value.

Rules the test applies even if the endpoint does not cooperate:

- **Follows no redirects**: a `Location` to another domain would turn an
  apparent 200 into a leak of the authentication header.
- **Rejects cloud metadata addresses** (`169.254.169.254`,
  `metadata.google.internal`…) before opening the socket.
- **Redacts the key** in any message it generates, even if the server
  echoes it back in an error.
- Does not read `auth.json` and writes nothing to disk.

---

## Keyboard shortcuts

| Key | Action |
|---|---|
| `Ctrl+F` | Focus the search box |
| `Ctrl+R` | Reload the current `opencode.json` |
| `Ctrl+Shift+R` | Refresh the catalog from Models.dev |
| `Ctrl+S` | Save (validates, backs up and writes atomically) |
| `Ctrl+O` | Open a specific `opencode.json` |
| `Ctrl+T` | Test the connection of the open card |
| `Esc` | 1st clears search **and filters** · 2nd collapses the filter panel |
| `Enter` (in results) | Open the card of the highlighted model |
| `Supr` (Delete) | Remove from OpenCode, with confirmation |
