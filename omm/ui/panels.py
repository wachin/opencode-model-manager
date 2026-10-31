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

from omm.i18n import LANGUAGES, format_int, get_language, tr
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
        self._notes: dict[str, str] = {}
        self._config_path = ""
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
    def set_rows(self, rows: list[dict], notes: dict[str, str] | None = None,
                 config_path: str = "") -> None:
        """Reconstruye el árbol (siempre con los hijos PLEGADOS por defecto).

        notes: pid → frase que explica por qué la entrada se puede editar o no
        desde el archivo abierto. Va en el tooltip de la fila: el aviso de
        «esto no se borra de aquí» tiene que verse sin pulsar nada.
        """
        self._rows = rows
        self._notes = dict(notes or {})
        self._config_path = config_path
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
            item.setToolTip(0, self._provider_tip(row))
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

    def _provider_tip(self, row: dict) -> str:
        tip = (
            f"ID: {row['id']}\n"
            f"{tr('Protocol', es='Protocolo')}: {row['protocol']}\n"
            f"SDK: {row['npm'] or '—'}\n"
            f"{tr('Endpoint', es='Endpoint')}: {row['base_url'] or '—'}\n"
            f"{tr('Models', es='Modelos')}: {row['count']}"
        )
        note = self._notes.get(row["id"], "")
        if row["configured"]:
            tip += "\n" + tr(
                "Registered in {path}", es="Registrado en {path}"
            ).format(path=self._config_path or "opencode.json")
        if note:
            tip += "\n" + note
        return tip

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
            note = self._notes.get(f"{pid}/{mrow['id']}", "")
            if mrow["configured"]:
                tip += "\n" + tr(
                    "Registered in {path}", es="Registrado en {path}"
                ).format(path=self._config_path or "opencode.json")
            if note:
                tip += "\n" + note
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
            tr("No matches for this search and filters.",
               es="Sin coincidencias con esta búsqueda y filtros."),
            self.viewport(),
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
            bits.append(f"· ctx {format_int(model.context)}")
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
        self.providers_label = QLabel()
        row_prov.addWidget(self.providers_label)
        self.scope_combo = QComboBox()
        self.scope_combo.currentIndexChanged.connect(self.filters_changed)
        row_prov.addWidget(self.scope_combo)
        self.protocol_combo = QComboBox()
        self.protocol_combo.currentIndexChanged.connect(self.filters_changed)
        row_prov.addWidget(self.protocol_combo)
        self.local_check = QCheckBox()
        self.local_check.toggled.connect(self.filters_changed)
        row_prov.addWidget(self.local_check)
        row_prov.addStretch()
        root.addLayout(row_prov)

        row_model = QHBoxLayout()
        row_model.setSpacing(6)
        self.models_label = QLabel()
        row_model.addWidget(self.models_label)
        self._chips: list[QToolButton] = []
        for attr, _en, _es in self.CHIP_DEFS:
            chip = QToolButton()
            chip.setCheckable(True)
            chip.toggled.connect(self.filters_changed)
            setattr(self, f"chip_{attr}", chip)
            self._chips.append(chip)
            row_model.addWidget(chip)
        row_model.addStretch()
        self.clear_btn = QPushButton()
        self.clear_btn.setObjectName("ghost")
        self.clear_btn.clicked.connect(self._on_clear)
        row_model.addWidget(self.clear_btn)
        root.addLayout(row_model)
        self.retranslate()

    # Definiciones con su traducción al lado: retranslate() las reaplica al
    # cambiar de idioma sin reconstruir la ventana ni perder los filtros.
    CHIP_DEFS = (
        ("free", "Free", "Gratis"),
        ("paid", "Paid", "De pago"),
        ("free_tier", "Free tier", "Nivel gratis"),
        ("coding", "Coding", "Código"),
        ("reasoning", "Reasoning", "Razonamiento"),
        ("vision", "Vision", "Visión"),
        ("tools", "Tool calling", "Tool calling"),
        ("multimodal", "Multimodal", "Multimodal"),
        ("large_context", "Context ≥ 200k", "Contexto ≥ 200k"),
    )
    SCOPE_ITEMS = (
        (SCOPE_ALL, "All", "Todos"),
        (SCOPE_CONFIGURED, "Registered in OpenCode",
         "Registrados en OpenCode"),
        (SCOPE_UNCONFIGURED, "Unregistered", "Sin registrar"),
    )
    PROTOCOL_ITEMS = (
        (PROTOCOL_ANY, "Any protocol", "Cualquier protocolo"),
        ("openai-compatible", "OpenAI-compatible", "OpenAI-compatible"),
        ("openai", "OpenAI", "OpenAI"),
        ("anthropic", "Anthropic", "Anthropic"),
        ("google", "Google", "Google"),
        (PROTOCOL_OTHER, "Other", "Otros"),
    )

    def retranslate(self) -> None:
        self.providers_label.setText(tr("Providers:", es="Proveedores:"))
        self.models_label.setText(tr("Models:", es="Modelos:"))
        self.local_check.setText(tr("Local", es="Locales"))
        self.local_check.setToolTip(tr(
            "Endpoints on this machine (Ollama, LM Studio, llama.cpp…).",
            es="Endpoints de máquina local (Ollama, LM Studio, llama.cpp…).",
        ))
        self.scope_combo.blockSignals(True)
        self.protocol_combo.blockSignals(True)
        self._fill(self.scope_combo, self.SCOPE_ITEMS)
        self._fill(self.protocol_combo, self.PROTOCOL_ITEMS)
        self.scope_combo.blockSignals(False)
        self.protocol_combo.blockSignals(False)
        self.scope_combo.setToolTip(tr(
            "Show only registered providers (or only unregistered ones).",
            es="Mostrar solo proveedores registrados (o no).",
        ))
        self.protocol_combo.setToolTip(tr(
            "“Other” includes protocols not listed here (Bedrock, Azure…).",
            es="«Otros» incluye los protocolos no listados (Bedrock, Azure…).",
        ))
        for chip, (attr, english, spanish) in zip(self._chips, self.CHIP_DEFS):
            label = tr(english, es=spanish)
            chip.setText(label)
            chip.setToolTip(tr(
                "Filter “{label}”, combinable with the rest.",
                es="Filtro «{label}» combinable con los demás.",
            ).format(label=label))
        self.clear_btn.setText(tr("Clear filters", es="Limpiar filtros"))

    @staticmethod
    def _fill(combo: QComboBox, items) -> None:
        """Reescribe los textos conservando datos e índice actual."""
        current = combo.currentData()
        if combo.count() != len(items):
            combo.clear()
            for data, _en, _es in items:
                combo.addItem("", data)
        for index, (_data, english, spanish) in enumerate(items):
            combo.setItemText(index, tr(english, es=spanish))
        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)

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
    probe_requested = pyqtSignal(bool)  # True → con la clave del entorno

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
        self.add_btn = QPushButton(tr("Add to OpenCode", es="Agregar a OpenCode"))
        self.add_btn.setObjectName("primary")
        self.add_btn.clicked.connect(self.add_requested)
        self.edit_btn = QPushButton(tr("Edit configuration", es="Editar configuración"))
        self.edit_btn.clicked.connect(self.edit_requested)
        self.default_btn = QPushButton(tr(
            "Set as default", es="Fijar como predeterminado"))
        self.default_btn.clicked.connect(lambda: self.set_default_requested.emit(False))
        self.small_btn = QPushButton(tr(
            "Set as small model", es="Fijar como modelo ligero"))
        self.small_btn.setToolTip(tr(
            "Writes “small_model” in opencode.json.",
            es="Escribe «small_model» en opencode.json."))
        self.small_btn.clicked.connect(lambda: self.set_default_requested.emit(True))
        self.copy_id_btn = QPushButton(tr("Copy ID", es="Copiar ID"))
        self.copy_id_btn.clicked.connect(self.copy_id_requested)
        self.copy_url_btn = QPushButton(tr("Copy endpoint", es="Copiar endpoint"))
        self.copy_url_btn.clicked.connect(self.copy_endpoint_requested)
        self.remove_btn = QPushButton(tr("Remove from OpenCode", es="Quitar de OpenCode"))
        self.remove_btn.setObjectName("danger")
        self.remove_btn.clicked.connect(self.remove_requested)
        for b in (
            self.add_btn, self.edit_btn, self.default_btn, self.small_btn,
            self.copy_id_btn, self.copy_url_btn, self.remove_btn,
        ):
            actions.addWidget(b)
        actions.addStretch()
        root.addLayout(actions)

        # La prueba de conexión va en su propia fila: son dos acciones y la
        # de arriba ya ocupa todo el ancho en pantallas estrechas.
        probe_row = QHBoxLayout()
        probe_row.setSpacing(8)
        self.probe_btn = QPushButton(tr("Test connection", es="Probar conexión"))
        self.probe_btn.clicked.connect(lambda: self.probe_requested.emit(False))
        self.probe_key_btn = QPushButton(tr(
            "Test with my key", es="Probar con mi clave"))
        self.probe_key_btn.clicked.connect(lambda: self.probe_requested.emit(True))
        probe_row.addWidget(self.probe_btn)
        probe_row.addWidget(self.probe_key_btn)
        probe_row.addStretch()
        root.addLayout(probe_row)
        self._probe_info: dict = {}
        self._probe_busy = False
        root.addStretch()

    # Etiquetas según el tipo de entrada: los siete botones existen siempre,
    # pero cambian de sentido (modelo registrado vs proveedor) para que
    # ninguno quede inactivo sin explicación.
    @staticmethod
    def _mode_labels(kind: str) -> dict[str, str]:
        labels = {
            "model": {
                "add": tr("Add to OpenCode", es="Agregar a OpenCode"),
                "edit": tr("Edit model", es="Editar modelo"),
                "default": tr("Set as default", es="Fijar como predeterminado"),
                "small": tr("Set as small model", es="Fijar como modelo ligero"),
                "copy_id": tr("Copy ID", es="Copiar ID"),
                "copy_url": tr("Copy endpoint", es="Copiar endpoint"),
                "remove": tr("Remove from OpenCode", es="Quitar de OpenCode"),
            },
            "provider": {
                "add": tr("Add model", es="Agregar modelo"),
                "edit": tr("Edit provider", es="Editar proveedor"),
                "default": tr("Set default", es="Fijar predeterminado"),
                "small": tr("Set small", es="Fijar ligero"),
                "copy_id": tr("Copy provider ID", es="Copiar ID del proveedor"),
                "copy_url": tr("Copy endpoint", es="Copiar endpoint"),
                "remove": tr("Remove provider", es="Quitar proveedor"),
            },
        }
        return labels.get(kind, labels["model"])

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
                  registered: bool, kind: str = "model",
                  action_note: str = "", probe: dict | None = None) -> None:
        self._kind = kind
        labels = self._mode_labels(kind)
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
            self.add_btn.setToolTip(tr(
                "Register a model by hand for this provider.",
                es="Registrar un modelo a mano en este proveedor.",
            ))
            self.default_btn.setEnabled(False)
            self.default_btn.setToolTip(tr(
                "Open a model (double-click in the results) to set it.",
                es="Abre un modelo (doble clic en los resultados) para fijarlo.",
            ))
            self.small_btn.setEnabled(False)
            self.small_btn.setToolTip(self.default_btn.toolTip())
            self.edit_btn.setEnabled(registered)
            self.remove_btn.setEnabled(registered)
            # Un botón gris sin explicación parece un fallo: los proveedores
            # del árbol existen aunque no estén en opencode.json.
            fallback = tr(
                "Edit and remove act on what is in opencode.json.",
                es="Editar y quitar actúan sobre lo que hay en opencode.json.",
            ) if registered else tr(
                "This provider is not in the opencode.json you are editing "
                "(look at the path in the header): there is nothing to edit "
                "or remove. It is still visible in the tree because it comes "
                "from the Models.dev catalog. If it is registered in another "
                "file —for example a project's opencode.json— open it with "
                "“Open…” or switch mode with “Global mode”.",
                es="Este proveedor no está en el opencode.json que estás "
                   "editando (mira la ruta de la cabecera): no hay nada que "
                   "editar ni quitar. En el árbol sigue visible porque "
                   "viene del catálogo de Models.dev. Si lo tienes "
                   "registrado en otro archivo —por ejemplo el "
                   "opencode.json de un proyecto— ábrelo con «Abrir…» o "
                   "cambia de modo con «Modo global».",
            )
            why = action_note or fallback
            self.edit_btn.setToolTip(why)
            self.remove_btn.setToolTip(why)
        else:
            self.add_btn.setEnabled(not registered)
            self.add_btn.setToolTip(
                tr("Registers this model in opencode.json (touches no credentials).",
                   es="Registra este modelo en opencode.json (no toca credenciales).")
                if not registered else tr(
                    "This model is already registered.",
                    es="Este modelo ya está registrado.")
            )
            self.default_btn.setEnabled(registered)
            self.default_btn.setToolTip(
                tr("Writes “model” in opencode.json.",
                   es="Escribe «model» en opencode.json.")
                if registered else tr("Register it first.",
                                      es="Primero hay que registrarlo.")
            )
            self.small_btn.setEnabled(registered)
            self.small_btn.setToolTip(
                tr("Writes “small_model” in opencode.json (quick tasks).",
                   es="Escribe «small_model» en opencode.json (tareas rápidas).")
                if registered else tr("Register it first.",
                                      es="Primero hay que registrarlo.")
            )
            self.edit_btn.setEnabled(registered)
            self.remove_btn.setEnabled(registered)
            why = action_note or (
                tr("Edit and remove act on what is in opencode.json.",
                   es="Editar y quitar actúan sobre lo que hay en opencode.json.")
                if registered
                else tr(
                    "This model is not in the opencode.json you are editing: "
                    "there is nothing to edit or remove. “Add to OpenCode” "
                    "registers it.",
                    es="Este modelo no está en el opencode.json que estás "
                       "editando: no hay nada que editar ni quitar. Con "
                       "«Agregar a OpenCode» queda registrado.",
                )
            )
            self.edit_btn.setToolTip(why)
            self.remove_btn.setToolTip(why)

        has_endpoint = any(
            label == tr("API / Base URL", es="API / Base URL")
            and value not in ("", tr("Unknown", es="Desconocida"))
            for label, value in rows
        )
        self.copy_url_btn.setEnabled(has_endpoint)
        if not has_endpoint:
            self.copy_url_btn.setToolTip(tr(
                "The catalog does not know this provider's endpoint.",
                es="El catálogo no conoce el endpoint de este proveedor.",
            ))
        self.set_probe(probe)

    # -- prueba de conexión ------------------------------------------------
    #
    # El panel no decide nada: main_window calcula si se puede probar, por
    # qué no, y con qué clave. Así el aviso del botón y la propia prueba
    # salen de la misma frase y nunca se contradicen.
    @staticmethod
    def _probe_tip() -> str:
        return tr(
            "Sends a GET to the endpoint's model list: spends no tokens, "
            "sends no credentials and writes nothing to your configuration.",
            es="Hace un GET a la lista de modelos del endpoint: no gasta "
               "tokens, no envía credenciales y no escribe en tu "
               "configuración.",
        )

    def set_probe(self, info: dict | None = None) -> None:
        """Nueva ficha: el estado de la prueba y el resultado, si lo hay."""
        self._probe_info = dict(info or {})
        self._probe_busy = False
        self._apply_probe_state()

    def set_probe_busy(self, busy: bool) -> None:
        """Mientras el worker habla con el endpoint, los botones esperan."""
        self._probe_busy = bool(busy)
        self._apply_probe_state()

    def _apply_probe_state(self) -> None:
        info = self._probe_info
        can = bool(info.get("can"))
        can_key = bool(info.get("can_key"))
        busy = self._probe_busy
        why = str(info.get("why") or "")
        self.probe_btn.setText(
            tr("Testing…", es="Probando…") if busy
            else tr("Test connection", es="Probar conexión")
        )
        self.probe_btn.setEnabled(can and not busy)
        self.probe_btn.setToolTip(why or self._probe_tip())
        self.probe_key_btn.setEnabled(can and can_key and not busy)
        self.probe_key_btn.setVisible(can and can_key)
        self.probe_key_btn.setToolTip(
            str(info.get("key_why") or tr(
                "Sends the environment key only to this endpoint, to check "
                "that it authorizes you.",
                es="Envía la clave del entorno solo a este endpoint, para "
                   "comprobar que te autoriza.",
            ))
        )


