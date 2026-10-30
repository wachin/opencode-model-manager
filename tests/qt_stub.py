#!/usr/bin/env python3
"""
Stub headless y determinista de PyQt6 para tests unitarios.

Sustituye a PyQt6 en los tests unitarios y además:
- QSettings funciona EN MEMORIA (no toca QSettings reales del usuario)
  y comparte almacenamiento entre instancias para simular reinicios.
- QMessageBox registra los mensajes en listas en lugar de abrir diálogos.
- stateChanged permite disparar señales manualmente en los tests.

Solo implementa lo que opencode_model_manager.py necesita importar.

Uso (en el test, ANTES de importar el módulo bajo prueba):
    import qt_stub
    qt_stub.install(force=True)

force=True garantiza hermeticidad: aunque PyQt6 esté instalado, los
tests corren contra el stub (QSettings en memoria, cero diálogos).
"""

from __future__ import annotations

import inspect
import sys
import types
from typing import Any


# ---------------------------------------------------------------------------
# QtCore
# ---------------------------------------------------------------------------

class _CheckState:
    Unchecked = types.SimpleNamespace(value=0)
    Checked = types.SimpleNamespace(value=2)


class _ItemDataRole:
    UserRole = 256


class _TextInteractionFlag:
    TextSelectableByMouse = 1


class _Orientation:
    Horizontal = 1
    Vertical = 2


class _Key:
    """Códigos de tecla que usa la interfaz (valores reales de Qt::Key)."""
    Key_Return = 0x01000004
    Key_Enter = 0x01000005
    Key_Escape = 0x01000000


class _AlignmentFlag:
    AlignLeft = 0x0001
    AlignRight = 0x0002
    AlignCenter = 0x0004
    AlignTop = 0x0020
    AlignBottom = 0x0040
    AlignVCenter = 0x0080


class _WidgetAttribute:
    """Sólo el atributo que usa la interfaz: pintar el fondo desde el QSS."""
    WA_StyledBackground = 90


class Qt:
    AlignmentFlag = _AlignmentFlag
    CheckState = _CheckState
    ItemDataRole = _ItemDataRole
    Key = _Key
    TextInteractionFlag = _TextInteractionFlag
    Orientation = _Orientation
    WidgetAttribute = _WidgetAttribute


class QSettings:
    """QSettings en memoria, aislado del QSettings real del usuario.

    El almacenamiento se comparte por (organización, aplicación) entre
    todas las instancias, igual que QSettings real: permite simular
    cerrar y reabrir la aplicación dentro de un test.
    """

    _store: dict[tuple, dict] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._key = tuple(str(a) for a in args)
        self._store.setdefault(self._key, {})

    def _values(self) -> dict:
        return self._store[self._key]

    def value(self, key: str, default: Any = None, type: Any = None) -> Any:
        values = self._values()
        if key not in values:
            return default
        value = values[key]
        if type is bool:
            return bool(value)
        return value

    def setValue(self, key: str, value: Any) -> None:
        self._values()[key] = value

    def contains(self, key: str) -> bool:
        return key in self._values()

    def remove(self, key: str) -> None:
        self._values().pop(key, None)

    @classmethod
    def reset(cls) -> None:
        """Borra todo el almacenamiento (usar en setUp/tearDown)."""
        cls._store.clear()


class Signal:
    """Señal mínima, por instancia, con la semántica que usan los widgets:

    - connect/emitmanuales;
    - cada instancia tiene su propia lista de slots (las señales de clase
      actúan como plantilla);
    - Qt recorta los argumentos a la firma del receptor, y permite conectar
      señal→señal: aquí se hace lo mismo (chips → filters_changed).
    """

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self._slots: list[Any] = []
        self._store_key = ""

    def __set_name__(self, owner: Any, name: str) -> None:
        self._store_key = f"_stub_signal_{name}"

    def __get__(self, obj: Any, objtype: Any = None) -> Any:
        if obj is None:
            return self
        return obj.__dict__.setdefault(self._store_key, Signal())

    def connect(self, slot: Any) -> None:
        self._slots.append(slot)

    def disconnect(self, slot: Any = None) -> None:
        if slot is None:
            self._slots.clear()
        elif slot in self._slots:
            self._slots.remove(slot)

    @staticmethod
    def _positional(slot: Any) -> int | None:
        """Nº de argumentos posicionales que acepta `slot` (None si no se sabe)."""
        try:
            params = inspect.signature(slot).parameters.values()
        except (TypeError, ValueError):
            return None
        if any(p.kind is inspect.Parameter.VAR_POSITIONAL for p in params):
            return None
        return sum(
            1 for p in params
            if p.kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        )

    def emit(self, *args: Any) -> None:
        for slot in list(self._slots):
            accepted = self._positional(slot)
            slot(*args if accepted is None else args[:accepted])

    __call__ = emit


def _widget_signals(widget: Any) -> list[Any]:
    """Todas las señales de esta instancia, creando las declaradas en clase.

    Qt las tiene todas vivas desde la construcción; si aquí solo aparecieran
    cuando se accede a ellas, blockSignals() llegaría tarde para la primera.
    """
    for klass in type(widget).__mro__:
        for value in vars(klass).values():
            if isinstance(value, Signal) and value._store_key:
                widget.__dict__.setdefault(value._store_key, Signal())
    found = [
        signal for signal in widget.__dict__.values()
        if isinstance(signal, Signal)
    ]
    store = widget.__dict__.get("_stub_signals")
    if isinstance(store, dict):
        found.extend(s for s in store.values() if isinstance(s, Signal))
    return found


