"""Trabajadores de Qt para red y catálogo sin bloquear la GUI.

Las descargas y el parseo ocurren SIEMPRE fuera del hilo principal.
Nunca se envían credenciales salvo en la prueba explícita «Probar con mi
clave», y jamás se ejecuta código descargado: se transforman datos JSON en
estructuras del catálogo.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from omm.catalog import CatalogStore
from omm.i18n import tr
from omm.probe import (
    PROBE_TIMEOUT_SECONDS, KIND_ERROR, KIND_NO_ENV, ProbeResult,
    first_present_env, probe_endpoint,
)


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


class ProbeWorker(QThread):
    """«Probar conexión» en segundo plano; el resultado viaja en la señal.

    Si se pide la prueba con clave, el valor se resuelve AQUÍ dentro desde
    os.environ: no pasa por el objeto del hilo ni por ninguna señal, y el
    ProbeResult que sale ya está redactado. No escribe nada en disco.
    """

    done = pyqtSignal(object)

    def __init__(
        self,
        base_url: str,
        protocol: str = "",
        env_names=(),
        with_key: bool = False,
        wanted_models=(),
        opener=None,
        timeout: int = PROBE_TIMEOUT_SECONDS,
        parent=None,
    ):
        super().__init__(parent)
        self.base_url = base_url
        self.protocol = protocol
        self.env_names = tuple(env_names or ())
        self.with_key = with_key
        self.wanted_models = tuple(wanted_models or ())
        self.opener = opener
        self.timeout = timeout

    def run(self) -> None:
        api_key, env_name = "", ""
        if self.with_key:
            env_name, api_key = first_present_env(self.env_names)
            if not api_key:
                declared = ", ".join(self.env_names) or tr(
                    "The provider variable", es="La variable del proveedor"
                )
                detail = tr(
                    "{declared} is not defined in this window's environment; "
                    "there is nothing to send.",
                    es="{declared} no está definida en el entorno de esta "
                       "ventana; no hay nada que enviar.",
                ).format(declared=declared)
                self.done.emit(ProbeResult(
                    kind=KIND_NO_ENV,
                    summary=tr("No key in the environment",
                               es="Sin clave en el entorno"),
                    detail=detail,
                    url=self.base_url,
                ))
                return
        try:
            result = probe_endpoint(
                self.base_url,
                protocol=self.protocol,
                api_key=api_key,
                env_name=env_name,
                wanted_models=self.wanted_models,
                opener=self.opener,
                timeout=self.timeout,
            )
        except Exception as exc:  # ninguna excepción debe dejar el botón «Probando…»
            result = ProbeResult(
                kind=KIND_ERROR,
                summary=tr("The test could not be completed",
                           es="La prueba no ha podido completarse"),
                detail=str(exc) or exc.__class__.__name__,
                url=self.base_url,
            )
        self.done.emit(result)
