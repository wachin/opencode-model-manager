"""Trabajadores de Qt para red y catálogo sin bloquear la GUI.

Las descargas y el parseo ocurren SIEMPRE fuera del hilo principal.
Nunca se envían credenciales ni se ejecuta código descargado: se
transforman datos JSON en estructuras del catálogo.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from omm.catalog import CatalogStore


class CatalogLoadWorker(QThread):
    """Carga la caché del catálogo y opcionalmente la refresca desde Models.dev.

    Señales:
        loaded(dict)  — {providers, meta} al terminar con éxito.
        failed(str)   — mensaje legible del fallo (offline, JSON inválido…).
    """

    loaded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, store: CatalogStore, refresh_remote: bool = False, parent=None):
        super().__init__(parent)
        self.store = store
        self.refresh_remote = refresh_remote

    def run(self) -> None:
        try:
            # Store propio: el hilo nunca escribe en el catálogo que lee la
            # GUI. Los datos completos viajan en la señal `loaded`.
            probe = CatalogStore(directory=self.store.directory)
            if not self.refresh_remote:
                probe.load_cache()
                self.loaded.emit({"providers": probe.providers,
                                  "source": probe.loaded_source,
                                  "last_updated": probe.last_updated})
                return
            count = probe.refresh()
            self.loaded.emit({"providers": probe.providers,
                              "source": probe.loaded_source,
                              "models": count,
                              "last_updated": probe.last_updated})
        except Exception as exc:  # red, JSON, sistema de archivos
            self.failed.emit(str(exc) or exc.__class__.__name__)