def _block_signals(widget: Any, block: bool) -> None:
    """blockSignals genérico: silencia TODAS las señales de la instancia.

    Es lo que hace Qt real, y lo que necesitan los `reset_controls()` de los
    paneles: sin esto, limpiar filtros volvería a disparar la búsqueda.
    """
    if block:
        widget._saved_signals = [
            (signal, list(signal._slots)) for signal in _widget_signals(widget)
        ]
        for signal, _slots in widget._saved_signals:
            signal._slots.clear()
    else:
        for signal, slots in getattr(widget, "_saved_signals", []):
            signal._slots[:] = slots
        widget._saved_signals = []


# ---------------------------------------------------------------------------
# QtWidgets
# ---------------------------------------------------------------------------

class QRect:
    """Rectángulo mínimo con la misma API que QRect de Qt real:
    todos los accesores son métodos (width(), left(), right(), ...)."""

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> None:
        self._x = x
        self._y = y
        self._width = width
        self._height = height

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def left(self) -> int:
        return self._x

    def top(self) -> int:
        return self._y

    def right(self) -> int:
        return self._x + self._width - 1

    def bottom(self) -> int:
        return self._y + self._height - 1


class QWidget:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._visible = True
        self._stub_children: list[Any] = []
        self._stub_parent: Any = None
        # QWidget(texto, padre) y QWidget(padre): en Qt el segundo argumento
        # reparenta, y los tests de «no quedan widgets fantasma» lo necesitan.
        for arg in args:
            if isinstance(arg, QWidget):
                arg._register_child(self)

    def _register_child(self, child: "QWidget") -> None:
        if child not in self._stub_children:
            self._stub_children.append(child)
            child._stub_parent = self

    def setParent(self, parent: Any) -> None:
        previous = self._stub_parent
        if previous is not None and self in previous._stub_children:
            previous._stub_children.remove(self)
        self._stub_parent = None
        if parent is not None:
            parent._register_child(self)

    def setLayout(self, layout: Any) -> None:
        self._stub_layout = layout
        if layout is not None:
            layout._attach_owner(self)

    def parent(self) -> Any:
        return self._stub_parent

    def layout(self) -> Any:
        return getattr(self, "_stub_layout", None)

    def children(self) -> list:
        return list(self._stub_children)

    def findChildren(self, type_: Any) -> list:
        found = []
        for child in self._stub_children:
            if isinstance(child, type_):
                found.append(child)
            found.extend(child.findChildren(type_))
        return found

    def setToolTip(self, tip: str) -> None:
        pass

    def setStyleSheet(self, sheet: str) -> None:
        self._style_sheet = sheet or ""

    def styleSheet(self) -> str:
        return getattr(self, "_style_sheet", "")

    def setVisible(self, visible: bool) -> None:
        self._visible = bool(visible)

    def isVisible(self) -> bool:
        return bool(getattr(self, "_visible", True))

    def __getattr__(self, name: str) -> Any:
        """Métodos de Qt no simulados: se aceptan y se ignoran.

        Permite que los paneles se construyan headless sin implementar
        toda la API de QWidget. Los atributos privados SÍ fallan, para no
        ocultar errores reales del código bajo prueba.
        """
        if name.startswith("_"):
            raise AttributeError(name)
        return _noop


class _NoOp:
    """Objeto tolerante: es llamable y encadena cualquier atributo."""

    def __call__(self, *args: Any, **kwargs: Any) -> "_NoOp":
        return self

    def __getattr__(self, name: str) -> "_NoOp":
        return self

    def __iter__(self):
        return iter(())


_noop = _NoOp()


