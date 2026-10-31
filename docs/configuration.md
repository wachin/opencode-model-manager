# Configuration

[Back to the README](../README.md)

How the app reads and writes `opencode.json`: global vs repository mode,
save and backup rules, why some rows cannot be removed, the automatic
migration and the LSP checkbox.

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

The automatic search order is `OPENCODE_CONFIG` → `./opencode.json` →
upward search in a git repository → `~/.config/opencode/opencode.json`.
In global mode, `OPENCODE_CONFIG` is ignored on purpose because you have
explicitly chosen to work on the global file.

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

---

## Why "Quitar" is greyed out, and where you can remove

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

## Automatic `providers` → `provider` migration

If your `opencode.json` uses the old `providers` key, the application
migrates it to `provider` (OpenCode's stable format) when loading it and
warns you with a dialog:

- If only `providers` exists, it is renamed to `provider`.
- If both exist, they are merged **without overwriting** what is already
  in `provider`, and `providers` is removed.

The change is made in memory; it is written to disk when you save.

---

## LSP server for Python (recommended)

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
  LSP server not found
  ────────────────────
  LSP will be saved as enabled, but the language server is missing
  from PATH...
    • pyright  →  npm install -g pyright
  ```

  (In Spanish: “Servidor LSP no encontrado. LSP se guardará como
  activado, pero falta el servidor del lenguaje en el PATH…”.)

When you untick the checkbox, the `"lsp"` key is removed from the file.
