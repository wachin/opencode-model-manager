# Tests

[Back to the README](../README.md)

```bash
python3 -m unittest discover -s tests -v
```

**344 tests** in two layers, in under ten seconds:

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