class QMainWindow(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._window_title = ""
        self._minimum_size: tuple[int, int] | None = None
        self._style_sheet = ""

    def setWindowTitle(self, title: str) -> None:
        self._window_title = title

    def setMinimumSize(self, w: int, h: int) -> None:
        self._minimum_size = (w, h)

    def resize(self, w: int, h: int) -> None:
        self._size = (w, h)

    def width(self) -> int:
        return getattr(self, "_size", (0, 0))[0]

    def height(self) -> int:
        return getattr(self, "_size", (0, 0))[1]

    def move(self, x: int, y: int) -> None:
        self._pos = (x, y)

    def x(self) -> int:
        return getattr(self, "_pos", (0, 0))[0]

    def y(self) -> int:
        return getattr(self, "_pos", (0, 0))[1]

    def saveGeometry(self) -> bytes:
        """Serializa tamaño y posición actuales (formato propio del stub)."""
        return f"{self.width()},{self.height()},{self.x()},{self.y()}".encode(
            "ascii"
        )

    def restoreGeometry(self, geometry: Any) -> bool:
        """Restaura la geometría serializada por saveGeometry() del stub."""
        try:
            raw = bytes(geometry)
            w, h, x, y = raw.decode("ascii").split(",")
            self.resize(int(w), int(h))
            self.move(int(x), int(y))
            return True
        except Exception:
            return False

    def setStyleSheet(self, sheet: str) -> None:
        self._style_sheet = sheet

    def setCentralWidget(self, widget: Any) -> None:
        pass

    def statusBar(self) -> Any:
        if not hasattr(self, "_status_bar"):
            self._status_bar = _StatusBar()
        return self._status_bar

    def closeEvent(self, event: Any) -> None:
        pass


class _StatusBar:
    def showMessage(self, message: str) -> None:
        self.last_message = message


class QDialog(QWidget):
    class DialogCode:
        Accepted = 1
        Rejected = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._window_title = ""
        self._minimum_width: int | None = None

    def setWindowTitle(self, title: str) -> None:
        self._window_title = title

    def setMinimumWidth(self, w: int) -> None:
        self._minimum_width = w

    def exec(self) -> int:
        return QDialog.DialogCode.Rejected

    def accept(self) -> None:
        pass

    def reject(self) -> None:
        pass


class QMessageBox:
    """Guarda los mensajes en listas de clase en lugar de abrir diálogos."""

    class StandardButton:
        Ok = 1024
        Cancel = 4194304
        Yes = 16384
        No = 65536

    information_calls: list[tuple] = []
    warning_calls: list[tuple] = []
    critical_calls: list[tuple] = []
    question_calls: list[tuple] = []
    question_reply: Any = None  # respuesta configurable para .question()

    @classmethod
    def reset(cls) -> None:
        cls.information_calls.clear()
        cls.warning_calls.clear()
        cls.critical_calls.clear()
        cls.question_calls.clear()
        cls.question_reply = None

    @classmethod
    def information(cls, *args: Any) -> Any:
        cls.information_calls.append(args)
        return cls.StandardButton.Ok

    @classmethod
    def warning(cls, *args: Any) -> Any:
        cls.warning_calls.append(args)
        return cls.StandardButton.Ok

    @classmethod
    def critical(cls, *args: Any) -> Any:
        cls.critical_calls.append(args)
        return cls.StandardButton.Ok

    @classmethod
    def question(cls, *args: Any) -> Any:
        cls.question_calls.append(args)
        if cls.question_reply is not None:
            return cls.question_reply
        return cls.StandardButton.Yes


class QComboBox(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.currentIndexChanged = Signal()
        self.activated = Signal()
        self._items: list[tuple[str, Any]] = []
        self._current_index = -1
        self._editable = False
        self._line_text = ""

    def addItem(self, text: str, data: Any = None) -> None:
        self._items.append((text, data))
        if self._current_index < 0:
            # Igual que Qt: el primer item añade seleccionado.
            self._current_index = 0

    def addItems(self, texts: Any) -> None:
        for text in texts:
            self._items.append((str(text), str(text)))
        if self._current_index < 0 and self._items:
            self._current_index = 0

    def clear(self) -> None:
        self._items.clear()
        self._current_index = -1

    def findData(self, data: Any) -> int:
        for index, (_text, item_data) in enumerate(self._items):
            if item_data == data:
                return index
        return -1

    def findText(self, text: str) -> int:
        for index, (item_text, _data) in enumerate(self._items):
            if item_text == text:
                return index
        return -1

    def setCurrentIndex(self, index: int) -> None:
        if index == self._current_index:
            return
        self._current_index = index
        # Igual que Qt: cambiar el índice dispara currentIndexChanged.
        self.currentIndexChanged.emit(index)

    def blockSignals(self, block: bool) -> None:
        _block_signals(self, block)

    def currentIndex(self) -> int:
        return self._current_index

    def currentData(self) -> Any:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index][1]
        return None

    def currentText(self) -> str:
        if self._editable and self._line_text:
            return self._line_text
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index][0]
        return ""

    def setCurrentText(self, text: str) -> None:
        self._line_text = text
        index = self.findText(text)
        if index >= 0:
            self._current_index = index

    def itemText(self, index: int) -> str:
        return self._items[index][0]

    def itemData(self, index: int) -> Any:
        return self._items[index][1]

    def setItemData(self, index: int, data: Any) -> None:
        self._items[index] = (self._items[index][0], data)

    def count(self) -> int:
        return len(self._items)

    def setEditable(self, editable: bool) -> None:
        self._editable = editable

    def isEditable(self) -> bool:
        return self._editable

    def setSizeAdjustPolicy(self, policy: Any) -> None:
        pass


class QListWidgetItem:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self._data: dict[int, Any] = {}

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setData(self, role: int, value: Any) -> None:
        self._data[role] = value

    def data(self, role: int) -> Any:
        return self._data.get(role)

    def __getattr__(self, name: str) -> Any:
        """Métodos de pintado (setToolTip, setForeground…): se ignoran."""
        if name.startswith("_"):
            raise AttributeError(name)
        return _noop


class _Viewport:
    """viewport() de QAbstractScrollArea: dimensiones navegables en tests."""

    def __init__(self, owner: Any) -> None:
        self._owner = owner

    def width(self) -> int:
        return int(getattr(self._owner, "_width", 0))

    def height(self) -> int:
        return int(getattr(self._owner, "_height", 0))


