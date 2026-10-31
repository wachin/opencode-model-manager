"""Ventana principal del OpenCode API Manager.

Así se organiza la interfaz:

- Cabecera (``HeaderBar``): título, archivo de configuración, búsqueda
  instantánea, orden de resultados y acciones.
- Panel de filtros plegable (``FilterPanel``).
- Área de trabajo (``QStackedWidget``): resumen, resultados o detalle.
- Barra lateral derecha: árbol proveedor → modelos, plegado por defecto
  y con los hijos cargados de forma perezosa.

Principios que no cambian nunca:

- Las credenciales las gestiona OpenCode con /connect; este módulo no
  lee, muestra ni escribe auth.json y ningún campo acepta API keys.
- Ningún modelo del catálogo se escribe en la configuración por aparecer
  en los resultados: solo se registra lo que el usuario agrega de forma
  explícita.
- Antes de guardar se valida la estructura, se detectan cambios externos
  y se crea una copia de seguridad; la escritura es atómica.
- La red ocurre siempre en un hilo aparte (``CatalogLoadWorker``).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from copy import copy, deepcopy
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QColor, QKeySequence, QPalette, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QFrame, QLabel,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSplitter,
    QStackedWidget, QVBoxLayout, QWidget,
)

from omm.catalog import CatalogStore
from omm.registry import (
    action_note,
    add_catalog_model_to_config, add_provider_to_config, config_base_url,
    config_providers, configured_full_ids, full_id, model_detail_rows,
    provider_from_config, remove_model_from_config,
    remove_provider_from_config, set_default_model, tree_data,
    validate_config,
)
from omm.search import Filters, catalog_pairs, search
from omm.theme import DARK, LIGHT, build_stylesheet
from omm.ui.dialogs import ModelDialog, PreviewDialog, ProviderDialog
from omm.ui.panels import (
    DetailsPanel, FilterPanel, HeaderBar, OverviewPanel, ProviderTreePanel,
    SearchResultsPanel,
)
from omm.workers import CatalogLoadWorker


APP_NAME = "OpenCode API Manager"
ACCEPTED = QDialog.DialogCode.Accepted

# Páginas del área de trabajo.
PAGE_OVERVIEW = 0
PAGE_RESULTS = 1
PAGE_DETAILS = 2

SPLITTER_SIZES_DEFAULT = [860, 300]
LSP_SERVER_HINTS = {"python": "pyright"}
SCHEMA_URL = "https://opencode.ai/config.json"


# ---------------------------------------------------------------------------
# Utilidades de configuración (sin dependencias de PyQt más allá de this
# módulo): también las usan las pruebas.
# ---------------------------------------------------------------------------

def lsp_server_installed(server: str) -> bool:
    """True si el ejecutable del servidor LSP está en el PATH."""
    return shutil.which(server) is not None


def lsp_languages(data: dict) -> list[str]:
    """Lenguajes declarados en la configuración de OpenCode.

    Lee "language servers" del propio opencode.json (formato de
    OpenCode: {"python": "pyright", ...}) y añade "python" como
    mínimo, porque es el lenguaje de los proyectos habituales.
    """
    languages: set[str] = {"python"}
    servers = data.get("language servers")
    if isinstance(servers, dict):
        for lang in servers:
            languages.add(str(lang).lower())
    return sorted(languages)


def missing_lsp_servers(languages: list[str]) -> list[str]:
    """Servidores LSP de la configuración que no están instalados."""
    missing = []
    for lang in languages:
        server = LSP_SERVER_HINTS.get(str(lang).lower())
        if server and not lsp_server_installed(server):
            missing.append(server)
    return missing


def global_config_path() -> Path:
    """Ruta del opencode.json global de OpenCode.

    Nota: OpenCode también respeta la variable OPENCODE_CONFIG, pero en
    modo global esa variable se ignora deliberadamente porque el usuario
    ha elegido explícitamente trabajar sobre el archivo global.
    """
    return Path.home() / ".config" / "opencode" / "opencode.json"


def discover_config() -> Path:
    """Busca la configuración de OpenCode según su prioridad habitual."""
    custom = os.environ.get("OPENCODE_CONFIG")
    if custom:
        return Path(custom).expanduser()

    cwd = Path.cwd()
    project = cwd / "opencode.json"
    if project.exists():
        return project

    # Si estamos dentro de un repositorio Git, se detiene ahí: el archivo
    # del repositorio manda sobre el global.
    current = cwd
    while current != current.parent:
        candidate = current / "opencode.json"
        if candidate.exists():
            return candidate
        if (current / ".git").exists():
            break
        current = current.parent

    if global_config_path().exists():
        return global_config_path()

    return project


def file_info(path: Path) -> tuple[str, str]:
    """(tamaño legible, fecha de modificación) del archivo de configuración."""
    if not path.exists():
        return "(no existe)", "(no existe)"
    st = path.stat()
    size = st.st_size
    if size < 1024:
        size_str = f"{size} B"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"
    return size_str, datetime.fromtimestamp(st.st_mtime).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def file_fingerprint(path: Path) -> tuple[float, int, str] | None:
    """Huella (mtime, tamaño, sha256) del archivo, o None si no existe.

    Permite detectar si OpenCode u otro editor cambió el archivo mientras
    esta ventana lo tenía cargado.
    """
    try:
        data = Path(path).read_bytes()
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    return mtime, len(data), hashlib.sha256(data).hexdigest()


def model_display_name(model_id, model_data):
    if isinstance(model_data, dict):
        return model_data.get("name") or model_data.get("modelID") or model_id
    return model_id


# ---------------------------------------------------------------------------
# Ventana principal
# ---------------------------------------------------------------------------

class OpenCodeModelManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1040, 620)
        self.resize(1280, 780)
        self._fit_to_screen()

        self.settings = QSettings("OpenCodeTools", "OpenCodeModelManager")
        self._restore_window_geometry()

        self.use_global = bool(self.settings.value("use_global", True, type=bool))
        self.config_path = (
            global_config_path() if self.use_global else discover_config()
        )
        self.data: dict = {}
        self.models: list = []

        self.catalog = CatalogStore()
        self.filters = Filters()
        self.worker = None
        self._file_fingerprint = None
        self._saved_json: str | None = None
        self._foreign_providers: dict[str, list[str]] = {}
        self._current_entry: tuple[str, str] = ("", "")
        self._current_kind = "model"
        self._theme_mode = str(self.settings.value("theme", "auto"))

        self.build_ui()
        self.setup_shortcuts()
        self.apply_theme()
        self._load_catalog_cache()
        self.load_config()

    # ------------------------------------------------------------------
    # Geometría persistente
    # ------------------------------------------------------------------

    def _fit_to_screen(self, clamp_position=False):
        """Ajusta tamaño y posición al área disponible del monitor.

        Evita que la barra de título quede fuera de la pantalla en
        monitores pequeños: la ventana nunca pide más alto o ancho que
        el área libre del escritorio (sin paneles ni barras).

        Con clamp_position=True (usado al restaurar una geometría
        guardada) también reencuadra la posición, por si la ventana se
        guardó en un monitor o resolución que ya no existe.
        """
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = min(self.width(), available.width())
        height = min(self.height(), available.height())
        if (width, height) != (self.width(), self.height()):
            self.resize(width, height)
        if clamp_position:
            x = min(max(self.x(), available.left()), available.right() - 120)
            y = min(max(self.y(), available.top()), available.bottom() - 40)
            if (x, y) != (self.x(), self.y()):
                self.move(x, y)

    def _restore_window_geometry(self):
        """Restaura tamaño y posición guardados en la sesión anterior.

        Si no hay geometría guardada (o está corrupta) se conserva la que
        acaba de definirse en __init__. En ambos casos se reencuadra al
        área disponible del monitor actual.
        """
        geometry = self.settings.value("geometry")
        restored = False
        if geometry is not None:
            try:
                restored = self.restoreGeometry(geometry)
            except Exception:
                restored = False
        self._fit_to_screen(clamp_position=restored)

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- cabecera + acciones ----
        self.header = HeaderBar()
        self._build_header_actions()
        root.addWidget(self.header)
        self.header.search_changed.connect(self.on_search_changed)
        self.header.sort_changed.connect(self.on_sort_changed)
        self.header.filters_toggled.connect(self.toggle_filter_panel)

        # ---- panel de filtros (plegable) ----
        self.filter_panel = FilterPanel()
        self.filter_panel.filters_changed.connect(self.update_view)
        self.filter_panel.clear_requested.connect(self.clear_all)
        wrap = QScrollArea()
        wrap.setObjectName("filterWrap")
        wrap.setWidgetResizable(True)
        wrap.setFrameShape(QFrame.Shape.NoFrame)
        wrap.setWidget(self.filter_panel)
        wrap.setMaximumHeight(190)
        wrap.setVisible(False)
        self.filter_wrap = wrap
        root.addWidget(wrap)

        # ---- área de trabajo ----
        self.overview = OverviewPanel()
        self.results = SearchResultsPanel()
        self.details = DetailsPanel()

        self.workspace = QStackedWidget()
        self.workspace.setObjectName("workspace")
        self.workspace.addWidget(self.overview)
        self.workspace.addWidget(self.results)
        self.workspace.addWidget(self.details)
        self.workspace.setCurrentIndex(PAGE_OVERVIEW)

        self.results.open_requested.connect(self.show_model)
        self.results.model_selected.connect(self.show_model)
        self.details.add_requested.connect(self.details_add)
        self.details.edit_requested.connect(self.details_edit)
        self.details.set_default_requested.connect(self.details_set_default)
        self.details.copy_id_requested.connect(self.details_copy_id)
        self.details.copy_endpoint_requested.connect(self.details_copy_endpoint)
        self.details.remove_requested.connect(self.details_remove)

        # ---- barra lateral derecha: árbol proveedor → modelos ----
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(10, 10, 10, 10)
        side_layout.setSpacing(6)

        side_title = QLabel("Proveedores")
        side_title.setObjectName("sectionTitle")
        side_layout.addWidget(side_title)

        hint = QLabel(
            "Clic para desplegar · ● proveedor registrado · ✓ modelo registrado"
        )
        hint.setObjectName("hintLabel")
        hint.setWordWrap(True)
        side_layout.addWidget(hint)

        self.tree = ProviderTreePanel()
        side_layout.addWidget(self.tree, 1)
        self.tree.provider_selected.connect(self.show_provider)
        self.tree.model_selected.connect(self.show_model)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("workspaceSplitter")
        self.splitter.addWidget(self.workspace)
        self.splitter.addWidget(sidebar)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setSizes(self._restored_splitter_sizes())
        root.addWidget(self.splitter, 1)

        self.statusBar().showMessage("Listo.")
        self._sync_checkboxes()

    def _build_header_actions(self):
        self.open_btn = QPushButton("Abrir…")
        self.open_btn.setObjectName("ghost")
        self.open_btn.setToolTip("Abrir un opencode.json concreto (Ctrl+O).")
        self.open_btn.clicked.connect(self.open_config)

        self.reload_btn = QPushButton("Recargar")
        self.reload_btn.setObjectName("ghost")
        self.reload_btn.setToolTip("Volver a leer el archivo actual.")
        self.reload_btn.clicked.connect(self.load_config)

        self.refresh_catalog_btn = QPushButton("Refrescar catálogo")
        self.refresh_catalog_btn.setObjectName("ghost")
        self.refresh_catalog_btn.setToolTip(
            "Descargar Models.dev en segundo plano.\n"
            "La petición es anónima: no se envían credenciales."
        )
        self.refresh_catalog_btn.clicked.connect(self.refresh_catalog)

        self.provider_btn = QPushButton("+ Proveedor")
        self.provider_btn.setObjectName("primary")
        self.provider_btn.setToolTip(
            "Alta guiada o importación JSON de un proveedor externo.\n"
            "La API key se introduce aparte, con /connect."
        )
        self.provider_btn.clicked.connect(self.add_provider)

        self.add_model_btn = QPushButton("+ Modelo")
        self.add_model_btn.setObjectName("ghost")
        self.add_model_btn.setToolTip(
            "Registrar un modelo a mano en el proveedor seleccionado."
        )
        self.add_model_btn.clicked.connect(lambda: self.add_model())

        self.preview_btn = QPushButton("Vista previa")
        self.preview_btn.setObjectName("ghost")
        self.preview_btn.setToolTip("Ver el JSON que se escribiría al guardar.")
        self.preview_btn.clicked.connect(self.show_preview)

        self.theme_btn = QPushButton("Tema: auto")
        self.theme_btn.setObjectName("ghost")
        self.theme_btn.setToolTip("Alterna auto → claro → oscuro.")
        self.theme_btn.clicked.connect(self.toggle_theme)

        self.backup_btn = QPushButton("Copiar archivo")
        self.backup_btn.setObjectName("ghost")
        self.backup_btn.setToolTip(
            "Crear ahora una copia fechada del opencode.json del disco."
        )
        self.backup_btn.clicked.connect(self.create_backup)

        self.save_btn = QPushButton("Guardar")
        self.save_btn.setObjectName("primary")
        self.save_btn.setToolTip(
            "Valida, respalda y guarda opencode.json (Ctrl+S)."
        )
        self.save_btn.clicked.connect(self.save_config)

        for widget in (
            self.open_btn, self.reload_btn, self.refresh_catalog_btn,
            self.provider_btn, self.add_model_btn, self.preview_btn,
            self.backup_btn, self.theme_btn, self.save_btn,
        ):
            self.header.row1.addWidget(widget)

        self.global_check = QCheckBox("Modo global")
        self.global_check.setToolTip(
            "Trabajar siempre sobre ~/.config/opencode/opencode.json "
            "en lugar del opencode.json del repositorio actual."
        )
        self.global_check.stateChanged.connect(self.toggle_global_mode)

        self.lsp_check = QCheckBox("LSP")
        self.lsp_check.setToolTip(
            "Activa o desactiva los servidores LSP de OpenCode (clave \"lsp\"\n"
            "de opencode.json). Requiere tener instalado el servidor del\n"
            "lenguaje; para Python: npm install -g pyright"
        )
        self.lsp_check.stateChanged.connect(self.toggle_lsp)

        self.header.row2.addWidget(self.global_check)
        self.header.row2.addWidget(self.lsp_check)

    def _sync_checkboxes(self):
        """Refleja el estado cargado sin disparar señales."""
        for check, value in (
            (self.global_check, self.use_global),
            (self.lsp_check, bool(self.data.get("lsp"))),
        ):
            check.blockSignals(True)
            check.setChecked(bool(value))
            check.blockSignals(False)

    def _restored_splitter_sizes(self) -> list[int]:
        stored = self.settings.value("splitter_sizes")
        if isinstance(stored, (list, tuple)) and len(stored) == 2:
            try:
                sizes = [int(value) for value in stored]
            except (TypeError, ValueError):
                return list(SPLITTER_SIZES_DEFAULT)
            if all(size > 0 for size in sizes):
                return sizes
        return list(SPLITTER_SIZES_DEFAULT)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_config)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self.load_config)
        QShortcut(
            QKeySequence("Ctrl+Shift+R"), self
        ).activated.connect(self.refresh_catalog)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_config)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.focus_search)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self.escape_pressed)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.details_remove)

    # ------------------------------------------------------------------
    # Tema claro/oscuro
    # ------------------------------------------------------------------

    def toggle_theme(self):
        order = ("auto", "light", "dark")
        index = order.index(self._theme_mode) if self._theme_mode in order else 0
        self._theme_mode = order[(index + 1) % len(order)]
        self.settings.setValue("theme", self._theme_mode)
        self.apply_theme()

    def _prefers_dark(self) -> bool:
        """Si el escritorio del usuario es oscuro (para el modo «auto»).

        Se lee la paleta del ESTILO, no la de la aplicación: la nuestra se
        pone en su sitio al aplicar el tema y leerla de vuelta convertiría el
        modo auto en un bucle sobre sí mismo.
        """
        app = QApplication.instance()
        if app is None:
            return False
        try:
            window_color = app.style().standardPalette().color(
                QPalette.ColorRole.Window
            )
            return window_color.lightness() < 128
        except Exception:
            return False

    def _palette_for(self, mode: str):
        if mode == "light":
            return LIGHT
        if mode == "dark":
            return DARK
        return DARK if self._prefers_dark() else LIGHT

    def apply_theme(self):
        """Publica el tema en toda la aplicación, no sólo en la ventana.

        Se fijan las dos capas: la hoja de estilos (lo que la app pinta) y la
        QPalette (lo que hereda todo lo que la hoja no cubre: popups de
        combos, diálogos, cuadros de mensaje, texto desactivado). Si sólo se
        pone la hoja de estilos, el tema claro sale con el fondo del escritorio
        oscuro asomando por cada hueco.
        """
        palette = self._palette_for(self._theme_mode)
        self._palette = palette
        app = QApplication.instance()
        if app is not None:
            qpal = app.palette()
            for name, hex_color in palette.roles().items():
                group, _, role = name.rpartition(".")
                qpal.setColor(
                    getattr(QPalette.ColorGroup, group or "Active"),
                    getattr(QPalette.ColorRole, role),
                    QColor(hex_color),
                )
            app.setPalette(qpal)
        target = app if app is not None else self
        target.setStyleSheet(build_stylesheet(palette))
        self.tree.set_configured_color(palette.success)
        self.theme_btn.setText(f"Tema: {self._theme_mode}")
        if self.workspace.currentIndex() == PAGE_OVERVIEW:
            self.overview.show_summary(self._overview_html())

    # ------------------------------------------------------------------
    # Catálogo: carga y refresco fuera del hilo de la GUI
    # ------------------------------------------------------------------

    def _load_catalog_cache(self):
        self._start_worker(refresh_remote=False)

    def refresh_catalog(self):
        if self.worker is not None and self.worker.isRunning():
            self.statusBar().showMessage(
                "Ya hay una descarga del catálogo en curso."
            )
            return
        self.statusBar().showMessage("Descargando catálogo de Models.dev…")
        self._start_worker(refresh_remote=True)

    def _start_worker(self, refresh_remote: bool):
        worker = CatalogLoadWorker(self.catalog, refresh_remote=refresh_remote)
        worker.loaded.connect(self._on_catalog_loaded)
        worker.failed.connect(self._on_catalog_failed)
        worker.finished.connect(self._on_catalog_finished)
        self.worker = worker
        worker.start()

    def _on_catalog_finished(self):
        self.worker = None

    def _on_catalog_loaded(self, payload):
        source = (payload or {}).get("source", "seed")
        providers = (payload or {}).get("providers")
        if isinstance(providers, dict):
            self.catalog.adopt(providers, payload.get("last_updated"), source)
        self.update_tree()
        self.update_view()
        if source == "remote":
            self.statusBar().showMessage(
                f"Catálogo actualizado: {self.catalog.model_count} modelos de "
                f"{len(self.catalog.providers)} proveedores."
            )
        else:
            self.statusBar().showMessage(self.catalog.describe_source())

    def _on_catalog_failed(self, message):
        self.statusBar().showMessage(
            f"No se pudo actualizar el catálogo ({message}). "
            "Se sigue usando la copia local."
        )

    def update_tree(self):
        rows = tree_data(self.catalog.providers, self.data)
        notes = {}
        for row in rows:
            notes[row["id"]] = self.note_for(
                row["name"], row["configured"], row["id"]
            )
            for mrow in row["models"]:
                key = full_id(row["id"], mrow["id"])
                notes[key] = self.note_for(mrow["name"], mrow["configured"], key)
        self.tree.set_rows(rows, notes=notes, config_path=str(self.config_path))

    def search_universe(self) -> dict:
        """Catálogo + modelos registrados que no existen en el catálogo.

        Así la búsqueda encuentra tanto las entradas de Models.dev como
        las que el usuario configuró a mano. No muta el catálogo: los
        proveedores que necesitan modelos añadidos se copian antes.
        """
        providers = dict(self.catalog.providers)
        for pid, pdata in config_providers(self.data).items():
            entry = provider_from_config(pid, pdata)
            base = providers.get(pid)
            if base is None:
                providers[pid] = entry
                continue
            missing = {
                mid: model
                for mid, model in entry.models.items()
                if mid not in base.models
            }
            if missing:
                merged = copy(base)
                merged.models = {**base.models, **missing}
                providers[pid] = merged
        return providers

    # ------------------------------------------------------------------
    # Búsqueda, filtros y páginas del área de trabajo
    # ------------------------------------------------------------------

    def on_search_changed(self, text: str):
        self.filters = self.filters.with_(text=text or "")
        self.update_view()

    def on_sort_changed(self, sort: str, descending: bool):
        self.filters = self.filters.with_(sort=sort, descending=descending)
        self.update_view()

    def focus_search(self):
        self.header.search_edit.setFocus()
        self.header.search_edit.selectAll()

    def clear_all(self):
        """Esc / «Limpiar filtros»: deja la vista en el resumen."""
        self.header.search_edit.blockSignals(True)
        self.header.search_edit.clear()
        self.header.search_edit.blockSignals(False)
        self.filter_panel.reset_controls()
        self.filters = self.filters.with_(text="")
        self.update_view()

    def escape_pressed(self):
        if self.header.search_edit.text():
            self.clear_all()
        elif self.filter_wrap.isVisible():
            self.header.filters_btn.blockSignals(True)
            self.header.filters_btn.setChecked(False)
            self.header.filters_btn.blockSignals(False)
            self.toggle_filter_panel(False)

    def toggle_filter_panel(self, visible: bool):
        self.filter_wrap.setVisible(bool(visible))

    def update_view(self):
        """Aplica búsqueda y filtros sobre los DATOS, no sobre el árbol.

        Un proveedor plegado en el árbol coincide igual que uno desplegado:
        la visibilidad de los widgets nunca interviene en el resultado.
        """
        filters = self.filter_panel.current_filters(self.filters).with_(
            text=self.header.search_edit.text() or ""
        )
        self.filters = filters

        if not filters.is_active():
            self.show_overview()
            return

        found, total = search(
            catalog_pairs(self.search_universe()),
            filters,
            configured_full_ids(self.data),
        )
        self.results.show_results(found)
        self.workspace.setCurrentIndex(PAGE_RESULTS)

        summary = filters.summary()
        note = f"{total} coincidencia{'s' if total != 1 else ''}"
        if len(found) < total:
            note += f" · mostrando {len(found)}"
        if summary:
            note += f" · {summary}"
        self.header.set_count(note)

    def show_overview(self):
        self.workspace.setCurrentIndex(PAGE_OVERVIEW)
        self.header.set_count("")
        self.overview.show_summary(self._overview_html())

    def _overview_html(self) -> str:
        providers = config_providers(self.data)
        model_count = sum(
            len(pdata.get("models") or {})
            for pdata in providers.values()
            if isinstance(pdata, dict)
        )
        size, mtime = file_info(self.config_path)
        rows = [
            ("Archivo", str(self.config_path)),
            (
                "Modo",
                f"{'global' if self.use_global else 'repositorio'} · "
                f"{size} · modificado {mtime}",
            ),
            ("Proveedores registrados", str(len(providers))),
            ("Modelos registrados", str(model_count)),
            ("model", str(self.data.get("model") or "(sin predeterminado)")),
            ("small_model", str(self.data.get("small_model") or "(automático)")),
            ("LSP", "activado" if self.data.get("lsp") else "desactivado"),
            ("Catálogo", self.catalog.describe_source()),
        ]
        table = "".join(
            "<tr>"
            f"<td style='color:{self._palette.text_muted};"
            f"padding:3px 16px 3px 0;'>{key}</td>"
            f"<td>{value}</td></tr>"
            for key, value in rows
        )
        return (
            "<div style='line-height:150%'>"
            "<p>Escribe en la barra de búsqueda para explorar proveedores y "
            "modelos (<b>Ctrl+F</b>). Despliega un proveedor en el panel "
            "derecho para ver sus modelos.</p>"
            "<p>Una entrada del catálogo <b>no</b> se añade a tu "
            "configuración hasta que pulses «Agregar a OpenCode», y las "
            "credenciales siguen gestionándose con /connect.</p>"
            f"<table>{table}</table>"
            "<p>Atajos: Ctrl+F buscar · Esc limpiar · Ctrl+O abrir · "
            "Ctrl+R recargar config · Ctrl+Shift+R refrescar catálogo · "
            "Ctrl+S guardar · Supr quitar el modelo registrado seleccionado.</p>"
            "</div>"
        )

    # ------------------------------------------------------------------
    # Detalle de modelo y de proveedor
    # ------------------------------------------------------------------

    def _resolve(self, pid: str, mid: str):
        """(modelo_catalogo, proveedor_catalogo, modelo_config, proveedor_config)."""
        providers = config_providers(self.data)
        pdata = providers.get(pid)
        pdata = pdata if isinstance(pdata, dict) else None
        mdata = None
        if pdata is not None:
            models = pdata.get("models")
            if isinstance(models, dict):
                candidate = models.get(mid)
                if isinstance(candidate, dict):
                    mdata = candidate
        provider = self.catalog.provider(pid)
        if provider is None and pdata is not None:
            provider = provider_from_config(pid, pdata)
        model = self.catalog.model(pid, mid)
        if model is None and mdata is not None:
            model = provider_from_config(pid, pdata).models.get(mid)
        return model, provider, mdata, pdata

    # ------------------------------------------------------------------
    # Dónde vive cada entrada
    #
    # El árbol muestra catálogo ∪ archivo abierto. Cuando una entrada no está
    # en el archivo abierto hay que poder explicar por qué, y si además está en
    # OTRO opencode.json, nombrar ese archivo: es lo que permite al usuario ir
    # a borrarlo. Solo lectura de opencode.json; auth.json no se mira nunca.
    # ------------------------------------------------------------------

    def other_config_files(self) -> list[Path]:
        """Archivos de configuración estándar que no son el que está abierto."""
        candidates = [global_config_path(), discover_config()]
        custom = os.environ.get("OPENCODE_CONFIG")
        if custom:
            candidates.append(Path(custom).expanduser())

        def key(path: Path) -> str:
            try:
                return str(Path(path).resolve())
            except OSError:
                return str(path)

        current = key(self.config_path)
        out, seen = [], {current}
        for candidate in candidates:
            name = key(candidate)
            if name in seen:
                continue
            seen.add(name)
            if candidate.is_file():
                out.append(candidate)
        return out

    def _refresh_foreign_providers(self) -> None:
        """Reindexa qué proveedores y modelos ajenos viven en otros archivos."""
        foreign: dict[str, list[str]] = {}
        for path in self.other_config_files():
            for pid, mid_list in self._providers_in_file(path).items():
                foreign.setdefault(pid, []).append(str(path))
                for mid in mid_list:
                    foreign.setdefault(full_id(pid, mid), []).append(str(path))
        self._foreign_providers = foreign

    @staticmethod
    def _providers_in_file(path: Path) -> dict[str, list[str]]:
        """pid → modelos registrados, o {} si el archivo no es legible."""
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        providers = data.get("provider")
        if not isinstance(providers, dict):
            providers = data.get("providers")
        if not isinstance(providers, dict):
            return {}
        out: dict[str, list[str]] = {}
        for pid, pdata in providers.items():
            models = pdata.get("models") if isinstance(pdata, dict) else None
            ids = [str(mid) for mid in models] if isinstance(models, dict) else []
            out[str(pid)] = ids
        return out

    def where_else(self, key: str) -> list[str]:
        """Rutas (otros opencode.json) donde está registrada esta entrada."""
        return self._foreign_providers.get(key, [])

    def entry_state(self, key: str, registered: bool) -> str:
        """De dónde sale cada entrada: 'here', 'elsewhere' o 'catalog'.

        Llamar «solo catálogo» a algo registrado en el opencode.json de un
        proyecto es mentira, y es justo lo que despistó con B.AI.
        """
        if registered:
            return "here"
        return "elsewhere" if self.where_else(key) else "catalog"

    def note_for(self, name: str, registered: bool, key: str) -> str:
        """Frase que explica por qué se puede —o no— actuar sobre la entrada."""
        return action_note(
            name, registered, str(self.config_path), self.where_else(key)
        )

    def show_model(self, pid: str, mid: str) -> None:
        if not pid or not mid:
            return
        model, provider, mdata, pdata = self._resolve(pid, mid)
        rows = model_detail_rows(model, provider, mdata, pdata)
        registered = mdata is not None
        title = str(
            (mdata or {}).get("name")
            or (model.name if model else mid)
        )
        self._current_entry = (pid, mid)
        self._current_kind = "model"
        self.workspace.setCurrentIndex(PAGE_DETAILS)
        self.header.set_count("")
        key = full_id(pid, mid)
        note = self.note_for(title, registered, key)
        badges = {
            "here": "Registrado en OpenCode",
            "elsewhere": "Registrado en otro archivo",
            "catalog": "Solo en el catálogo",
        }
        self.details.show_rows(
            title,
            key,
            badges[self.entry_state(key, registered)],
            rows + [("Desde esta ventana", note)],
            registered,
            "model",
            note,
        )

    def show_provider(self, pid: str) -> None:
        if not pid:
            return
        pdata = config_providers(self.data).get(pid)
        pdata = pdata if isinstance(pdata, dict) else None
        entry = self.catalog.provider(pid) or provider_from_config(pid, pdata)
        registered = pdata is not None
        state = self.entry_state(pid, registered)
        where = {
            "here": "Registrado",
            "elsewhere": "Registrado en otro archivo: "
                         + ", ".join(self.where_else(pid)),
            "catalog": "Solo en catálogo (no registrado)",
        }[state]
        rows = [
            ("Proveedor", entry.name),
            ("ID del proveedor", pid),
            ("API / Base URL", config_base_url(pdata) or entry.api or "Desconocida"),
            ("Protocolo de API", entry.protocol),
            ("Paquete del AI SDK", entry.npm or "Desconocido"),
            ("Variables de entorno", ", ".join(entry.env) or "Sin declaración"),
            (
                "Modelos en el catálogo",
                str(len(entry.models)) if entry.models else "Sin modelos conocidos",
            ),
            (
                "Modelos registrados",
                str(len(pdata.get("models") or {})) if registered else "0",
            ),
            ("Documentación", entry.doc or "No disponible"),
            (
                "Credenciales",
                "Se gestionan con /connect; esta herramienta no las lee "
                "ni las escribe.",
            ),
            (
                "Configuración en OpenCode",
                where,
            ),
        ]
        note = self.note_for(entry.name, registered, pid)
        rows.append(("Desde esta ventana", note))
        self._current_entry = (pid, "")
        self._current_kind = "provider"
        self.workspace.setCurrentIndex(PAGE_DETAILS)
        self.header.set_count("")
        self.details.show_rows(
            entry.name, pid,
            {"here": "Proveedor",
             "elsewhere": "Registrado en otro archivo",
             "catalog": "Solo catálogo"}[state],
            rows, registered, "provider", note,
        )

    # ------------------------------------------------------------------
    # Acciones del panel de detalle
    # ------------------------------------------------------------------

    def details_add(self):
        if self._current_kind == "provider":
            self.add_model(self._current_entry[0])
        else:
            self.register_current_model()

    def details_edit(self):
        if self._current_kind == "provider":
            self.edit_provider(self._current_entry[0])
        else:
            self.edit_model()

    def details_set_default(self, small: bool = False):
        if self._current_kind != "model":
            return
        pid, mid = self._current_entry
        pdata = config_providers(self.data).get(pid)
        models = pdata.get("models") if isinstance(pdata, dict) else None
        if not isinstance(models, dict) or mid not in models:
            QMessageBox.information(
                self, "No registrado",
                "Primero agrega el modelo a OpenCode para poder fijarlo."
            )
            return
        set_default_model(self.data, full_id(pid, mid), small=small)
        self.refresh()
        self.statusBar().showMessage(
            f"{'small_model' if small else 'model'} = {full_id(pid, mid)} "
            "(aún no guardado)."
        )

    def details_copy_id(self):
        pid, mid = self._current_entry
        text = full_id(pid, mid) if mid else pid
        if text:
            self._copy_to_clipboard(text)

    def details_copy_endpoint(self):
        pid = self._current_entry[0]
        entry = self.catalog.provider(pid)
        url = config_base_url(config_providers(self.data).get(pid)) or (
            entry.api if entry else ""
        )
        if not url:
            self.statusBar().showMessage(
                "Este proveedor no tiene endpoint conocido en el catálogo."
            )
            return
        self._copy_to_clipboard(url)

    def details_remove(self):
        pid, mid = self._current_entry
        if self._current_kind == "provider" or not mid:
            self.delete_provider(pid)
        else:
            self.delete_model(pid, mid)

    def _copy_to_clipboard(self, text: str) -> None:
        app = QApplication.instance()
        clipboard = app.clipboard() if app is not None and hasattr(app, "clipboard") else None
        if clipboard is None:
            self.statusBar().showMessage(f"Valor: {text}")
            return
        try:
            clipboard.setText(text)
        except Exception as exc:
            self.statusBar().showMessage(f"No se pudo copiar: {exc}")
            return
        self.statusBar().showMessage(f"Copiado al portapapeles: {text}")

    # ------------------------------------------------------------------
    # Modo global y LSP
    # ------------------------------------------------------------------

    def toggle_lsp(self, state):
        """Activa o desactiva la clave "lsp" de opencode.json."""
        enabled = state == Qt.CheckState.Checked.value
        if enabled:
            missing = missing_lsp_servers(lsp_languages(self.data))
            if missing:
                unique = sorted(set(missing))
                cmds = "\n".join(f"  • {s}  →  npm install -g {s}" for s in unique)
                QMessageBox.warning(
                    self,
                    "Servidor LSP no encontrado",
                    "LSP se guardará como activado, pero falta el servidor "
                    "del lenguaje en el PATH. OpenCode seguirá mostrando "
                    "LSP como desactivado hasta que lo instales:\n\n"
                    f"{cmds}\n\n"
                    "Después de instalar, reinicia OpenCode para que lo "
                    "detecte."
                )
            self.data["lsp"] = True
        else:
            self.data.pop("lsp", None)

        self.save_config(quiet=True)

    def toggle_global_mode(self, state):
        use_global = state == Qt.CheckState.Checked.value
        self.use_global = use_global
        self.settings.setValue("use_global", use_global)

        if use_global:
            self.config_path = global_config_path()
        else:
            self.config_path = discover_config()

        self.load_config()

    # ------------------------------------------------------------------
    # Alta / edición / baja de proveedores y modelos
    # ------------------------------------------------------------------

    def providers(self) -> dict:
        if not isinstance(self.data.get("provider"), dict):
            self.data["provider"] = {}
        return self.data["provider"]

    def register_current_model(self):
        """Alta explícita en opencode.json del modelo del catálogo seleccionado."""
        pid, mid = self._current_entry
        if not pid or not mid:
            return
        model = self.catalog.model(pid, mid)
        provider = self.catalog.provider(pid)
        if model is None:
            pdata = self.providers().get(pid)
            models = pdata.get("models") if isinstance(pdata, dict) else None
            if not isinstance(models, dict) or mid not in models:
                QMessageBox.warning(
                    self, "Sin datos del catálogo",
                    "Esta entrada no está en el catálogo. Puedes registrarla "
                    "a mano con «+ Modelo»."
                )
                return
            self.show_model(pid, mid)
            return
        ref = add_catalog_model_to_config(self.data, model, provider)
        self.refresh()
        self.tree.select_entry(pid, mid)
        self.show_model(pid, mid)
        self.statusBar().showMessage(
            f"{ref} agregado a opencode.json (aún no guardado). "
            "La API key se introduce con /connect."
        )

    def add_provider(self):
        dlg = ProviderDialog(self, existing_ids=self.providers().keys())
        if dlg.exec() != ACCEPTED:
            return
        spec = dlg.get_spec()
        errors = dlg.errors_for(spec)
        if errors:
            QMessageBox.warning(
                self, "Validación", "\n".join(errors)
            )
            return
        pid = add_provider_to_config(self.data, spec)
        self.refresh()
        self.tree.select_entry(pid)
        self.show_provider(pid)
        self.statusBar().showMessage(
            f"Proveedor «{pid}» añadido (aún no guardado). "
            "La API key se introduce con /connect."
        )

    def edit_provider(self, pid: str = ""):
        pid = pid or (self._current_entry[0] if self._current_kind == "provider" else "")
        providers = self.providers()
        if not pid or pid not in providers:
            QMessageBox.information(
                self, "Sin proveedor registrado",
                "Selecciona en el árbol un proveedor ya registrado para "
                "editarlo, o usa «+ Proveedor» para crear uno."
            )
            return
        dlg = ProviderDialog(
            self, pid, providers[pid], existing_ids=providers.keys()
        )
        if dlg.exec() != ACCEPTED:
            return
        add_provider_to_config(self.data, dlg.get_spec())
        self.refresh()
        self.show_provider(pid)
        self.statusBar().showMessage("Proveedor actualizado (aún no guardado).")

    def add_model(self, pid: str = ""):
        pid = pid or self._current_entry[0]
        providers = self.providers()
        if not pid or pid not in providers:
            QMessageBox.information(
                self, "Sin proveedor registrado",
                "Selecciona un proveedor registrado en el árbol para "
                "agregarle un modelo."
            )
            return
        pdata = providers[pid]
        if not isinstance(pdata, dict):
            return
        models = pdata.get("models")
        if not isinstance(models, dict):
            pdata["models"] = {}
            models = pdata["models"]

        dlg = ModelDialog(self, existing_ids=models.keys())
        if dlg.exec() != ACCEPTED:
            return
        model_id, name, modelid, limit = dlg.get_data()
        if model_id in models:
            QMessageBox.warning(
                self, "ID duplicado", f"Ya existe el modelo:\n{model_id}"
            )
            return
        model_data = {"name": name}
        if modelid:
            model_data["modelID"] = modelid
        if limit:
            model_data["limit"] = limit
        models[model_id] = model_data
        self.refresh()
        self.tree.select_entry(pid, model_id)
        self.show_model(pid, model_id)

    def edit_model(self):
        pid, mid = self._current_entry
        providers = self.providers()
        pdata = providers.get(pid) if pid else None
        models = pdata.get("models") if isinstance(pdata, dict) else None
        if not isinstance(models, dict) or mid not in models:
            QMessageBox.information(
                self, "Sin modelo registrado",
                "Selecciona un modelo registrado (✓ en el árbol) para "
                "editarlo."
            )
            return
        old_data = models[mid]

        dlg = ModelDialog(
            self, model_id=mid, model_data=old_data, existing_ids=models.keys()
        )
        if dlg.exec() != ACCEPTED:
            return
        new_id, name, modelid, limit = dlg.get_data()
        if new_id != mid and new_id in models:
            QMessageBox.warning(
                self, "ID duplicado",
                f"Ya existe otro modelo con el ID:\n{new_id}",
            )
            return

        # Conserva cualquier propiedad adicional (cost, options, variants…).
        new_data = deepcopy(old_data) if isinstance(old_data, dict) else {}
        new_data["name"] = name
        if modelid:
            new_data["modelID"] = modelid
        else:
            new_data.pop("modelID", None)
        merged_limit = {**(new_data.get("limit") or {}), **limit}
        if merged_limit:
            new_data["limit"] = merged_limit
        else:
            new_data.pop("limit", None)

        if new_id != mid:
            models[new_id] = new_data
            del models[mid]
            self.update_default_references(pid, mid, new_id)

        self.refresh()
        self.tree.select_entry(pid, new_id)
        self.show_model(pid, new_id)

    def update_default_references(self, pid, old_id, new_id):
        old_full = f"{pid}/{old_id}"
        new_full = f"{pid}/{new_id}"
        if self.data.get("model") == old_full:
            self.data["model"] = new_full
        if self.data.get("small_model") == old_full:
            self.data["small_model"] = new_full

    def _not_here_message(self, label: str, key: str) -> str:
        """Qué decir cuando piden borrar algo que no está en el archivo abierto.

        Por teclado (Supr) no hay botón gris que frene al usuario: el mensaje
        tiene que explicar lo mismo que el tooltip y decir dónde sí está.
        """
        elsewhere = self.where_else(key)
        if elsewhere:
            return (
                f"«{label}» no está en {self.config_path}, pero sí en "
                + ", ".join(elsewhere)
                + ". Esta ventana no lo borra de ahí: ábrelo con «Abrir…» o "
                  "cambia de modo con «Modo global»."
            )
        return (
            f"«{label}» es solo una fila del catálogo de Models.dev: en "
            f"{self.config_path} no hay nada que eliminar."
        )

    def delete_model(self, pid: str = "", mid: str = ""):
        current_pid, current_mid = self._current_entry
        pid = pid or current_pid
        mid = mid or current_mid
        if not pid or not mid:
            return
        pdata = self.providers().get(pid)
        models = pdata.get("models") if isinstance(pdata, dict) else None
        if not isinstance(models, dict) or mid not in models:
            self.statusBar().showMessage(
                self._not_here_message(full_id(pid, mid), full_id(pid, mid))
            )
            return
        name = model_display_name(mid, models[mid])

        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar este modelo de opencode.json?\n\n"
            f"Nombre: {name}\n"
            f"ID: {mid}\n\n"
            "La credencial de /connect NO será tocada y el modelo seguirá "
            "disponible en el catálogo.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        remove_model_from_config(self.data, pid, mid)
        self._current_entry = (pid, "")
        self.refresh()
        self.show_provider(pid)
        self.statusBar().showMessage(
            f"{pid}/{mid} quitado de opencode.json (aún no guardado)."
        )

    def delete_provider(self, pid: str) -> None:
        if not pid:
            return
        providers = self.providers()
        if pid not in providers:
            self.statusBar().showMessage(self._not_here_message(pid, pid))
            return
        pdata = providers[pid]
        count = len(pdata.get("models") or {}) if isinstance(pdata, dict) else 0
        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar el proveedor «{pid}» y sus {count} modelos de "
            "opencode.json?\n\nLa credencial de /connect NO será tocada.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        remove_provider_from_config(self.data, pid)
        self._current_entry = ("", "")
        self.refresh()
        self.show_overview()
        self.statusBar().showMessage(
            f"Proveedor «{pid}» quitado de opencode.json (aún no guardado). "
            "Si sigue en el árbol es porque existe en el catálogo: pulsa "
            "«Guardar» para escribir el archivo."
        )

    # ------------------------------------------------------------------
    # Carga, refresco y guardado de la configuración
    # ------------------------------------------------------------------

    def load_config(self):
        path = self.config_path

        if not path.exists():
            # Crear una configuración inicial solo después de confirmación.
            reply = QMessageBox.question(
                self,
                "Archivo no encontrado",
                f"No existe:\n{path}\n\n"
                "¿Quieres crear un opencode.json básico?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.data = {"$schema": SCHEMA_URL, "provider": {}}
                self._file_fingerprint = None
                self._mark_saved()
                self._refresh_foreign_providers()
                self.refresh()
            else:
                self.statusBar().showMessage("Archivo no encontrado.")
            return

        try:
            with path.open("r", encoding="utf-8") as handle:
                self.data = json.load(handle)
        except json.JSONDecodeError as e:
            QMessageBox.critical(
                self, "JSON inválido", f"No se pudo leer {path}.\n\nError:\n{e}"
            )
            return
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo abrir el archivo:\n{e}"
            )
            return

        if not isinstance(self.data, dict):
            QMessageBox.critical(
                self, "Configuración inválida",
                "El contenido de opencode.json debe ser un objeto JSON."
            )
            return

        self._file_fingerprint = file_fingerprint(path)
        self._refresh_foreign_providers()
        self._sync_checkboxes()

        migrated = False
        if "providers" in self.data and "provider" not in self.data:
            self.data["provider"] = self.data.pop("providers")
            migrated = True
        elif "providers" in self.data and "provider" in self.data:
            # Ambas existen: fusiona sin sobrescribir lo ya presente en
            # "provider" y elimina la clave antigua.
            providers_old = self.data["providers"]
            if isinstance(providers_old, dict):
                for pid, pdata in providers_old.items():
                    self.data["provider"].setdefault(pid, pdata)
            del self.data["providers"]
            migrated = True

        if migrated:
            QMessageBox.information(
                self,
                "Migración de configuración",
                "Se detectó la clave 'providers' y se migró a 'provider' "
                "(formato estable de OpenCode).\n\n"
                "Si usas una versión antigua de OpenCode, revisa el archivo "
                "antes de continuar."
            )

        self._mark_saved()
        self.refresh()
        self.statusBar().showMessage(f"Cargado: {path}")

    def _snapshot(self) -> str:
        return json.dumps(self.data, sort_keys=True, ensure_ascii=False)

    def _mark_saved(self) -> None:
        """Punto de comparación para «cambios sin guardar»."""
        self._saved_json = self._snapshot()

    def _is_dirty(self) -> bool:
        if self._saved_json is None:
            return False
        return self._snapshot() != self._saved_json

    def _update_save_button(self) -> None:
        """Mantiene visible que hay cambios pendientes de escribir.

        Todos los mandos que modifican la configuración son en memoria: sin
        este indicador el usuario pulsa «Quitar proveedor», ve que el árbol
        sigue igual (el proveedor viene del catálogo) y cree que no funcionó.
        """
        dirty = self._is_dirty()
        self.save_btn.setText("Guardar ●" if dirty else "Guardar")
        self.save_btn.setToolTip(
            "Hay cambios sin escribir en opencode.json (Ctrl+S)."
            if dirty
            else "Valida, respalda y guarda opencode.json (Ctrl+S)."
        )

    def refresh(self):
        """Vuelve a pintar la ventana a partir de self.data y del catálogo."""
        size, mtime = file_info(self.config_path)
        self.header.set_path(
            f"{self.config_path} · {size} · {mtime} · "
            f"{'modo global' if self.use_global else 'modo repositorio'}"
        )
        self.update_tree()
        self._update_save_button()

        pid, mid = self._current_entry
        if mid:
            self.show_model(pid, mid)
        elif pid:
            self.show_provider(pid)
        else:
            self.update_view()

    def save_config(self, quiet: bool = False) -> bool:
        """Valida, respalda y escribe opencode.json de forma atómica."""
        errors = validate_config(self.data)
        if errors:
            QMessageBox.critical(
                self, "Configuración inválida",
                "No se guardó. Revisa:\n\n• " + "\n• ".join(errors),
            )
            self.statusBar().showMessage(
                "Sin guardar: la configuración no es válida."
            )
            return False

        try:
            json_text = json.dumps(self.data, indent=2, ensure_ascii=False)
            json.loads(json_text)
        except Exception as e:
            QMessageBox.critical(
                self, "JSON inválido",
                f"No se puede guardar la configuración:\n{e}",
            )
            return False

        path = self.config_path
        previous = getattr(self, "_file_fingerprint", None)
        current = file_fingerprint(path)
        if previous is not None and current is not None and previous != current:
            reply = QMessageBox.question(
                self,
                "El archivo cambió fuera de esta ventana",
                f"{path}\n\nfue modificado después de cargarlo (por "
                "OpenCode, un editor o tú mismo).\n\n"
                "¿Sobrescribirlo con la versión de esta ventana?\n"
                "«No» deja el archivo externo intacto y no guarda nada.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.statusBar().showMessage(
                    "Sin guardar: se conservó el archivo externo. "
                    "Recarga con Ctrl+R para merges manuales."
                )
                return False

        if path.exists():
            try:
                shutil.copy2(path, path.with_suffix(path.suffix + ".backup"))
            except OSError:
                pass
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            try:
                backup_dir = path.parent / "opencode-backups"
                backup_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, backup_dir / f"{path.stem}_{stamp}.backup.json")
            except OSError:
                pass

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as handle:
                handle.write(json_text)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", f"No se pudo guardar:\n{e}")
            return False

        self._file_fingerprint = file_fingerprint(path)
        self._mark_saved()
        self.refresh()
        if quiet:
            self.statusBar().showMessage(f"Guardado: {path}")
            return True

        QMessageBox.information(
            self,
            "Guardado",
            "opencode.json se guardó correctamente.\n\n"
            "La API key almacenada por /connect no fue modificada.",
        )
        return True

    def create_backup(self):
        if not self.config_path.exists():
            QMessageBox.warning(
                self, "Sin archivo", "No existe un archivo para respaldar."
            )
            return

        backup_dir = self.config_path.parent / "opencode-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup = backup_dir / f"{self.config_path.stem}_{timestamp}.json"

        try:
            shutil.copy2(self.config_path, backup)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo crear la copia:\n{e}")
            return

        QMessageBox.information(
            self, "Copia creada", f"Backup guardado en:\n\n{backup}"
        )

    def show_preview(self):
        PreviewDialog(
            self, data=self.data, path_note=str(self.config_path)
        ).exec()

    def open_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Abrir configuración de OpenCode",
            str(self.config_path.parent),
            "OpenCode JSON (opencode.json);;JSON (*.json);;Todos (*)",
        )
        if not path:
            return
        self.config_path = Path(path)
        self.load_config()

    def closeEvent(self, event):
        """Guarda tamaño, posición y anchos del divisor para la próxima sesión."""
        if self._is_dirty():
            reply = QMessageBox.question(
                self,
                "Cambios sin guardar",
                "opencode.json todavía no contiene los cambios de esta "
                "ventana.\n\n¿Salir sin guardar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.settings.setValue("geometry", self.saveGeometry())
        splitter = getattr(self, "splitter", None)
        if splitter is not None:
            try:
                self.settings.setValue("splitter_sizes", list(splitter.sizes()))
            except Exception:
                pass
        event.accept()
