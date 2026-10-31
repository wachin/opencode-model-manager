# OpenCode API Manager

[Español](README.md) · **English**

> English translation of the Spanish README. If the two ever differ, the
> Spanish version prevails.

![](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEisuFUVre-MOxXm1lfvA_mEhp3GC8rcQ93U0N4E1erQ-1kmtIpbNgMbyebyA3SM38NTUuPfAOlmeXF9Fr5RNx2G4cHsWLrjC6wYngr27xBvPOKXzf8RTwnwXrUYT4v2nMLHhyphenhyphenMGBGXPCD-X3gA4QN-MxP8re58d9lEOZ5Srd-satUhSblTyae3uIWr1FlM/s1600-rw/Portada.jpg)

**Python / PyQt6** GUI to discover, compare and register
[OpenCode](https://opencode.ai/) models. It works on two separate layers:

1. **The catalog** — providers and models with their protocol, endpoint,
   context window, maximum output, modalities, capabilities and prices.
   It is fed by [Models.dev](https://models.dev) (MIT) plus a local seed
   and an on-disk cache, and it is **not part of your configuration**.
2. **`opencode.json`** — what OpenCode reads. Only what you register is
   written there: adding and removing models and providers, renaming
   them, changing the real ID (`modelID`), the limits (`limit`), the
   default model (`model`) and `small_model`, with an automatic backup
   before every save.

**This program does not ask for or store API keys.** OpenCode keeps
`/connect` credentials separately (in `auth.json`), and this tool never
reads, shows or modifies them: you can change models without entering the
key again. Searching the catalog **does not** write anything either: a
model reaches `opencode.json` only when you press **Agregar a OpenCode**
(“Add to OpenCode”). The connection test does not ask for a key either:
if you choose **Probar con mi clave** (“Test with my key”), it uses the
environment variable declared by the provider, without showing or storing
it.

> The interface itself is in Spanish. Button and label names appear below
> as the app shows them, usually with an English gloss in quotes.

---

## Features

- **Catalog separate from configuration**: model data without touching
  your `opencode.json` and without installing anything.
- **Visible sources and provenance**: local seed + Models.dev (MIT), with
  the last-updated date; with no network you keep browsing from the
  cache.
- **Instant search** over names, IDs, `modelID`, endpoint, description and
  tags — it works **whether the tree is collapsed or expanded**, because
  it filters data, not widgets.
- **Combinable filters** (scope, protocol, local providers and nine chips)
  with a match counter, clear button, sort orders and a collapsible panel.
- **Provider → model tree on the right**: narrow, alphabetical,
  **fully collapsed by default**, children loaded on expand, a count of
  how many models there are, and a clear difference between registered
  (`●`/`✓`) and catalog-only.
- **Model card with no invented data**: anything unknown is labelled
  `Desconocido` (“Unknown”), `Sin datos de precio` (“No price data”) or
  `Solo en catálogo (no registrado)` (“Catalog only (not registered)”).
- **Seven real actions** on the card: Add to OpenCode, Edit, Set as
  default (`model`), Set as small model (`small_model`), Copy ID, Copy
  endpoint and Remove from OpenCode.
- **Test the provider's connection** (`Ctrl+T`): a `GET` to its model
  list that spends no tokens and reports what really happens (200 with
  how many of your models exist, 401 “alive but asks for credentials”,
  404, DNS, TLS, timeout…). Anonymous by default; **Probar con mi clave**
  only appears if the declared environment variable exists, and the key
  is never shown or stored. It follows no redirects and never contacts
  cloud metadata addresses.
- **Guided custom-provider creation**, with an *Importar JSON* (“Import
  JSON”) tab that validates before accepting anything.
- Edits `opencode.json` without touching
  `~/.local/share/opencode/auth.json`.
- **Global mode by default**: works on
  `~/.config/opencode/opencode.json`; with the **Modo global** (“Global
  mode”) checkbox (persistent across sessions) you switch to the
  `opencode.json` of the current repository.
- Changes the ID and visible name of any model.
- Preserves extra properties of each model (`limit`, `options`,
  `variants`, etc.).
- Automatic backup (`.backup`) before saving, dated backups in
  `opencode-backups/` and a manual backup button.
- **Atomic save** (temporary file + `fsync` + `os.replace`), prior
  validation and **external-change detection**: if someone edited the
  file since your last load, it asks before overwriting.
- **LSP checkbox**: enables or disables OpenCode's LSP servers (the
  `"lsp"` key in `opencode.json`). Before enabling it, the app checks
  whether the language server is installed (for Python: **pyright**) and,
  if missing, warns with the install command: without it, OpenCode will
  keep showing *LSP* as disabled.
- **Auto → light → dark theme** (the **Tema** button in the header). Both
  layers are applied — the stylesheet and the application `QPalette` — so
  combo popups, dialogs, message boxes and disabled text follow the theme
  instead of the desktop theme. **Auto** mode detects whether your desktop
  is dark by reading the *style* palette (never its own, to avoid feeding
  back on itself). Contrasts are measured in the tests: text ≥ 7:1 and
  muted text ≥ 4.5:1 on every surface, in both themes.
- Remembers size, position, tree width and theme between sessions (the
  window is re-fitted to the monitor so it never ends up off-screen).
- Automatically normalizes the old `providers` key to `provider`
  (OpenCode's stable format) on load, with a dialog warning.
- Automatic local configuration detection:
  `OPENCODE_CONFIG` → `./opencode.json` → upward search in a git
  repository → `~/.config/opencode/opencode.json`.
- The network **never** blocks the interface: downloading and parsing the
  catalog and the connection test run in a `QThread`, and the result
  arrives complete via a signal.

---

## Requirements and installation

You need **Python 3** (3.10 or newer) and **PyQt6**:

```bash
pip install PyQt6
```

And to run it:

```bash
python3 opencode_model_manager.py
```

### LSP server for Python (recommended)

If you want OpenCode to have autocompletion, type analysis and diagnostics
for your Python files, install **pyright** as well:

```bash
npm install -g pyright
```

Check that it ended up in your `PATH`:

```bash
pyright --version
command -v pyright
```

> **Note:** if you installed global npm packages in your HOME (with
> `npm config set prefix ~/.local/npm`), the binary lands in
> `~/.local/npm/bin` — make sure that directory is in your `PATH`, just
> like for `opencode`.

---

## Run and test from the terminal (English · Português)

These self-contained guides repeat the same steps as **Requirements and
installation** and add a headless check. The app's interface stays in
Spanish: the instructions are translated, not the buttons. The Spanish
original is in [README.md](README.md).

### English — Run and test from the terminal

**Requirements:** Python 3.10+ and PyQt6 (the only dependency).

Install in a virtual environment:

```bash
git clone https://github.com/wachin/opencode-model-manager.git
cd opencode-model-manager
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 -m pip install PyQt6
```

Run it from the terminal:

```bash
python3 opencode_model_manager.py
```

If the configuration does not exist yet, the app asks before creating it.

Check that it starts without a display (SSH or CI). It uses a throwaway
`HOME`, so it never touches your real configuration, settings or backups:

```bash
tmp=$(mktemp -d)
mkdir -p "$tmp/.config/opencode"
printf '{"$schema": "https://opencode.ai/config.json", "provider": {}}' \
  > "$tmp/.config/opencode/opencode.json"
HOME="$tmp" QT_QPA_PLATFORM=offscreen python3 - <<'PY'
import sys
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from omm.main_window import OpenCodeModelManager

app = QApplication(sys.argv)
window = OpenCodeModelManager()
window.show()
QTimer.singleShot(1500, app.quit)
sys.exit(app.exec())
PY
```

No traceback and exit status `0` mean the window was built, shown and
painted; the app closes itself after 1.5 s. Qt may print harmless font or
plugin warnings.

Run the test suite:

```bash
python3 -m unittest discover -s tests
```

Expected: `Ran 343 tests ... OK`. Without PyQt6 the single real-Qt file is
skipped; everything else runs headless.

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'PyQt6'` | Activate the venv (`source .venv/bin/activate`) or install it. |
| `qt.qpa.xcb: could not connect to display` | There is no display: use `QT_QPA_PLATFORM=offscreen` for checks, or run inside the desktop session. |
| `ImportError: libGL.so.1` | Debian/Ubuntu: `sudo apt install libgl1`. |
| `python3: command not found` on Windows | Use `py` instead of `python3`, and `.venv\Scripts\activate`. |

### Português (Brasil) — Executar e testar no terminal

**Requisitos:** Python 3.10+ e PyQt6 (a única dependência).

Instale em um ambiente virtual:

```bash
git clone https://github.com/wachin/opencode-model-manager.git
cd opencode-model-manager
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 -m pip install PyQt6
```

Execute pelo terminal:

```bash
python3 opencode_model_manager.py
```

Se a configuração ainda não existir, o programa pergunta antes de criá-la.

Verifique que inicia sem tela (SSH ou CI). Usa um `HOME` descartável, então
nunca toca sua configuração, preferências ou backups reais:

```bash
tmp=$(mktemp -d)
mkdir -p "$tmp/.config/opencode"
printf '{"$schema": "https://opencode.ai/config.json", "provider": {}}' \
  > "$tmp/.config/opencode/opencode.json"
HOME="$tmp" QT_QPA_PLATFORM=offscreen python3 - <<'PY'
import sys
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication
from omm.main_window import OpenCodeModelManager

app = QApplication(sys.argv)
window = OpenCodeModelManager()
window.show()
QTimer.singleShot(1500, app.quit)
sys.exit(app.exec())
PY
```

Sem traceback e com código de saída `0`, a janela foi criada, exibida e
pintada; o programa se fecha sozinho após 1,5 s. O Qt pode imprimir avisos
de fonte ou de plugin inofensivos.

Execute a suíte de testes:

```bash
python3 -m unittest discover -s tests
```

Esperado: `Ran 343 tests ... OK`. Sem PyQt6, o único arquivo com Qt real é
ignorado; o restante roda sem tela.

| Sintoma | Solução |
|---|---|
| `ModuleNotFoundError: No module named 'PyQt6'` | Ative o venv (`source .venv/bin/activate`) ou instale o PyQt6. |
| `qt.qpa.xcb: could not connect to display` | Não há tela: use `QT_QPA_PLATFORM=offscreen` para verificações ou execute na sessão gráfica. |
| `ImportError: libGL.so.1` | Debian/Ubuntu: `sudo apt install libgl1`. |
| `python3: command not found` no Windows | Use `py` em vez de `python3` e `.venv\Scripts\activate`. |

---

## Interface

Three zones, with a `QSplitter` between the workspace and the tree:

```
┌──────────────────────────────────────────────────────────────────┐
│ Header: title · file · search · Filters · actions                │
├───────────────────────────────────────┼──────────────────────────┤
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

---

## Credentials and security

What this project guarantees and checks in the tests:

- `~/.local/share/opencode/auth.json` is **never** read or written; a test
  compares its bytes before and after the whole flow (search, filter,
  register, set default, save) and requires them to stay identical.
- An API key is **never** shown or stored in the catalog, the cache, the
  preview or `opencode.json`.
- Credentials are managed with environment variables (`env`) and with
  `/connect`. There is no key-management feature; any future addition
  would be optional and explicitly authorized by the user.
- No key is passed on the command line and no credential is sent to a
  catalog provider.
- The connection test is anonymous unless you press **Probar con mi
  clave**; in that case the key comes from the declared variable,
  travels only over HTTPS or to loopback and is redacted from any
  message. The test follows no redirects and never contacts cloud
  metadata addresses.
- URLs and imported data are validated before being accepted; writes are
  atomic and **never silently overwrite**: there is always a backup and a
  warning if the file changed outside the app.
- No scripts or npm packages are downloaded or executed automatically.

---

## Saving, backups and external-change detection

When you press **Guardar** (“Save”):

1. The structure is validated (`$schema`, `provider`, `models`, `model`,
   `small_model`, `lsp`) and the resulting JSON is checked.
2. If the file changed since your last load, you are asked whether to
   overwrite or reload — it is never replaced without warning.
3. `opencode.json.backup` is created, plus a dated copy
   `opencode-backups/opencode_YYYYMMDD_HHMMSS_micros.backup.json` (with
   microseconds so two consecutive saves cannot collide).
4. It is written to a temporary file, `fsync` is called and the file is
   replaced with `os.replace`, so a crash never leaves it half-written.

**No control writes by itself.** Adding a model, editing, setting
`model`/`small_model`, removing a model or **removing a provider** are
applied in memory and announced in the status bar. While anything is
pending, the button reads **`Guardar ●`** — with the notice “there are
changes not yet written to opencode.json” on hover — and closing the
window asks before losing the changes. That is why removing a provider
leaves its row in the tree: what goes away is the registered `●` mark, and
the name remains because it comes from the Models.dev catalog.

### Why "Quitar" is greyed out, and where you can remove

Every row in the tree comes from one of these three situations, and the
card says so with the same sentence in the row tooltip, in a visible row
called **Desde esta ventana** (“From this window”; in case the tooltip of
a disabled button is never seen) and in the buttons themselves:

| Situation | What you see | What to do |
|---|---|---|
| Registered in the open file | Bold `●` and a card that says “Proveedor” | Edit and remove work right here |
| Registered in **another** `opencode.json` | “Registrado en otro archivo” (“Registered in another file”) badge and the exact path in the notice | Open that file with **Abrir…** (“Open…”) or switch modes |
| Catalog row only | “Solo catálogo” (“Catalog only”) badge and “there is nothing to edit or remove” | It is not deleted: it is Models.dev data, not your configuration |

The `Supr` shortcut repeats the notice in the status bar, with the path of
the file where the entry really is, because with the keyboard there is no
greyed-out button to stop you.

To be able to name that other file, the application **reads**
(read-only, when loading the configuration) the standard
`opencode.json` files it does not have open: the global one, the project
one according to `discover_config()` and the one pointed to by
`OPENCODE_CONFIG`. It never reads `auth.json` or any other file, and an
unreadable path or broken JSON is silently ignored.

---

## Code architecture

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

The package is imported from `opencode_model_manager.py`, which remains
the usual entry point.

---

## Enabling LSP in OpenCode (LSP checkbox)

OpenCode can work with LSP (*Language Server Protocol*) servers to analyze
your code while the agent edits it. If you see the message
`LSPs are disabled` in OpenCode, it is because the `"lsp"` key is not
enabled in your `opencode.json`.

With this GUI it is one click: tick the **LSP** checkbox (next to **Modo
global**) and `"lsp": true` is written and saved immediately:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "lsp": true,
  "provider": {
    "bai": { "...": "..." }
  }
}
```

When you tick it, the tool checks whether the language server is installed
in `PATH`:

- **If it is installed** (e.g. `pyright`): it saves and that is it — after
  a restart, OpenCode will show `LSPs will activate as files are read`.
- **If it is missing**: it still saves `"lsp": true`, but shows a notice
  with the install command and explains that **OpenCode will keep showing
  LSP as disabled** until you install it and restart OpenCode:

  ```text
  Servidor LSP no encontrado
  ─────────────────────────
  LSP se guardará como activado, pero falta el servidor del lenguaje
  en el PATH...
    • pyright  →  npm install -g pyright
  ```

  (The dialog is in Spanish: “LSP server not found. LSP will be saved as
  enabled, but the language server is missing from PATH…”)

When you untick the checkbox, the `"lsp"` key is removed from the file.

---

## What is it for? Context: OpenCode + free B.AI

This tool was born as a companion to the tutorial
**“How to install OpenCode on Linux and Termux and use DeepSeek V4 Flash
and Hy3 through B.AI for free (limited-time promotion)”**, which is
included in this repository:

- 📄 [OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI.md](<OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI.md>)

That tutorial sets up [B.AI](https://chat.b.ai/) as an OpenCode provider
to use the `deepseek-v4-flash` (1-million-token context) and `hy3` models
**for free (limited-time promotion)**. The resulting `opencode.json`
configuration is the one this GUI edits comfortably:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "bai": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "B.AI",
      "options": {
        "baseURL": "https://api.b.ai/v1"
      },
      "models": {
        "deepseek-v4-flash": {
          "name": "DeepSeek V4 Flash (B.AI)"
        },
        "hy3": {
          "name": "Hy3 (B.AI)"
        }
      }
    }
  }
}
```

The full flow is (as an example, since promotions expire and new ones
appear):

```
Linux or Android/Termux
        │
        ▼
     OpenCode        (/connect stores the API key separately, in auth.json)
        │
        ▼
@ai-sdk/openai-compatible
        │
        ▼
 https://api.b.ai/v1
        │
        ▼
       B.AI
      ╱    ╲
     ▼      ▼
DeepSeek   Hy3
V4 Flash
```

**Workflow summary:**

1. Install OpenCode (on Linux or on Android via
   [Termux](https://github.com/guysoft/opencode-termux)).
2. Create your API key at `https://chat.b.ai/key`.
3. Inside OpenCode, run `/connect`, choose **Other** and use the provider
   ID `bai`, pasting your API key there.
4. Create `opencode.json` with the content above — or better: use this
   GUI, search `B.AI` in the catalog, check the model's real context and
   register it with one click.
5. Inside OpenCode, choose the model with `/models`.

> **Important:** promotions are temporary. Check the **Usage** section of
> B.AI regularly to monitor your account consumption.

---

## Global mode vs repository mode

| Mode | File being edited | When to use it |
|---|---|---|
| **Global** (default) | `~/.config/opencode/opencode.json` | Configuration valid for all your projects |
| **Repository** | The project's `./opencode.json` (or the one detected) | Project-specific configuration, versionable with git |

- On first launch the **Modo global** (“Global mode”) checkbox appears
  ticked; if you untick it, the current repository's configuration is
  detected automatically and the preference is saved for future sessions.
- If the file does not exist, the application offers to create a basic
  one.
- You can also open any `opencode.json` with the **Abrir…** (“Open…”)
  button (`Ctrl+O`).

---

## Automatic `providers` → `provider` migration

If your `opencode.json` uses the old `providers` key, the application
migrates it to `provider` (OpenCode's stable format) when loading it and
warns you with a dialog:

- If only `providers` exists, it is renamed to `provider`.
- If both exist, they are merged **without overwriting** what is already
  in `provider`, and `providers` is removed.

The change is made in memory; it is written to disk when you save.

---

## Tests

```bash
python3 -m unittest discover -s tests -v
```

**343 tests** in two layers, in under ten seconds:

- **Headless with a stub** (`tests/qt_stub.py`): window, panel and dialog
  logic runs without PyQt6, without windows and without touching your real
  `QSettings`. It covers the catalog (Models.dev parser, seed, cache,
  provenance, offline), search and filters (scopes, protocols including
  Bedrock/Azure, chips and sort orders), the catalog↔configuration
  boundary (`tests/test_registry.py`), the theme (`tests/test_theme.py`:
  measured WCAG contrasts, QSS order and coverage — every `objectName` and
  every widget class has its surface — and that `apply_theme()` publishes
  the palette and stylesheet to the application) and the window flows
  (`tests/test_flows.py`): tree collapsed by default, searching with the
  tree collapsed, every filter control applying on its own, `Enter` to
  open the card, the `small_model` button, registration, removal, saving,
  reloading and shortcuts. Plus the complete provider-removal path
  (`TestProviderRemoval`): it asks for confirmation, leaves the file
  untouched until Save, announces it in the status bar, marks the button
  with `●`, discards the `model` that pointed to that provider and, if the
  provider is only in the catalog, the disabled button explains why. The
  provenance of each entry is watched by `TestEntryOriginIsExplained`: the
  row tooltip, the visible card row, the disabled button and the `Supr`
  notice say the same thing, name the exact file when the entry lives in
  another `opencode.json` (the B.AI case) and the badge stops calling
  “catalog only” something registered elsewhere. Writing that test
  revealed an isolation hole: with `OPENCODE_CONFIG` in the environment,
  the fixture could end up reading the user's real `opencode.json`; the
  `setUp` now removes it. It also watches the card: every row is added
  with `addLayout`, so `item.widget()` is `None`; the stub now replicates
  that detail (and the reparenting Qt does) and checks that the card
  contains exactly two labels per row, on a new view or a repeated one.
  The connection test has its own file (`tests/test_probe.py`, no Qt): a
  fake `opener` covers the URL per protocol (Bedrock/Azure are declared
  unprobeable), refusals (no URL, metadata host, cleartext key), HTTP
  statuses, body decoding and key redaction; and a real `http.server` on
  loopback checks end to end that a 3xx is not followed (a second server
  records zero hits) and that the sent key never reappears in the report
  if the server echoes it. In the flows (`TestConnectionProbe`) it
  measures which buttons light up — registered, catalog-only, no
  endpoint, metadata host, Bedrock —, the environment row
  (`presente`/`ausente`, never the value), the result row in the card with
  what is missing, that the anonymous test carries no credentials, that a
  401 still counts as “alive”, that the keyed variant sends `Bearer`
  without leaking it to the view or the disk, that the result survives
  switching cards and that a second test is not started while the first
  one runs. The security constraints are also tested: `auth.json`
  identical byte for byte, no key written and searching registers
  nothing.
- **Real Qt** (`tests/test_app_launch.py`): launches the real application
  with `QT_QPA_PLATFORM=offscreen` on a temporary HOME, pumps the event
  loop until the `QThread` publishes the cache and runs search → filter →
  expand → register → set `small_model` → save. It checks that the process
  ends without tracebacks, that the final file is valid JSON and keeps
  what was there before, that a backup was left, that no `.tmp` files
  remain and that `auth.json` was not touched. With `findChildren(QLabel)`
  on the card it measures, after three consecutive views, that only the
  labels of the visible row remain (this is the duplicated-text defect the
  user reported: with real Qt the labels really are children of the card,
  and the stub ignored them). With the same binary it removes a registered
  provider (answering “Sí” to the question) and checks that the notice
  appears in the status bar, that the button becomes `Guardar ●`, that
  `opencode.json` was not touched and that “Cambios sin guardar”
  (“Unsaved changes”) appears on close. With the same binary, and with a
  **second** `opencode.json` passed through `OPENCODE_CONFIG`, it reads
  `toolTip(0)` from the tree rows and their models: the registered row
  says which file it is in, the one living in the foreign file names both
  and the badge becomes “Registrado en otro archivo”. The connection test
  runs with a real `ProbeWorker`: the thread does its GET against an
  injected `opener`, the signal repaints the card and the status bar, the
  “Probando…” (“Testing…”) text is observed while it runs, and then the
  provider variable is defined for the keyed variant: the `Authorization`
  reaches the `opener`, the key appears in no label, report or file, and
  `opencode.json` and `auth.json` stay identical. It also forces a
  **dark system palette** and measures pixels of the painted window: the
  light theme must come out light (header, workspace, status bar and the
  dialog's tab panel) and the dark one dark. It is skipped only if PyQt6
  is not installed.

Use `discover` (it adds `tests/` to `PYTHONPATH` so `support.py` can be
found). The suite also covers the `providers` → `provider` migration,
global mode (default value, toggling and persistence), the LSP checkbox
(writing and deleting the `"lsp"` key, detecting `pyright` in `PATH` with
and without it installed) and window-geometry persistence.

---

## Links

- Full tutorial (included in this repo):
  [OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI](<OpenCode en Linux y Termux y usar gratis DeepSeek V4 Flash y Hy3 mediante B.AI.md>)
- OpenCode: <https://opencode.ai/> · Documentation:
  <https://opencode.ai/docs/>
- Provider and model catalog: <https://models.dev> (MIT)
- B.AI: <https://chat.b.ai/> · API key:
  <https://chat.b.ai/key>
- Port built with this workflow (OpenCode + DeepSeek V4 Flash):
  <https://github.com/wachin/TBO>
