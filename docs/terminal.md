# Run and test from the terminal

[Back to the README](../README.md)

Install, launch and verify the app from a terminal, including a headless
check for SSH or CI. The app is bilingual (English by default, Spanish
from the header selector); these are translated instructions, not
translated buttons.

---

## English — Run and test from the terminal

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

Expected: `Ran 357 tests ... OK`. Without PyQt6 the single real-Qt file is
skipped; everything else runs headless.

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'PyQt6'` | Activate the venv (`source .venv/bin/activate`) or install it. |
| `qt.qpa.xcb: could not connect to display` | There is no display: use `QT_QPA_PLATFORM=offscreen` for checks, or run inside the desktop session. |
| `ImportError: libGL.so.1` | Debian/Ubuntu: `sudo apt install libgl1`. |
| `python3: command not found` on Windows | Use `py` instead of `python3`, and `.venv\Scripts\activate`. |

---

## Português (Brasil) — Executar e testar no terminal

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

Esperado: `Ran 357 tests ... OK`. Sem PyQt6, o único arquivo com Qt real é
ignorado; o restante roda sem tela.

| Sintoma | Solução |
|---|---|
| `ModuleNotFoundError: No module named 'PyQt6'` | Ative o venv (`source .venv/bin/activate`) ou instale o PyQt6. |
| `qt.qpa.xcb: could not connect to display` | Não há tela: use `QT_QPA_PLATFORM=offscreen` para verificações ou execute na sessão gráfica. |
| `ImportError: libGL.so.1` | Debian/Ubuntu: `sudo apt install libgl1`. |
| `python3: command not found` no Windows | Use `py` em vez de `python3` e `.venv\Scripts\activate`. |
