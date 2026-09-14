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


class Qt:
    CheckState = _CheckState
    ItemDataRole = _ItemDataRole
    TextInteractionFlag = _TextInteractionFlag
    Orientation = _Orientation


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
    """Señal mínima: permite conectar slots y emitir manualmente."""

    def __init__(self) -> None:
        self._slots: list[Any] = []

    def connect(self, slot: Any) -> None:
        self._slots.append(slot)

    def emit(self, *args: Any) -> None:
        for slot in list(self._slots):
            slot(*args)


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
        pass

    def setToolTip(self, tip: str) -> None:
        pass

    def setStyleSheet(self, sheet: str) -> None:
        pass


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
        self._items: list[tuple[str, Any]] = []
        self._current_index = -1

    def addItem(self, text: str, data: Any = None) -> None:
        self._items.append((text, data))

    def clear(self) -> None:
        self._items.clear()
        self._current_index = -1

    def findData(self, data: Any) -> int:
        for index, (_text, item_data) in enumerate(self._items):
            if item_data == data:
                return index
        return -1

    def setCurrentIndex(self, index: int) -> None:
        self._current_index = index

    def currentIndex(self) -> int:
        return self._current_index

    def currentData(self) -> Any:
        if 0 <= self._current_index < len(self._items):
            return self._items[self._current_index][1]
        return None

    def count(self) -> int:
        return len(self._items)

    def blockSignals(self, block: bool) -> None:
        pass

    def setEditable(self, editable: bool) -> None:
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


class QListWidget(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.itemSelectionChanged = Signal()
        self._items: list[QListWidgetItem] = []
        self._current_item: QListWidgetItem | None = None
        self._spacing = 0

    def setSpacing(self, spacing: int) -> None:
        self._spacing = spacing

    def addItem(self, item: QListWidgetItem) -> None:
        self._items.append(item)

    def clear(self) -> None:
        self._items.clear()
        self._current_item = None

    def count(self) -> int:
        return len(self._items)

    def item(self, index: int) -> QListWidgetItem:
        return self._items[index]

    def setCurrentItem(self, item: QListWidgetItem) -> None:
        self._current_item = item

    def selectedItems(self) -> list[QListWidgetItem]:
        if self._current_item is not None:
            return [self._current_item]
        return []


class QLineEdit(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._text = ""
        self._placeholder = ""

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setPlaceholderText(self, text: str) -> None:
        self._placeholder = text

    def setReadOnly(self, read_only: bool) -> None:
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
        self._checked = False

    def setChecked(self, checked: bool) -> None:
        self._checked = bool(checked)
        state = Qt.CheckState.Checked.value if self._checked else 0
        # Igual que Qt real: setChecked dispara stateChanged salvo bloqueo.
        self.stateChanged.emit(state)

    def isChecked(self) -> bool:
        return self._checked

    def blockSignals(self, block: bool) -> None:
        self._blocked = block
        if block:
            self.stateChanged._slots_backup = list(self.stateChanged._slots)
            self.stateChanged._slots.clear()
        else:
            backup = getattr(self.stateChanged, "_slots_backup", None)
            if backup is not None:
                self.stateChanged._slots = backup
                self.stateChanged._slots_backup = None


class QPushButton(QWidget):
    def __init__(self, text: str = "", *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.clicked = Signal()
        self._text = text

    def setText(self, text: str) -> None:
        self._text = text

    def setEnabled(self, enabled: bool) -> None:
        self._enabled = enabled

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


class _LayoutMixin:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._items: list[Any] = []

    def addWidget(self, widget: Any) -> None:
        self._items.append(widget)

    def addLayout(self, layout: Any) -> None:
        self._items.append(layout)

    def addRow(self, *args: Any) -> None:
        self._items.append(args)

    def setContentsMargins(self, *margins: int) -> None:
        pass

    def setSpacing(self, spacing: int) -> None:
        pass


class QHBoxLayout(_LayoutMixin):
    pass


class QVBoxLayout(_LayoutMixin):
    pass


class QFormLayout(_LayoutMixin):
    pass


class QSplitter(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()

    def addWidget(self, widget: Any) -> None:
        pass

    def setSizes(self, sizes: list[int]) -> None:
        pass


class QApplication:
    @staticmethod
    def primaryScreen() -> Any:
        return None

    @staticmethod
    def exec() -> int:
        return 0

    @staticmethod
    def setStyle(style: str) -> None:
        pass

    @staticmethod
    def setApplicationName(name: str) -> None:
        pass


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

    def setStyleHint(self, hint: Any) -> None:
        pass

    class StyleHint:
        Monospace = 49


class QKeySequence:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass


class QShortcut(QWidget):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.activated = Signal()


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
    QtGui.QShortcut = QShortcut

    QtWidgets = types.ModuleType("PyQt6.QtWidgets")
    QtWidgets.QApplication = QApplication
    QtWidgets.QCheckBox = QCheckBox
    QtWidgets.QComboBox = QComboBox
    QtWidgets.QDialog = QDialog
    QtWidgets.QDialogButtonBox = QDialogButtonBox
    QtWidgets.QFileDialog = QFileDialog
    QtWidgets.QFormLayout = QFormLayout
    QtWidgets.QGroupBox = QGroupBox
    QtWidgets.QHBoxLayout = QHBoxLayout
    QtWidgets.QLabel = QLabel
    QtWidgets.QLineEdit = QLineEdit
    QtWidgets.QListWidget = QListWidget
    QtWidgets.QListWidgetItem = QListWidgetItem
    QtWidgets.QMainWindow = QMainWindow
    QtWidgets.QMessageBox = QMessageBox
    QtWidgets.QPushButton = QPushButton
    QtWidgets.QSplitter = QSplitter
    QtWidgets.QTextEdit = QTextEdit
    QtWidgets.QVBoxLayout = QVBoxLayout
    QtWidgets.QWidget = QWidget

    for name, module in (
        ("PyQt6", pyqt6),
        ("PyQt6.QtCore", QtCore),
        ("PyQt6.QtGui", QtGui),
        ("PyQt6.QtWidgets", QtWidgets),
    ):
        sys.modules[name] = module
