"""Paneles reutilizables de la interfaz.

Diseño:
  - workspace central (resultados / detalle / resumen) a la IZQUIERDA;
  - árbol de proveedores estrecho a la DERECHA, plegado por defecto,
    hijos cargados de forma perezosa;
  - la búsqueda opera sobre los DATOS del catálogo, nunca sobre la
    visibilidad del árbol: un proveedor plegado coincide igual.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QScrollArea, QSizePolicy, QToolButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
)

from omm.search import (
    PROTOCOL_ANY, PROTOCOL_OTHER, SCOPE_ALL, SCOPE_CONFIGURED,
    SCOPE_UNCONFIGURED, SORT_CONTEXT, SORT_NAME, SORT_PRICE, SORT_PROVIDER,
    Filters,
)
from omm.theme import LIGHT

# Roles de datos en el árbol.
ROLE_KIND = Qt.ItemDataRole.UserRole
ROLE_PID = Qt.ItemDataRole.UserRole + 1
ROLE_MID = Qt.ItemDataRole.UserRole + 2
ROLE_CONFIGURED = Qt.ItemDataRole.UserRole + 3

KIND_PROVIDER = "provider"
KIND_MODEL = "model"

MAX_VISIBLE_RESULTS = 300


class ProviderTreePanel(QTreeWidget):
    """Árbol estrecho de la derecha: proveedor → modelos.

    Señales:
        model_selected(pid, mid)
        provider_selected(pid)
    """

    model_selected = pyqtSignal(str, str)
    provider_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("providerTree")
        self.setHeaderHidden(True)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.setIndentation(14)
        self.setMinimumWidth(210)
        self.setMaximumWidth(560)
        self.setSortingEnabled(False)
        self.itemClicked.connect(self._on_clicked)
        self.itemExpanded.connect(self._load_children)
        self._expanded_ids: set[str] = set()
        self._loaded_ids: set[str] = set()
        self._rows: list[dict] = []
        self._configured_brush = QBrush(QColor(LIGHT.success))

    def set_configured_color(self, hex_color: str) -> None:
        """Tiñe los modelos registrados con el verde del tema activo.

        Hay que repintar los hijos ya creados: el árbol carga los modelos bajo
        demanda y cambiar de tema no reconstruye nada.
        """
        self._configured_brush = QBrush(QColor(hex_color))
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            for j in range(item.childCount()):
                child = item.child(j)
                if child.data(0, ROLE_CONFIGURED):
                    child.setForeground(0, self._configured_brush)

    # -- datos ------------------------------------------------------------
    def set_rows(self, rows: list[dict]) -> None:
        """Reconstruye el árbol (siempre con los hijos PLEGADOS por defecto)."""
        self._rows = rows
        previous = set(self._expanded_ids)
        self._loaded_ids.clear()
        self.setUpdatesEnabled(False)
        self.clear()
        for row in rows:
            label = self._provider_label(row)
            item = QTreeWidgetItem([label])
            item.setData(0, ROLE_KIND, KIND_PROVIDER)
            item.setData(0, ROLE_PID, row["id"])
            item.setData(0, ROLE_MID, "")
            tip = (
                f"ID: {row['id']}\n"
                f"Protocolo: {row['protocol']}\n"
                f"SDK: {row['npm'] or '—'}\n"
                f"Endpoint: {row['base_url'] or '—'}\n"
                f"Modelos: {row['count']}"
            )
            if row["configured"]:
                tip += "\nRegistrado en opencode.json"
            item.setToolTip(0, tip)
            if row["configured"]:
                f = item.font(0)
                f.setBold(True)
                item.setFont(0, f)
            # Placeholder perezoso: los hijos se crean al expandir.
            QTreeWidgetItem(item)
            self.addTopLevelItem(item)
        self.setUpdatesEnabled(True)
        # Restaura expansiones previas tras reconstrucciones (p. ej. guardar).
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            pid = item.data(0, ROLE_PID)
            if pid in previous:
                self._expanded_ids.add(pid)
                item.setExpanded(True)

    @staticmethod
    def _provider_label(row: dict) -> str:
        mark = "● " if row["configured"] else ""
        count = row["count"]
        return f"{mark}{row['name']}  ({count})"

    # -- expansión perezosa -------------------------------------------------
    def _load_children(self, item: QTreeWidgetItem) -> None:
        pid = item.data(0, ROLE_PID)
        if item.data(0, ROLE_KIND) != KIND_PROVIDER or pid in self._loaded_ids:
            return
        row = next((r for r in self._rows if r["id"] == pid), None)
        if row is None:
            return
        self._loaded_ids.add(pid)
        self._expanded_ids.add(pid)
        item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        placeholders = item.takeChildren()
        for mrow in row["models"]:
            child = QTreeWidgetItem([self._model_label(mrow)])
            child.setData(0, ROLE_KIND, KIND_MODEL)
            child.setData(0, ROLE_PID, pid)
            child.setData(0, ROLE_MID, mrow["id"])
            tip = f"ID: {mrow['id']}"
            if mrow["configured"]:
                tip += "\nRegistrado en opencode.json"
            child.setToolTip(0, tip)
            if mrow["configured"]:
                child.setData(0, ROLE_CONFIGURED, True)
                child.setForeground(0, self._configured_brush)
            item.addChild(child)
        if row["count"]:
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        else:
            item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator
            )

    @staticmethod
    def _model_label(mrow: dict) -> str:
        mark = "✓ " if mrow["configured"] else ""
        return f"{mark}{mrow['name']}"

    def _on_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        kind = item.data(0, ROLE_KIND)
        pid = item.data(0, ROLE_PID)
        if kind == KIND_PROVIDER:
            expands = not item.isExpanded()
            if not expands:
                self._expanded_ids.discard(pid)
            item.setExpanded(expands)
            self.provider_selected.emit(pid)
        elif kind == KIND_MODEL:
            self.model_selected.emit(pid, item.data(0, ROLE_MID))

    def select_entry(self, pid: str, mid: str = "") -> None:
        """Selecciona un proveedor o modelo; expande si es necesario."""
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            if top.data(0, ROLE_PID) != pid:
                continue
            if not mid:
                self.setCurrentItem(top)
                return
            if top.data(0, ROLE_PID) not in self._loaded_ids:
                top.setExpanded(True)  # dispara _load_children
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, ROLE_MID) == mid:
                    self.setCurrentItem(child)
                    self.scrollToItem(child)
                    return
            self.setCurrentItem(top)
            return


class SearchResultsPanel(QListWidget):
    """Resultados de búsqueda; la vista se recorta, el conteo no."""

    model_selected = pyqtSignal(str, str)
    open_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.ListMode)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setUniformItemSizes(True)
        self.itemSelectionChanged.connect(self._forward_selection)
        self.itemActivated.connect(self._on_activated)
        # Aviso de lista vacía: hijo del viewport, porque QListView no
        # expone placeholderText en PyQt6.
        self._empty = QLabel(
            "Sin coincidencias con esta búsqueda y filtros.", self.viewport()
        )
        self._empty.setObjectName("emptyState")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setVisible(False)

    def show_results(self, models, cap: int = MAX_VISIBLE_RESULTS) -> None:
        self.clear()
        for model in models[:cap]:
            item = QListWidgetItem(self._label(model))
            item.setData(ROLE_PID, model.provider_id)
            item.setData(ROLE_MID, model.id)
            item.setToolTip(
                f"{model.provider_name} · {model.protocol}\n"
                f"ID: {model.full_id}"
            )
            self.addItem(item)
        if models:
            self.setCurrentRow(0)
        self._empty.setVisible(not models)
        self._place_empty()

    def _place_empty(self) -> None:
        view = self.viewport()
        self._empty.setGeometry(0, 0, view.width(), view.height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_empty()

    @staticmethod
    def _label(model) -> str:
        bits = [f"{model.name}", f"· {model.provider_name}"]
        if model.context:
            bits.append(f"· ctx {model.context:,}".replace(",", "."))
        if model.reasoning:
            bits.append("· R")
        if model.tool_call:
            bits.append("· T")
        return " ".join(bits)

    def _forward_selection(self) -> None:
        item = self.currentItem()
        if item is not None:
            self.model_selected.emit(item.data(ROLE_PID), item.data(ROLE_MID))

    def _on_activated(self, item: QListWidgetItem) -> None:
        self.open_requested.emit(item.data(ROLE_PID), item.data(ROLE_MID))

    def open_current(self) -> None:
        item = self.currentItem()
        if item is not None:
            self.open_requested.emit(item.data(ROLE_PID), item.data(ROLE_MID))

    def keyPressEvent(self, event) -> None:
        """Enter abre la ficha de la fila resaltada (el doble clic ya funciona)."""
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.open_current()
            return
        super().keyPressEvent(event)


class FilterPanel(QWidget):
    """Panel compacto y plegable de filtros (chips + combos de ámbito)."""

    filters_changed = pyqtSignal()
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("filterPanel")
        # Sin este atributo Qt pinta el fondo con la paleta e ignora el
        # `background` de la hoja de estilos: un QWidget liso no es un QFrame.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)

        row_prov = QHBoxLayout()
        row_prov.setSpacing(8)
        row_prov.addWidget(QLabel("Proveedores:"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Todos", SCOPE_ALL)
        self.scope_combo.addItem("Registrados en OpenCode", SCOPE_CONFIGURED)
        self.scope_combo.addItem("Sin registrar", SCOPE_UNCONFIGURED)
        self.scope_combo.setToolTip("Mostrar solo proveedores registrados (o no).")
        self.scope_combo.currentIndexChanged.connect(self.filters_changed)
        row_prov.addWidget(self.scope_combo)
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItem("Cualquier protocolo", PROTOCOL_ANY)
        self.protocol_combo.addItem("OpenAI-compatible", "openai-compatible")
        self.protocol_combo.addItem("OpenAI", "openai")
        self.protocol_combo.addItem("Anthropic", "anthropic")
        self.protocol_combo.addItem("Google", "google")
        self.protocol_combo.addItem("Otros", PROTOCOL_OTHER)
        self.protocol_combo.setToolTip(
            "«Otros» incluye los protocolos no listados (Bedrock, Azure…)."
        )
        self.protocol_combo.currentIndexChanged.connect(self.filters_changed)
        row_prov.addWidget(self.protocol_combo)
        self.local_check = QCheckBox("Locales")
        self.local_check.setToolTip(
            "Endpoints de máquina local (Ollama, LM Studio, llama.cpp…)."
        )
        self.local_check.toggled.connect(self.filters_changed)
        row_prov.addWidget(self.local_check)
        row_prov.addStretch()
        root.addLayout(row_prov)

        row_model = QHBoxLayout()
        row_model.setSpacing(6)
        row_model.addWidget(QLabel("Modelos:"))
        self._chips: list[QToolButton] = []
        chip_defs = (
            ("free", "Gratis"), ("paid", "De pago"),
            ("free_tier", "Nivel gratis"), ("coding", "Código"),
            ("reasoning", "Razonamiento"), ("vision", "Visión"),
            ("tools", "Tool calling"), ("multimodal", "Multimodal"),
            ("large_context", "Contexto ≥ 200k"),
        )
        for attr, label in chip_defs:
            chip = QToolButton()
            chip.setText(label)
            chip.setCheckable(True)
            chip.setToolTip(f"Filtro «{label}» combinable con los demás.")
            chip.toggled.connect(self.filters_changed)
            setattr(self, f"chip_{attr}", chip)
            self._chips.append(chip)
            row_model.addWidget(chip)
        row_model.addStretch()
        self.clear_btn = QPushButton("Limpiar filtros")
        self.clear_btn.setObjectName("ghost")
        self.clear_btn.clicked.connect(self._on_clear)
        row_model.addWidget(self.clear_btn)
        root.addLayout(row_model)

    def _on_clear(self) -> None:
        self.reset_controls()
        self.filters_changed.emit()
        self.clear_requested.emit()

    def current_filters(self, base: Filters) -> Filters:
        """Mezcla el estado del panel sobre una base de filtros."""
        return base.with_(
            scope=self.scope_combo.currentData() or SCOPE_ALL,
            protocol=self.protocol_combo.currentData() or PROTOCOL_ANY,
            local_only=self.local_check.isChecked(),
            free=self.chip_free.isChecked(),
            paid=self.chip_paid.isChecked(),
            free_tier=self.chip_free_tier.isChecked(),
            coding=self.chip_coding.isChecked(),
            reasoning=self.chip_reasoning.isChecked(),
            vision=self.chip_vision.isChecked(),
            tools=self.chip_tools.isChecked(),
            multimodal=self.chip_multimodal.isChecked(),
            large_context=self.chip_large_context.isChecked(),
        )

    def reset_controls(self) -> None:
        for chip in self._chips:
            chip.blockSignals(True)
            chip.setChecked(False)
            chip.blockSignals(False)
        self.scope_combo.blockSignals(True)
        self.protocol_combo.blockSignals(True)
        self.local_check.blockSignals(True)
        self.scope_combo.setCurrentIndex(0)
        self.protocol_combo.setCurrentIndex(0)
        self.local_check.setChecked(False)
        self.scope_combo.blockSignals(False)
        self.protocol_combo.blockSignals(False)
        self.local_check.blockSignals(False)


class DetailsPanel(QWidget):
    """Vista de detalle de un modelo o proveedor del catálogo."""

    add_requested = pyqtSignal()
    edit_requested = pyqtSignal()
    set_default_requested = pyqtSignal(bool)  # True → small_model
    copy_id_requested = pyqtSignal()
    copy_endpoint_requested = pyqtSignal()
    remove_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        head = QVBoxLayout()
        self.title = QLabel("")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        self.title.setFont(f)
        self.title.setWordWrap(True)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("pathLabel")
        mono = QFont("Monospace", 10)
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        self.subtitle.setFont(mono)
        self.subtitle.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.badge = QLabel("")
        self.badge.setStyleSheet("padding: 2px 8px; border-radius: 8px; font-size: 11px;")
        head.addWidget(self.title)
        head.addWidget(self.subtitle)
        head.addWidget(self.badge)
        root.addLayout(head)

        self.card = QFrame()
        self.card.setObjectName("card")
        self.grid = QVBoxLayout(self.card)
        self.grid.setContentsMargins(12, 10, 12, 10)
        self.grid.setSpacing(4)
        root.addWidget(self.card)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.add_btn = QPushButton("Agregar a OpenCode")
        self.add_btn.setObjectName("primary")
        self.add_btn.clicked.connect(self.add_requested)
        self.edit_btn = QPushButton("Editar configuración")
        self.edit_btn.clicked.connect(self.edit_requested)
        self.default_btn = QPushButton("Fijar como predeterminado")
        self.default_btn.clicked.connect(lambda: self.set_default_requested.emit(False))
        self.small_btn = QPushButton("Fijar como modelo ligero")
        self.small_btn.setToolTip("Escribe «small_model» en opencode.json.")
        self.small_btn.clicked.connect(lambda: self.set_default_requested.emit(True))
        self.copy_id_btn = QPushButton("Copiar ID")
        self.copy_id_btn.clicked.connect(self.copy_id_requested)
        self.copy_url_btn = QPushButton("Copiar endpoint")
        self.copy_url_btn.clicked.connect(self.copy_endpoint_requested)
        self.remove_btn = QPushButton("Quitar de OpenCode")
        self.remove_btn.setObjectName("danger")
        self.remove_btn.clicked.connect(self.remove_requested)
        for b in (
            self.add_btn, self.edit_btn, self.default_btn, self.small_btn,
            self.copy_id_btn, self.copy_url_btn, self.remove_btn,
        ):
            actions.addWidget(b)
        actions.addStretch()
        root.addLayout(actions)
        root.addStretch()

    # Etiquetas según el tipo de entrada: los siete botones existen siempre,
    # pero cambian de sentido (modelo registrado vs proveedor) para que
    # ninguno quede inactivo sin explicación.
    _MODE_LABELS = {
        "model": {
            "add": "Agregar a OpenCode",
            "edit": "Editar modelo",
            "default": "Fijar como predeterminado",
            "small": "Fijar como modelo ligero",
            "copy_id": "Copiar ID",
            "copy_url": "Copiar endpoint",
            "remove": "Quitar de OpenCode",
        },
        "provider": {
            "add": "Agregar modelo",
            "edit": "Editar proveedor",
            "default": "Fijar predeterminado",
            "small": "Fijar ligero",
            "copy_id": "Copiar ID del proveedor",
            "copy_url": "Copiar endpoint",
            "remove": "Quitar proveedor",
        },
    }

    @staticmethod
    def _clear_rows(layout) -> None:
        """Vacía el grid de la ficha por completo, incluyendo sub-layouts.

        Cada fila se añade con addLayout(), así que item.widget() del nivel
        exterior es siempre None: sin bajar un nivel, las etiquetas de la
        ficha anterior quedan hijas de la tarjeta y se pintan encima.
        setParent(None) las esconde al instante; deleteLater() no actuaría
        hasta la siguiente vuelta al bucle de eventos.
        """
        while layout.count():
            item = layout.takeAt(0)
            inner = item.layout()
            if inner is not None:
                DetailsPanel._clear_rows(inner)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def show_rows(self, title: str, subtitle: str, badge: str, rows,
                  registered: bool, kind: str = "model") -> None:
        labels = self._MODE_LABELS.get(kind, self._MODE_LABELS["model"])
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.badge.setText(badge)
        self._clear_rows(self.grid)
        for label, value in rows:
            row = QHBoxLayout()
            key = QLabel(label)
            key.setObjectName("mutedLabel")
            key.setMinimumWidth(180)
            val = QLabel(value)
            mono = QFont("Monospace", 10)
            mono.setStyleHint(QFont.StyleHint.TypeWriter)
            val.setFont(mono)
            val.setWordWrap(True)
            val.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(key)
            row.addWidget(val, 1)
            self.grid.addLayout(row)

        self.add_btn.setText(labels["add"])
        self.edit_btn.setText(labels["edit"])
        self.default_btn.setText(labels["default"])
        self.small_btn.setText(labels["small"])
        self.copy_id_btn.setText(labels["copy_id"])
        self.copy_url_btn.setText(labels["copy_url"])
        self.remove_btn.setText(labels["remove"])

        if kind == "provider":
            self.add_btn.setEnabled(True)
            self.add_btn.setToolTip(
                "Registrar un modelo a mano en este proveedor."
            )
            self.default_btn.setEnabled(False)
            self.default_btn.setToolTip(
                "Abre un modelo (doble clic en los resultados) para fijarlo."
            )
            self.small_btn.setEnabled(False)
            self.small_btn.setToolTip(self.default_btn.toolTip())
            self.edit_btn.setEnabled(registered)
            self.remove_btn.setEnabled(registered)
            # Un botón gris sin explicación parece un fallo: los proveedores
            # del árbol existen aunque no estén en opencode.json.
            why = (
                "Editar y quitar actúan sobre lo que hay en opencode.json."
                if registered
                else "Este proveedor no está en opencode.json: no hay nada "
                     "que editar ni quitar. En el árbol sigue visible porque "
                     "viene del catálogo de Models.dev."
            )
            self.edit_btn.setToolTip(why)
            self.remove_btn.setToolTip(why)
        else:
            self.add_btn.setEnabled(not registered)
            self.add_btn.setToolTip(
                "Registra este modelo en opencode.json (no toca credenciales)."
                if not registered else "Este modelo ya está registrado."
            )
            self.default_btn.setEnabled(registered)
            self.default_btn.setToolTip(
                "Escribe «model» en opencode.json."
                if registered else "Primero hay que registrarlo."
            )
            self.small_btn.setEnabled(registered)
            self.small_btn.setToolTip(
                "Escribe «small_model» en opencode.json (tareas rápidas)."
                if registered else "Primero hay que registrarlo."
            )
            self.edit_btn.setEnabled(registered)
            self.remove_btn.setEnabled(registered)

        has_endpoint = any(
            label == "API / Base URL" and value not in ("", "Desconocida")
            for label, value in rows
        )
        self.copy_url_btn.setEnabled(has_endpoint)
        if not has_endpoint:
            self.copy_url_btn.setToolTip(
                "El catálogo no conoce el endpoint de este proveedor."
            )


class OverviewPanel(QWidget):
    """Resumen inicial: estado de la config, catálogo y accesos rápidos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        self.title = QLabel("Resumen")
        f = QFont()
        f.setPointSize(14)
        f.setBold(True)
        self.title.setFont(f)
        root.addWidget(self.title)
        self.body = QLabel()
        self.body.setWordWrap(True)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        root.addWidget(self.body)
        root.addStretch()

    def show_summary(self, html: str) -> None:
        self.body.setText(html)