class OverviewPanel(QWidget):
    """Resumen inicial: estado de la config, catálogo y accesos rápidos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        self.title = QLabel(tr("Overview", es="Resumen"))
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
    language_changed = pyqtSignal(str)

    SORT_ITEMS = (
        ("A → Z", SORT_NAME, "A → Z"),
        ("Provider", SORT_PROVIDER, "Proveedor"),
        ("Context", SORT_CONTEXT, "Contexto"),
        ("Price", SORT_PRICE, "Precio"),
    )

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
        self.filters_btn.setCheckable(True)
        self.filters_btn.toggled.connect(self.filters_toggled)
        row2.addWidget(self.filters_btn)
        self.sort_combo = QComboBox()
        for _english, data, _spanish in self.SORT_ITEMS:
            self.sort_combo.addItem("", data)
        self.sort_combo.currentIndexChanged.connect(self._emit_sort)
        row2.addWidget(self.sort_combo)
        self.dir_btn = QToolButton()
        self.dir_btn.setText("↑↓")
        self.dir_btn.setCheckable(True)
        self.dir_btn.toggled.connect(lambda _on: self._emit_sort())
        row2.addWidget(self.dir_btn)
        self.count_label = QLabel("")
        self.count_label.setObjectName("mutedLabel")
        row2.addWidget(self.count_label)
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.currentIndexChanged.connect(self._emit_language)
        row2.addWidget(self.language_combo)
        root.addLayout(row2)
        self.retranslate()

    def retranslate(self) -> None:
        """Reaplica los textos fijos sin perder búsqueda, orden ni idioma."""
        self.search_edit.setPlaceholderText(tr(
            "Search providers, models, endpoints, descriptions…  (Ctrl+F)",
            es="Buscar proveedores, modelos, endpoints, descripciones…  (Ctrl+F)",
        ))
        self.filters_btn.setText(tr("Filters", es="Filtros"))
        self.filters_btn.setToolTip(tr(
            "Show or hide the filter panel.",
            es="Mostrar u ocultar el panel de filtros.",
        ))
        self.sort_combo.blockSignals(True)
        for index, (english, _data, spanish) in enumerate(self.SORT_ITEMS):
            self.sort_combo.setItemText(index, tr(english, es=spanish))
        self.sort_combo.blockSignals(False)
        self.sort_combo.setToolTip(tr(
            "Order of the results.", es="Criterio de orden de los resultados."))
        self.dir_btn.setToolTip(tr("Reverse the order.", es="Invertir el orden."))
        self.language_combo.blockSignals(True)
        index = self.language_combo.findData(get_language())
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        self.language_combo.blockSignals(False)
        self.language_combo.setToolTip(tr(
            "Interface language. Applies immediately.",
            es="Idioma de la interfaz. Se aplica al momento.",
        ))

    def _emit_language(self, _index: int) -> None:
        code = self.language_combo.currentData()
        if code:
            self.language_changed.emit(str(code))

    def _emit_sort(self) -> None:
        self.sort_changed.emit(
            self.sort_combo.currentData() or SORT_NAME, self.dir_btn.isChecked()
        )

    def set_path(self, text: str) -> None:
        self.path_label.setText(text)

    def set_count(self, text: str) -> None:
        self.count_label.setText(text)