class QListWidget(QWidget):
    class ViewMode:
        # Nombres exactos de PyQt6 6.x (no existe "List" ni "ListView").
        ListMode = 1
        IconMode = 3

    class SelectionMode:
        NoSelection = 0
        SingleSelection = 1
        ExtendedSelection = 2

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.itemSelectionChanged = Signal()
        self.itemActivated = Signal()
        self.itemClicked = Signal()
        self._items: list[QListWidgetItem] = []
        self._current_item: QListWidgetItem | None = None
        self._spacing = 0
        self._viewport = _Viewport(self)

    def viewport(self) -> "_Viewport":
        return self._viewport

    def setSpacing(self, spacing: int) -> None:
        self._spacing = spacing

    def addItem(self, item: QListWidgetItem) -> None:
        self._items.append(item)

    def clear(self) -> None:
        had_item = self._current_item is not None
        self._items.clear()
        self._current_item = None
        if had_item:
            self.itemSelectionChanged.emit()

    def count(self) -> int:
        return len(self._items)

    def item(self, index: int) -> QListWidgetItem:
        return self._items[index]

    def setCurrentItem(self, item: QListWidgetItem) -> None:
        if item is self._current_item:
            return
        self._current_item = item
        self.itemSelectionChanged.emit()

    def currentItem(self) -> QListWidgetItem | None:
        return self._current_item

    def selectedItems(self) -> list[QListWidgetItem]:
        if self._current_item is not None:
            return [self._current_item]
        return []

    def setViewMode(self, mode: Any) -> None:
        pass

    def setSelectionMode(self, mode: Any) -> None:
        pass

    def setUniformItemSizes(self, uniform: bool) -> None:
        pass

    def setWordWrap(self, wrap: bool) -> None:
        pass

    def setEditTriggers(self, triggers: Any) -> None:
        pass

    def scrollToItem(self, item: Any, *args: Any) -> None:
        pass

    def setCurrentRow(self, row: int) -> None:
        if 0 <= row < len(self._items):
            self.setCurrentItem(self._items[row])

    def currentRow(self) -> int:
        return self._items.index(self._current_item) if self._current_item else -1


