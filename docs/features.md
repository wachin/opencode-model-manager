# Features

[Back to the README](../README.md)

A complete list of what OpenCode API Manager does. For day-to-day steps,
see [usage](usage.md); for saving rules and LSP, see
[configuration](configuration.md).

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
