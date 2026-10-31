"""Arranque común de los tests: stub de PyQt6 + import del paquete omm.

Los tests unitarios corren headless y con QSettings en memoria, aunque
PyQt6 esté instalado en el sistema (force=True).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Los tests existentes comprueban los textos en español. OMM_LANG gana a la
# preferencia guardada, así que la ventana arranca en español aunque el
# QSettings de prueba no tenga idioma.
os.environ.setdefault("OMM_LANG", "es")

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent

for path in (str(TESTS_DIR), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import qt_stub  # noqa: E402

qt_stub.install(force=True)

from omm import catalog, main_window, registry, search, theme, workers  # noqa: E402
from omm.i18n import set_language  # noqa: E402

# Los tests existentes comprueban los textos en español; los del módulo
# i18n fijan su propio idioma y lo restauran al terminar.
set_language("es")

__all__ = [
    "ROOT", "TESTS_DIR", "catalog", "main_window", "qt_stub", "registry",
    "search", "theme", "workers",
]