class QLineEdit(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._text = ""
        self._placeholder = ""
        self.textChanged = Signal()
        self.returnPressed = Signal()
        self.editingFinished = Signal()

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setPlaceholderText(self, text: str) -> None:
        self._placeholder = text

    def setReadOnly(self, read_only: bool) -> None:
        pass

    def clear(self) -> None:
        self._text = ""

    def selectAll(self) -> None:
        pass

    def setFocus(self) -> None:
        pass

    def setClearButtonEnabled(self, enabled: bool) -> None:
        pass

    def setEchoMode(self, mode: Any) -> None:
        pass


class QTextEdit(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._text = ""
        self._read_only = False

    def setPlainText(self, text: str) -> None:
        self._text = text

    def toPlainText(self) -> str:
        return self._text

    def setReadOnly(self, read_only: bool) -> None:
        self._read_only = read_only

    def setFont(self, font: Any) -> None:
        pass


class QCheckBox(QWidget):
    def __init__(self, text: str = "", *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._text = text
        self.stateChanged = Signal()
        self.toggled = Signal()
        self._checked = False

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        changed = checked != self._checked
        self._checked = checked
        if not changed:
            return
        state = Qt.CheckState.Checked.value if self._checked else 0
        # Igual que Qt real: un cambio de estado dispara ambas señales.
        self.stateChanged.emit(state)
        self.toggled.emit(self._checked)

    def isChecked(self) -> bool:
        return self._checked

    def blockSignals(self, block: bool) -> None:
        _block_signals(self, block)


class QPushButton(QWidget):
    def __init__(self, text: str = "", *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.clicked = Signal()
        self._text = text

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setEnabled(self, enabled: bool) -> None:
        self._enabled = bool(enabled)

    def isEnabled(self) -> bool:
        return bool(getattr(self, "_enabled", True))

    def click(self) -> None:
        """Como Qt: un clic programado solo emite si el botón está activo."""
        if self.isEnabled():
            self.clicked.emit()

    def setMinimumHeight(self, height: int) -> None:
        pass


class QLabel(QWidget):
    def __init__(self, text: str = "", *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._text = text

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setWordWrap(self, wrap: bool) -> None:
        pass

    def setFont(self, font: Any) -> None:
        pass

    def setTextInteractionFlags(self, flags: Any) -> None:
        pass


class QGroupBox(QWidget):
    def __init__(self, title: str = "", *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._title = title


class _LayoutItem:
    """Envoltorio mínimo de QLayoutItem: widget() Y layout().

    Sin layout() los tests no podían ver que takeAt(0).widget() devuelve None
    en las filas añadidas con addLayout(): el bug de las etiquetas fantasma de
    la ficha vivía exactamente ahí.
    """

    def __init__(self, widget: Any = None, args: tuple = (),
                 layout: Any = None) -> None:
        self._widget = widget
        self._layout = layout
        self._args = args

    def widget(self) -> Any:
        return self._widget

    def layout(self) -> Any:
        return self._layout

    def sizeHint(self) -> Any:
        return None


class _LayoutMixin:
    """Layout de prueba con las dos cosas que el stub no tenía: el widget
    dueño y los sub-layouts como items.

    addWidget() reparenta en el dueño (Qt lo hace) y addLayout() produce un
    item cuyo widget() es None pero cuyo layout() sí existe. Sin eso, un
    bucle de limpieza que sólo mire item.widget() pasa todos los tests
    aunque en Qt deje las etiquetas de la ficha anterior pintadas encima.
    """

    def __init__(self, parent: Any = None, *args: Any, **kwargs: Any) -> None:
        self._items: list[Any] = []
        self._layout_items: list[_LayoutItem] = []
        self._owner: Any = None
        self._parent_layout: Any = None
        if isinstance(parent, _LayoutMixin):
            self._parent_layout = parent
        elif isinstance(parent, QWidget):
            if parent.layout() is None:
                parent.setLayout(self)
            else:
                self._attach_owner(parent)

    def _attach_owner(self, widget: Any) -> None:
        self._owner = widget

    def parentWidget(self) -> Any:
        return self._owner

    def _resolve_owner(self) -> Any:
        layout: Any = self
        while layout is not None:
            if layout._owner is not None:
                return layout._owner
            layout = layout._parent_layout
        return None

    def _adopt(self, widget: Any) -> None:
        owner = self._resolve_owner()
        if owner is not None and widget._stub_parent is not owner:
            widget.setParent(owner)

    def _owned_widgets(self) -> list[Any]:
        """Widgets de este layout y de los sub-layouts que contenga."""
        widgets: list[Any] = []
        for item in self._layout_items:
            if item._widget is not None:
                widgets.append(item._widget)
            if item._layout is not None:
                widgets.extend(item._layout._owned_widgets())
        return widgets

    def addWidget(self, widget: Any, *args: Any, **kwargs: Any) -> None:
        self._items.append(widget)
        self._layout_items.append(_LayoutItem(widget, args))
        if isinstance(widget, QWidget):
            self._adopt(widget)

    def insertWidget(self, index: int, widget: Any, *args: Any) -> None:
        self._items.insert(index, widget)
        self._layout_items.insert(index, _LayoutItem(widget, args))
        if isinstance(widget, QWidget):
            self._adopt(widget)

    def addLayout(self, layout: Any, *args: Any, **kwargs: Any) -> None:
        self._items.append(layout)
        self._layout_items.append(_LayoutItem(None, args, layout))
        if isinstance(layout, _LayoutMixin):
            layout._parent_layout = self
            # Qt reparenta al widget dueño cuando el sub-layout se instala:
            # si no, un addWidget previo a el addLayout quedaría huérfano y
            # los tests de «no sobran etiquetas» no verían el bug de la ficha.
            for widget in layout._owned_widgets():
                self._adopt(widget)

    def addRow(self, *args: Any, **kwargs: Any) -> None:
        self._items.append(args)
        for arg in args:
            if isinstance(arg, _LayoutMixin):
                arg._parent_layout = self
                self._layout_items.append(_LayoutItem(None, (), arg))
                for widget in arg._owned_widgets():
                    self._adopt(widget)
            elif isinstance(arg, QWidget):
                self._layout_items.append(_LayoutItem(arg))
                self._adopt(arg)

    def addStretch(self, *args: Any, **kwargs: Any) -> None:
        pass

    def addSpacing(self, *args: Any, **kwargs: Any) -> None:
        pass

    def setContentsMargins(self, *margins: int) -> None:
        pass

    def setSpacing(self, spacing: int) -> None:
        pass

    def setAlignment(self, *args: Any, **kwargs: Any) -> None:
        pass

    def count(self) -> int:
        return len(self._layout_items)

    def itemAt(self, index: int) -> Any:
        if 0 <= index < len(self._layout_items):
            return self._layout_items[index]
        return None

    def takeAt(self, index: int) -> Any:
        if 0 <= index < len(self._layout_items):
            return self._layout_items.pop(index)
        return _LayoutItem(None)


class QHBoxLayout(_LayoutMixin):
    pass


class QVBoxLayout(_LayoutMixin):
    pass


class QFormLayout(_LayoutMixin):
    pass


class QSplitter(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._widgets: list[Any] = []
        self._sizes: list[int] = []

    def addWidget(self, widget: Any) -> int:
        self._widgets.append(widget)
        return len(self._widgets) - 1

    def widget(self, index: int) -> Any:
        return self._widgets[index]

    def setSizes(self, sizes: list[int]) -> None:
        self._sizes = list(sizes)

    def sizes(self) -> list[int]:
        return list(self._sizes)

    def setCollapsible(self, index: int, collapsible: bool) -> None:
        pass

    def setStretchFactor(self, index: int, factor: int) -> None:
        pass

    def setHandleWidth(self, width: int) -> None:
        pass


class QApplication:
    _instance: Any = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        QApplication._instance = self
        self._palette = QPalette()
        self._style_sheet = ""

    @staticmethod
    def primaryScreen() -> Any:
        return None

    @staticmethod
    def instance() -> Any:
        return QApplication._instance

    @staticmethod
    def exec() -> int:
        return 0

    @staticmethod
    def setStyle(style: str) -> None:
        pass

    @staticmethod
    def setApplicationName(name: str) -> None:
        pass

    @staticmethod
    def clipboard() -> Any:
        return None

    @staticmethod
    def style() -> Any:
        return _NoOp()

    def palette(self) -> QPalette:
        return self._palette.copy()

    def setPalette(self, palette: QPalette) -> None:
        self._palette = palette.copy()

    def styleSheet(self) -> str:
        return self._style_sheet

    def setStyleSheet(self, sheet: str) -> None:
        self._style_sheet = sheet or ""


class QDialogButtonBox(QWidget):
    class StandardButton:
        Ok = 1024
        Cancel = 4194304

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.accepted = Signal()
        self.rejected = Signal()


class QFileDialog:
    @staticmethod
    def getOpenFileName(*args: Any, **kwargs: Any) -> tuple[str, str]:
        return "", ""


class QFont:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def setPointSize(self, size: int) -> None:
        pass

    def setBold(self, bold: bool) -> None:
        pass

    def setFamily(self, family: str) -> None:
        pass

    def setStyleHint(self, hint: Any) -> None:
        pass

    class StyleHint:
        Monospace = 49
        TypeWriter = 49
        SansSerif = 3


class QKeySequence:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass


class QKeyEvent:
    """Evento de tecla mínimo, para probar keyPressEvent sin Qt real."""

    def __init__(self, key: int, text: str = "", modifiers: int = 0) -> None:
        self._key = key
        self._text = text
        self._modifiers = modifiers

    def key(self) -> int:
        return self._key

    def text(self) -> str:
        return self._text

    def modifiers(self) -> int:
        return self._modifiers


class QShortcut(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.activated = Signal()


# ---------------------------------------------------------------------------
# Nombres adicionales que necesitan los módulos del paquete ``omm``.
# Se implementa lo justo para construir y consultar sin Qt real: los tests
# de lógica no dependen del pintado, y el arranque de la interfaz completa
# se comprueba con PyQt6 real en modo offscreen.
# ---------------------------------------------------------------------------

def pyqtSignal(*_args: Any, **_kwargs: Any) -> Any:
    """Descriptor mínimo: cada instancia recibe su propio Signal()."""

    class _Descriptor:
        def __set_name__(self, owner, name: str) -> None:
            self.name = f"_stub_signal_{name}"

        def __get__(self, obj: Any, objtype: Any = None) -> Any:
            if obj is None:
                return self
            store = obj.__dict__.setdefault("_stub_signals", {})
            return store.setdefault(self.name, Signal())

    return _Descriptor()


class QObject(QWidget):
    pass


class QThread(QObject):
    """Hilo simulado: ``start()`` NO ejecuta nada (cero red en los tests)."""

    finished = pyqtSignal()

    def __init__(self, parent: Any = None) -> None:
        super().__init__()

    def start(self, *args: Any, **kwargs: Any) -> None:
        self._stub_started = True

    def isRunning(self) -> bool:
        return False

    def run(self) -> None:  # pragma: no cover - la llaman los tests a mano
        pass

    def wait(self, *args: Any, **kwargs: Any) -> bool:
        return True

    def quit(self) -> None:
        pass


class QTimer(QObject):
    timeout = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._interval = 0
        self._single = False

    def setSingleShot(self, single: bool) -> None:
        self._single = single

    def setInterval(self, msec: int) -> None:
        self._interval = msec

    def start(self, *args: Any, **kwargs: Any) -> None:
        pass

    def stop(self) -> None:
        pass

    @staticmethod
    def singleShot(msec: int, callback: Any) -> None:
        pass


class QFrame(QWidget):
    class Shape:
            NoFrame = 0
            StyledPanel = 5


class QSizePolicy(QWidget):
    class Policy:
        Fixed = 0
        Expanding = 1
        Preferred = 4
        Minimum = 1


class QAbstractItemView(QWidget):
    class SelectionMode:
        NoSelection = 0
        SingleSelection = 1
        ExtendedSelection = 2

    class EditTrigger:
        NoEditTriggers = 0

    def setSelectionMode(self, mode: Any) -> None:
        pass

    def setEditTriggers(self, triggers: Any) -> None:
        pass


class QStackedWidget(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._pages: list[Any] = []
        self._current = 0

    def addWidget(self, widget: Any) -> int:
        self._pages.append(widget)
        return len(self._pages) - 1

    def setCurrentIndex(self, index: int) -> None:
        self._current = index

    def currentIndex(self) -> int:
        return self._current

    def widget(self, index: int) -> Any:
        return self._pages[index]

    def count(self) -> int:
        return len(self._pages)


class QScrollArea(QWidget):
    def setWidget(self, widget: Any) -> None:
        self._widget = widget

    def setWidgetResizable(self, resizable: bool) -> None:
        pass

    def setFrameShape(self, shape: Any) -> None:
        pass

    def takeWidget(self) -> Any:
        return getattr(self, "_widget", None)


class QPlainTextEdit(QWidget):
    textChanged = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._plain = ""

    def setPlainText(self, text: str) -> None:
        self._plain = text

    def toPlainText(self) -> str:
        return self._plain

    def appendPlainText(self, text: str) -> None:
        self._plain = f"{self._plain}\n{text}" if self._plain else text

    def setPlaceholderText(self, text: str) -> None:
        pass


class QTabWidget(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._tabs: list[tuple[Any, str]] = []
        self._current = 0

    def addTab(self, widget: Any, label: str) -> int:
        self._tabs.append((widget, label))
        return len(self._tabs) - 1

    def setCurrentIndex(self, index: int) -> None:
        self._current = index

    def currentIndex(self) -> int:
        return self._current

    def widget(self, index: int) -> Any:
        return self._tabs[index][0]

    def count(self) -> int:
        return len(self._tabs)


class QToolButton(QPushButton):
    toggled = Signal()
    clicked = Signal()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._checkable = False
        self._checked = False

    def setCheckable(self, checkable: bool) -> None:
        self._checkable = bool(checkable)

    def isCheckable(self) -> bool:
        return self._checkable

    def setChecked(self, checked: bool) -> None:
        checked = bool(checked)
        changed = checked != self._checked
        self._checked = checked
        if changed and self._checkable:
            self.toggled.emit(checked)

    def isChecked(self) -> bool:
        return self._checked

    def blockSignals(self, block: bool) -> None:
        _block_signals(self, block)


class QTreeWidgetItem:
    class ChildIndicatorPolicy:
        ShowIndicator = 0
        DontShowIndicator = 1
        ShowIndicatorWhenChildless = 2

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._texts: list[str] = []
        self._data: dict[tuple[int, int], Any] = {}
        self._children: list["QTreeWidgetItem"] = []
        self._parent: "QTreeWidgetItem | None" = None
        self._tree: Any = None
        self._expanded = False
        if args and isinstance(args[0], list):
            self._texts = list(args[0])
        elif args and isinstance(args[0], QTreeWidgetItem):
            self._parent = args[0]
            self._tree = args[0]._tree
            args[0]._children.append(self)
        elif args and isinstance(args[0], str):
            self._texts = [args[0]]

    def text(self, column: int = 0) -> str:
        return self._texts[column] if column < len(self._texts) else ""

    def setData(self, column: int, role: int, value: Any) -> None:
        self._data[(column, role)] = value

    def data(self, column: int, role: int) -> Any:
        return self._data.get((column, role))

    def setToolTip(self, column: int, tip: str) -> None:
        pass

    def toolTip(self, column: int) -> str:
        return ""

    def font(self, column: int) -> "QFont":
        return QFont()

    def setFont(self, column: int, font: Any) -> None:
        pass

    def setForeground(self, column: int, brush: Any) -> None:
        self._foreground = brush

    def foreground(self, column: int = 0) -> Any:
        return getattr(self, "_foreground", None)

    def setBackground(self, column: int, brush: Any) -> None:
        pass

    def setExpanded(self, expanded: bool) -> None:
        expanded = bool(expanded)
        opened = expanded and not self._expanded
        self._expanded = expanded
        # Qt real: expandir dispara itemExpanded (expansión perezosa del árbol).
        if opened and self._tree is not None:
            self._tree.itemExpanded.emit(self)

    def isExpanded(self) -> bool:
        return self._expanded

    def setChildIndicatorPolicy(self, policy: Any) -> None:
        pass

    def addChild(self, child: "QTreeWidgetItem") -> None:
        child._parent = self
        child._tree = self._tree
        self._children.append(child)

    def children(self) -> list["QTreeWidgetItem"]:
        return list(self._children)

    def child(self, index: int) -> "QTreeWidgetItem":
        return self._children[index]

    def childCount(self) -> int:
        return len(self._children)

    def takeChildren(self) -> list["QTreeWidgetItem"]:
        taken = list(self._children)
        self._children.clear()
        return taken

    def parent(self) -> "QTreeWidgetItem | None":
        return self._parent

    def columnCount(self) -> int:
        return 1


class QTreeView(QAbstractItemView):
    pass


class QTreeWidget(QTreeView):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.itemClicked = Signal()
        self.itemExpanded = Signal()
        self.itemSelectionChanged = Signal()
        self._top: list[QTreeWidgetItem] = []
        self._current_item: QTreeWidgetItem | None = None

    def setHeaderHidden(self, hidden: bool) -> None:
        pass

    def setRootIsDecorated(self, decorated: bool) -> None:
        pass

    def setUniformRowHeights(self, uniform: bool) -> None:
        pass

    def setIndentation(self, value: int) -> None:
        pass

    def setSortingEnabled(self, enabled: bool) -> None:
        pass

    def setColumnCount(self, count: int) -> None:
        pass

    def addTopLevelItem(self, item: QTreeWidgetItem) -> None:
        item._tree = self
        for child in item.children():
            child._tree = self
        self._top.append(item)

    def topLevelItem(self, index: int) -> QTreeWidgetItem:
        return self._top[index]

    def topLevelItemCount(self) -> int:
        return len(self._top)

    def clear(self) -> None:
        self._top.clear()
        self._current_item = None

    def setCurrentItem(self, item: QTreeWidgetItem) -> None:
        self._current_item = item

    def currentItem(self) -> QTreeWidgetItem | None:
        return self._current_item

    def selectedItems(self) -> list[QTreeWidgetItem]:
        return [self._current_item] if self._current_item else []

    def scrollToItem(self, item: Any, *args: Any) -> None:
        pass

    def setUpdatesEnabled(self, enabled: bool) -> None:
        pass


class QBrush:
    def __init__(self, color: Any = None, *args: Any, **kwargs: Any) -> None:
        self._color = color

    def color(self) -> Any:
        return self._color


class QColor:
    """Color con parseo real de #rgb / #rrggbb: los tests de contraste
    comparan canales, así que quedarse en un valor fijo los invalidaría."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._rgb = (0, 0, 0)
        if args:
            first = args[0]
            if isinstance(first, QColor):
                self._rgb = first._rgb
            elif isinstance(first, str):
                self._rgb = self._parse(first)
            elif isinstance(first, int) and len(args) >= 3:
                self._rgb = (args[0], args[1], args[2])

    @staticmethod
    def _parse(text: str) -> tuple:
        body = text.strip().lstrip("#")
        if len(body) == 3:
            body = "".join(ch * 2 for ch in body)
        if len(body) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in body):
            return (0, 0, 0)
        return tuple(int(body[i:i + 2], 16) for i in (0, 2, 4))

    def red(self) -> int:
        return self._rgb[0]

    def green(self) -> int:
        return self._rgb[1]

    def blue(self) -> int:
        return self._rgb[2]

    def getRgb(self) -> tuple:
        return self._rgb

    def name(self) -> str:
        return "#{:02x}{:02x}{:02x}".format(*self._rgb)

    def isValid(self) -> bool:
        return True

    def lightness(self) -> int:
        # Fórmula de Qt: max+min sobre 2, en escala 0..255.
        lo, hi = min(self._rgb), max(self._rgb)
        return int((lo + hi) / 2)

    @staticmethod
    def fromRgb(r: int, g: int, b: int) -> "QColor":
        return QColor(r, g, b)


class QPalette:
    class ColorGroup:
        Active = 0
        Disabled = 1
        Inactive = 2
        All = 3

    class ColorRole:
        Window = 0
        WindowText = 1
        Base = 2
        AlternateBase = 3
        ToolTipBase = 4
        ToolTipText = 5
        Text = 6
        Button = 7
        ButtonText = 8
        Background = 9
        Foreground = 10
        Light = 12
        Midlight = 13
        Dark = 14
        Mid = 15
        Shadow = 16
        Highlight = 17
        HighlightedText = 18
        Link = 19
        LinkVisited = 20
        BrightText = 21
        PlaceholderText = 22

    def __init__(self) -> None:
        self._colors: dict[tuple[int, int], QColor] = {}

    def setColor(self, *args: Any) -> None:
        if len(args) == 2:
            role, color = args
            group = QPalette.ColorGroup.Active
        else:
            group, role, color = args
        self._colors[(int(group), int(role))] = QColor(color)

    def color(self, *args: Any) -> QColor:
        """Firma real de Qt: color(rol) o color(grupo, rol)."""
        if len(args) == 1:
            group, role = QPalette.ColorGroup.Active, args[0]
        else:
            group, role = args
        return self._colors.get((int(group), int(role)), QColor("#000000"))

    def copy(self) -> "QPalette":
        clone = QPalette()
        clone._colors = dict(self._colors)
        return clone


# ---------------------------------------------------------------------------
# Instalación
# ---------------------------------------------------------------------------

def install(force: bool = False) -> None:
    """Registra el stub como sys.modules["PyQt6"] y submódulos.

    Con force=False no hace nada si PyQt6 está realmente instalado.
    Con force=True (recomendado en tests) sustituye siempre PyQt6 para
    garantizar hermeticidad: QSettings del stub vive en memoria y
    QMessageBox nunca abre diálogos.
    """
    if not force and "PyQt6" in sys.modules:
        try:
            __import__("PyQt6.QtWidgets")
            return  # PyQt6 real disponible y force=False: no sustituir.
        except Exception:
            pass

    pyqt6 = types.ModuleType("PyQt6")
    pyqt6.__path__ = []  # marca como paquete

    QtCore = types.ModuleType("PyQt6.QtCore")
    QtCore.Qt = Qt
    QtCore.QSettings = QSettings

    QtGui = types.ModuleType("PyQt6.QtGui")
    QtGui.QFont = QFont
    QtGui.QRect = QRect
    QtGui.QKeySequence = QKeySequence
    QtGui.QKeyEvent = QKeyEvent
    QtGui.QShortcut = QShortcut

    QtWidgets = types.ModuleType("PyQt6.QtWidgets")
    for name in (
        "QAbstractItemView", "QApplication", "QBrush", "QCheckBox", "QColor",
        "QComboBox", "QDialog", "QDialogButtonBox", "QFileDialog",
        "QFormLayout", "QFrame", "QGroupBox", "QHBoxLayout", "QLabel",
        "QLineEdit", "QListWidget", "QListWidgetItem", "QMainWindow",
        "QMessageBox", "QPalette", "QPlainTextEdit", "QPushButton",
        "QScrollArea", "QSizePolicy", "QSplitter", "QStackedWidget",
        "QTabWidget", "QTextEdit", "QToolButton", "QTreeWidget",
        "QTreeWidgetItem", "QTreeView", "QVBoxLayout", "QWidget",
    ):
        setattr(QtWidgets, name, globals()[name])

    QtCore.QObject = QObject
    QtCore.QThread = QThread
    QtCore.QTimer = QTimer
    QtCore.pyqtSignal = pyqtSignal
    QtGui.QColor = QColor
    QtGui.QPalette = QPalette
    QtGui.QBrush = QBrush

    for name, module in (
        ("PyQt6", pyqt6),
        ("PyQt6.QtCore", QtCore),
        ("PyQt6.QtGui", QtGui),
        ("PyQt6.QtWidgets", QtWidgets),
    ):
        sys.modules[name] = module
