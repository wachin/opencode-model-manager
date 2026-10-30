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


def main():
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        print("ERROR: PyQt6 no está instalado.")
        print("Instálalo con: pip install PyQt6")
        sys.exit(1)

    from omm.main_window import APP_NAME, OpenCodeModelManager

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)

    window = OpenCodeModelManager()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
