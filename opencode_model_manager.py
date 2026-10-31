#!/usr/bin/env python3
"""
OpenCode API Manager
====================

Punto de entrada del programa. La interfaz vive en ``omm.main_window`` y
el resto se reparte en módulos: catálogo (``omm.catalog``), búsqueda
(``omm.search``), configuración de OpenCode (``omm.registry``), hilos de
segundo plano (``omm.workers``), tema (``omm.theme``) y paneles/diálogos
(``omm.ui``).

Requisito:
    pip install PyQt6

Uso:
    python3 opencode_model_manager.py
"""

import sys
from pathlib import Path

ICON_PATH = Path(__file__).resolve().parent / "omm" / "assets" / "icon.png"


def main():
    from omm.i18n import init_language, tr

    init_language()
    try:
        from PyQt6.QtGui import QIcon
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print(tr("ERROR: PyQt6 is not installed.",
                 es="ERROR: PyQt6 no está instalado."))
        print(tr("Install it with: pip install PyQt6",
                 es="Instálalo con: pip install PyQt6"))
        sys.exit(1)

    from omm.main_window import APP_NAME, OpenCodeModelManager

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))

    window = OpenCodeModelManager()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