class HeaderBar(QWidget):
    """Cabecera: título, archivo de config, búsqueda, filtros y acciones."""

    search_changed = pyqtSignal(str)
    filters_toggled = pyqtSignal(bool)
    sort_changed = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("headerBar")
        # Ver FilterPanel: un QWidget liso necesita WA_StyledBackground para
        # que la hoja de estilos le pinte el fondo.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(8)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        self.row1 = row1
        title = QLabel("OpenCode API Manager")
        title.setObjectName("appTitle")
        row1.addWidget(title)
        self.path_label = QLabel("")
        self.path_label.setObjectName("pathLabel")
        self.path_label.setWordWrap(True)
        self.path_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        row1.addWidget(self.path_label, 1)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.row2 = row2
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("searchBox")
        self.search_edit.setPlaceholderText(
            "Buscar proveedores, modelos, endpoints, descripciones…  (Ctrl+F)"
        )
        self.search_edit.setClearButtonEnabled(True)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(160)
        self._debounce.timeout.connect(
            lambda: self.search_changed.emit(self.search_edit.text())
        )
        self.search_edit.textChanged.connect(self._debounce.start)
        self.search_edit.returnPressed.connect(
            lambda: self.search_changed.emit(self.search_edit.text())
        )
        row2.addWidget(self.search_edit, 1)
        self.filters_btn = QToolButton()
        self.filters_btn.setText("Filtros")
        self.filters_btn.setCheckable(True)
        self.filters_btn.setToolTip("Mostrar u ocultar el panel de filtros.")
        self.filters_btn.toggled.connect(self.filters_toggled)
        row2.addWidget(self.filters_btn)
        self.sort_combo = QComboBox()
        for label, data in (
            ("A → Z", SORT_NAME),
            ("Proveedor", SORT_PROVIDER),
            ("Contexto", SORT_CONTEXT),
            ("Precio", SORT_PRICE),
        ):
            self.sort_combo.addItem(label, data)
        self.sort_combo.setToolTip("Criterio de orden de los resultados.")
        self.sort_combo.currentIndexChanged.connect(self._emit_sort)
        row2.addWidget(self.sort_combo)
        self.dir_btn = QToolButton()
        self.dir_btn.setText("↑↓")
        self.dir_btn.setCheckable(True)
        self.dir_btn.setToolTip("Invertir el orden.")
        self.dir_btn.toggled.connect(lambda _on: self._emit_sort())
        row2.addWidget(self.dir_btn)
        self.count_label = QLabel("")
        self.count_label.setObjectName("mutedLabel")
        row2.addWidget(self.count_label)
        root.addLayout(row2)

    def _emit_sort(self) -> None:
        self.sort_changed.emit(
            self.sort_combo.currentData() or SORT_NAME, self.dir_btn.isChecked()
        )

    def set_path(self, text: str) -> None:
        self.path_label.setText(text)

    def set_count(self, text: str) -> None:
        self.count_label.setText(text)
