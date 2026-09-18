#!/usr/bin/env python3
"""
OpenCode Model Manager
GUI para administrar proveedores y modelos de OpenCode.

Características:
- Edita opencode.json sin tocar ~/.local/share/opencode/auth.json.
- Permite cambiar SIEMPRE el ID del modelo y su nombre visible.
- Agrega y elimina modelos.
- Permite cambiar el nombre visible del proveedor.
- Permite seleccionar el modelo predeterminado ("model").
- Permite configurar "small_model".
- Conserva propiedades adicionales de cada modelo.
- Hace una copia de seguridad antes de guardar.
- Recuerda el tamaño y la posición de la ventana entre sesiones.
- Puede abrir un opencode.json existente mediante un selector.
- Detecta automáticamente:
    1. OPENCODE_CONFIG
    2. ./opencode.json
    3. ~/.config/opencode/opencode.json
- Modo global por defecto: edita ~/.config/opencode/opencode.json;
  alternable al modo de repositorio con el checkbox "Modo global".
- Normaliza la clave "providers" a "provider" (formato estable) al cargar.
- No solicita ni almacena API keys.

Requisito:
    pip install PyQt6

Uso:
    python3 opencode_model_manager.py
"""

import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

try:
    from PyQt6.QtCore import Qt, QSettings
    from PyQt6.QtGui import QFont, QKeySequence, QShortcut
    from PyQt6.QtWidgets import (
        QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
        QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
        QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QSplitter,
        QTextEdit, QVBoxLayout, QWidget, QCheckBox
    )
except ImportError:
    print("ERROR: PyQt6 no está instalado.")
    print("Instálalo con: pip install PyQt6")
    sys.exit(1)


APP_NAME = "OpenCode Model Manager"
SCHEMA_URL = "https://opencode.ai/config.json"


def global_config_path():
    """Ruta del opencode.json global de OpenCode.

    Nota: OpenCode también respeta la variable OPENCODE_CONFIG, pero
    en modo global esa variable se ignora deliberadamente porque el
    usuario ha elegido explícitamente trabajar sobre el archivo global.
    """
    return Path.home() / ".config" / "opencode" / "opencode.json"


def discover_config():
    """Busca la configuración de OpenCode según su prioridad habitual."""
    custom = os.environ.get("OPENCODE_CONFIG")
    if custom:
        return Path(custom).expanduser()

    cwd = Path.cwd()
    project = cwd / "opencode.json"
    if project.exists():
        return project

    # Si estamos dentro de un repositorio Git, busca hacia arriba.
    current = cwd
    while current != current.parent:
        candidate = current / "opencode.json"
        if candidate.exists():
            return candidate
        git = current / ".git"
        if git.exists():
            candidate = current / "opencode.json"
            if candidate.exists():
                return candidate
            break
        current = current.parent

    global_config = Path.home() / ".config" / "opencode" / "opencode.json"
    if global_config.exists():
        return global_config

    return project


def file_info(path):
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


def model_display_name(model_id, model_data):
    if isinstance(model_data, dict):
        return model_data.get("name") or model_data.get("modelID") or model_id
    return model_id


class ModelDialog(QDialog):
    """Diálogo para crear/editar un modelo."""

    def __init__(self, parent=None, model_id="", model_data=None, existing_ids=None):
        super().__init__(parent)
        self.setWindowTitle("Editar modelo" if model_data is not None else "Agregar modelo")
        self.setMinimumWidth(620)

        model_data = deepcopy(model_data) if isinstance(model_data, dict) else {}
        existing_ids = set(existing_ids or [])
        self.original_id = model_id

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.id_edit = QLineEdit(model_id)
        self.id_edit.setPlaceholderText("Ej.: deepseek-v4-pro")
        form.addRow("ID del modelo:", self.id_edit)

        self.name_edit = QLineEdit(model_display_name(model_id, model_data))
        self.name_edit.setPlaceholderText("Nombre visible en /models")
        form.addRow("Nombre visible:", self.name_edit)

        # En OpenCode moderno puede existir modelID para mapear una clave local
        # a otro ID enviado al proveedor. Lo mostramos si ya existe.
        self.modelid_edit = QLineEdit(str(model_data.get("modelID", "")))
        self.modelid_edit.setPlaceholderText(
            "Opcional; normalmente déjalo vacío"
        )
        form.addRow("modelID (opcional):", self.modelid_edit)

        layout.addLayout(form)

        note = QLabel(
            "El nombre visible es independiente del ID real. "
            "Puedes cambiar ambos. Las demás propiedades del modelo se conservarán."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; padding: 6px;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate(self):
        model_id = self.id_edit.text().strip()
        name = self.name_edit.text().strip()

        if not model_id:
            QMessageBox.warning(self, "Validación", "El ID del modelo es obligatorio.")
            return
        if not name:
            QMessageBox.warning(
                self, "Validación", "El nombre visible es obligatorio."
            )
            return

        self.accept()

    def get_data(self):
        return (
            self.id_edit.text().strip(),
            self.name_edit.text().strip(),
            self.modelid_edit.text().strip(),
        )


class ProviderDialog(QDialog):
    def __init__(self, parent=None, provider_id="", provider_data=None):
        super().__init__(parent)
        self.setWindowTitle(
            "Editar proveedor" if provider_data is not None else "Agregar proveedor"
        )
        self.setMinimumWidth(600)

        provider_data = deepcopy(provider_data) if isinstance(provider_data, dict) else {}

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.id_edit = QLineEdit(provider_id)
        if provider_data:
            self.id_edit.setReadOnly(True)
        self.id_edit.setPlaceholderText("Ej.: bai")
        form.addRow("ID del proveedor:", self.id_edit)

        self.name_edit = QLineEdit(provider_data.get("name", provider_id))
        self.name_edit.setPlaceholderText("Nombre visible del proveedor")
        form.addRow("Nombre visible:", self.name_edit)

        self.base_edit = QLineEdit(
            provider_data.get("options", {}).get("baseURL", "")
            if isinstance(provider_data.get("options"), dict)
            else ""
        )
        self.base_edit.setPlaceholderText("https://api.example.com/v1")
        form.addRow("Base URL:", self.base_edit)

        self.npm_edit = QLineEdit(
            provider_data.get("npm", "@ai-sdk/openai-compatible")
        )
        form.addRow("AI SDK package:", self.npm_edit)

        layout.addLayout(form)

        note = QLabel(
            "Este editor no modifica credenciales almacenadas por /connect. "
            "Solo modifica la configuración de opencode.json."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #666; padding: 6px;")
        layout.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate(self):
        if not self.id_edit.text().strip():
            QMessageBox.warning(self, "Validación", "El ID del proveedor es obligatorio.")
            return
        if not self.name_edit.text().strip():
            QMessageBox.warning(
                self, "Validación", "El nombre visible es obligatorio."
            )
            return
        if not self.base_edit.text().strip():
            QMessageBox.warning(self, "Validación", "La Base URL es obligatoria.")
            return
        self.accept()

    def get_data(self):
        return {
            "id": self.id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "baseURL": self.base_edit.text().strip(),
            "npm": self.npm_edit.text().strip(),
        }


class OpenCodeModelManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(980, 560)
        self.resize(1120, 720)
        self._fit_to_screen()

        self.settings = QSettings("OpenCodeTools", "OpenCodeModelManager")
        self._restore_window_geometry()

        use_global = self.settings.value("use_global", True, type=bool)
        self.use_global = use_global
        self.config_path = (
            global_config_path() if use_global else discover_config()
        )
        self.data = {}
        self.models = []

        self.build_ui()
        self.setup_shortcuts()
        self.apply_style()
        self.load_config()

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
            x = min(
                max(self.x(), available.left()),
                available.right() - 120,
            )
            y = min(
                max(self.y(), available.top()),
                available.bottom() - 40,
            )
            if (x, y) != (self.x(), self.y()):
                self.move(x, y)

    def _restore_window_geometry(self):
        """Restaura tamaño y posición guardados en la sesión anterior.

        Si no hay geometría guardada (o está corrupta) se conserva la
        que acaba de definirse en __init__. En ambos casos se reencuadra
        al área disponible del monitor actual.
        """
        geometry = self.settings.value("geometry")
        restored = False
        if geometry is not None:
            try:
                restored = self.restoreGeometry(geometry)
            except Exception:
                restored = False
        self._fit_to_screen(clamp_position=restored)

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main = QHBoxLayout(central)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # ---------- LEFT ----------
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Modelos de OpenCode")
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        title.setFont(font)
        left_layout.addWidget(title)

        self.file_label = QLabel()
        self.file_label.setWordWrap(True)
        self.file_label.setStyleSheet("color: #666; font-size: 11px;")
        left_layout.addWidget(self.file_label)

        top_buttons = QHBoxLayout()
        self.open_btn = QPushButton("Abrir opencode.json…")
        self.open_btn.clicked.connect(self.open_config)
        top_buttons.addWidget(self.open_btn)

        self.reload_btn = QPushButton("Recargar")
        self.reload_btn.clicked.connect(self.load_config)
        top_buttons.addWidget(self.reload_btn)

        self.global_check = QCheckBox("Modo global")
        self.global_check.setToolTip(
            "Trabajar siempre sobre ~/.config/opencode/opencode.json "
            "en lugar del opencode.json del repositorio actual."
        )
        self.global_check.stateChanged.connect(self.toggle_global_mode)
        top_buttons.addWidget(self.global_check)

        self.lsp_check = QCheckBox("LSP")
        self.lsp_check.setToolTip(
            "Activa o desactiva los servidores LSP de OpenCode (clave \"lsp\"\n"
            "de opencode.json). Requiere tener instalado el servidor del\n"
            "lenguaje, por ejemplo: npm install -g pyright"
        )
        self.lsp_check.stateChanged.connect(self.toggle_lsp)
        top_buttons.addWidget(self.lsp_check)
        top_buttons.addStretch()
        left_layout.addLayout(top_buttons)

        self.models_list = QListWidget()
        self.models_list.setSpacing(2)
        self.models_list.itemSelectionChanged.connect(self.selection_changed)
        left_layout.addWidget(self.models_list)

        row1 = QHBoxLayout()
        self.add_model_btn = QPushButton("+ Modelo")
        self.add_model_btn.clicked.connect(self.add_model)
        row1.addWidget(self.add_model_btn)

        self.edit_model_btn = QPushButton("Editar")
        self.edit_model_btn.setEnabled(False)
        self.edit_model_btn.clicked.connect(self.edit_model)
        row1.addWidget(self.edit_model_btn)

        left_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.delete_model_btn = QPushButton("Eliminar")
        self.delete_model_btn.setEnabled(False)
        self.delete_model_btn.clicked.connect(self.delete_model)
        row2.addWidget(self.delete_model_btn)

        self.set_default_btn = QPushButton("Usar como predeterminado")
        self.set_default_btn.setEnabled(False)
        self.set_default_btn.clicked.connect(self.set_default_model)
        row2.addWidget(self.set_default_btn)
        left_layout.addLayout(row2)

        provider_group = QGroupBox("Proveedor")
        provider_layout = QVBoxLayout(provider_group)

        self.provider_combo = QComboBox()
        self.provider_combo.currentIndexChanged.connect(self.provider_changed)
        provider_layout.addWidget(self.provider_combo)

        prow = QHBoxLayout()
        self.add_provider_btn = QPushButton("+ Proveedor")
        self.add_provider_btn.clicked.connect(self.add_provider)
        prow.addWidget(self.add_provider_btn)

        self.edit_provider_btn = QPushButton("Editar proveedor")
        self.edit_provider_btn.clicked.connect(self.edit_provider)
        prow.addWidget(self.edit_provider_btn)
        provider_layout.addLayout(prow)

        left_layout.addWidget(provider_group)

        default_group = QGroupBox("Modelos predeterminados")
        default_layout = QFormLayout(default_group)

        self.default_combo = QComboBox()
        self.default_combo.setEditable(False)
        default_layout.addRow("model:", self.default_combo)

        self.small_combo = QComboBox()
        default_layout.addRow("small_model:", self.small_combo)

        self.apply_defaults_btn = QPushButton("Aplicar predeterminados")
        self.apply_defaults_btn.clicked.connect(self.apply_defaults)
        default_layout.addRow(self.apply_defaults_btn)

        left_layout.addWidget(default_group)

        self.save_btn = QPushButton("Guardar cambios")
        self.save_btn.clicked.connect(self.save_config)
        left_layout.addWidget(self.save_btn)

        self.backup_btn = QPushButton("Crear copia de seguridad")
        self.backup_btn.clicked.connect(self.create_backup)
        left_layout.addWidget(self.backup_btn)

        # ---------- RIGHT ----------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        details = QGroupBox("Modelo seleccionado")
        details_layout = QVBoxLayout(details)

        self.detail_id = QLabel("Selecciona un modelo")
        self.detail_name = QLabel("")
        self.detail_provider = QLabel("")
        self.detail_base = QLabel("")
        self.detail_default = QLabel("")

        for label in (
            self.detail_id,
            self.detail_name,
            self.detail_provider,
            self.detail_base,
            self.detail_default,
        ):
            label.setWordWrap(True)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            details_layout.addWidget(label)

        right_layout.addWidget(details)

        info = QGroupBox("Credenciales")
        info_layout = QVBoxLayout(info)
        cred_label = QLabel(
            "OpenCode guarda las credenciales de /connect por separado. "
            "Este programa NO lee, muestra ni modifica la API key. "
            "Por eso puedes cambiar los modelos sin volver a introducir la clave."
        )
        cred_label.setWordWrap(True)
        info_layout.addWidget(cred_label)
        right_layout.addWidget(info)

        preview = QGroupBox("Vista previa de opencode.json")
        preview_layout = QVBoxLayout(preview)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        mono = QFont("Monospace", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.preview.setFont(mono)
        preview_layout.addWidget(self.preview)
        right_layout.addWidget(preview)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([500, 620])
        main.addWidget(splitter)

        self.statusBar().showMessage("Listo.")

        # Sincroniza los checkboxes con la configuración cargada sin
        # disparar señales (los datos llegan vía load_config()).
        self.global_check.blockSignals(True)
        self.global_check.setChecked(self.use_global)
        self.global_check.blockSignals(False)

        self.lsp_check.blockSignals(True)
        self.lsp_check.setChecked(bool(self.data.get("lsp")))
        self.lsp_check.blockSignals(False)

    def toggle_lsp(self, state):
        """Activa o desactiva la clave "lsp" de opencode.json."""
        enabled = state == Qt.CheckState.Checked.value
        if enabled:
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

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.open_config)
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self.load_config)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_config)
        QShortcut(QKeySequence("Delete"), self).activated.connect(self.delete_model)

    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #f5f6fa; }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #dcdde1;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 8px;
                background: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #2f3640;
            }
            QListWidget {
                background: #ffffff;
                border: 1px solid #dcdde1;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 5px 10px;
                border-radius: 6px;
                margin-bottom: 2px;
            }
            QListWidget::item:selected {
                background: #0984e3;
                color: white;
            }
            QPushButton {
                background: #0984e3;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 4px 10px;
                font-weight: bold;
            }
            QPushButton:hover { background: #0770c2; }
            QPushButton:disabled {
                background: #b2bec3;
                color: #636e72;
            }
            QTextEdit {
                background: #2d3436;
                color: #dfe6e9;
                border-radius: 6px;
                padding: 6px;
            }
            QLineEdit, QComboBox {
                border: 1px solid #dcdde1;
                border-radius: 4px;
                padding: 4px 6px;
            }
        """)
        self.save_btn.setStyleSheet(
            "QPushButton { background: #00b894; color: white; }"
            "QPushButton:hover { background: #00a381; }"
        )
        self.delete_model_btn.setStyleSheet(
            "QPushButton { background: #d63031; color: white; }"
            "QPushButton:hover { background: #b71515; }"
            "QPushButton:disabled { background: #b2bec3; color: #636e72; }"
        )

    def load_config(self):
        path = self.config_path

        if not path.exists():
            # Crear una configuración inicial solo después de confirmación.
            reply = QMessageBox.question(
                self,
                "Archivo no encontrado",
                f"No existe:\n{path}\n\n¿Quieres crear un opencode.json básico?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.data = {"$schema": SCHEMA_URL, "provider": {}}
                self.refresh()
            else:
                self.statusBar().showMessage("Archivo no encontrado.")
            return

        try:
            with path.open("r", encoding="utf-8") as f:
                self.data = json.load(f)
        except json.JSONDecodeError as e:
            QMessageBox.critical(
                self,
                "JSON inválido",
                f"No se pudo leer {path}.\n\nError:\n{e}",
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

        # Sincroniza el checkbox LSP con la clave "lsp" del archivo.
        self.lsp_check.blockSignals(True)
        self.lsp_check.setChecked(bool(self.data.get("lsp")))
        self.lsp_check.blockSignals(False)

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

        self.refresh()
        self.statusBar().showMessage(f"Cargado: {path}")

    def refresh(self):
        size, mtime = file_info(self.config_path)
        self.file_label.setText(
            f"Archivo: {self.config_path}\n"
            f"Tamaño: {size} | Modificado: {mtime}"
        )

        self.refresh_provider_combo()
        self.refresh_models()
        self.refresh_defaults()
        self.preview.setPlainText(
            json.dumps(self.data, indent=2, ensure_ascii=False)
        )

    def providers(self):
        if not isinstance(self.data.get("provider"), dict):
            self.data["provider"] = {}
        return self.data["provider"]

    def current_provider_id(self):
        return self.provider_combo.currentData()

    def refresh_provider_combo(self):
        current = self.current_provider_id()
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()

        for pid, pdata in self.providers().items():
            pname = pdata.get("name", pid) if isinstance(pdata, dict) else pid
            self.provider_combo.addItem(f"{pname}  [{pid}]", pid)

        if current:
            idx = self.provider_combo.findData(current)
            if idx >= 0:
                self.provider_combo.setCurrentIndex(idx)

        self.provider_combo.blockSignals(False)

    def provider_changed(self):
        self.refresh_models()

    def refresh_models(self):
        self.models_list.clear()
        self.models = []

        pid = self.current_provider_id()
        if not pid:
            self.selection_changed()
            return

        pdata = self.providers().get(pid, {})
        if not isinstance(pdata, dict):
            return

        models = pdata.get("models", {})
        if not isinstance(models, dict):
            models = {}
            pdata["models"] = models

        for model_id, model_data in models.items():
            if not isinstance(model_data, dict):
                model_data = {}
            self.models.append((model_id, model_data))

            visible = model_display_name(model_id, model_data)
            model_id_sent = model_data.get("modelID", "")
            suffix = f"  → {model_id_sent}" if model_id_sent else ""

            item = QListWidgetItem(f"{visible}\n    ID: {model_id}{suffix}")
            item.setData(Qt.ItemDataRole.UserRole, model_id)
            self.models_list.addItem(item)

        self.selection_changed()

    def selection_changed(self):
        selected = self.models_list.selectedItems()
        enabled = bool(selected)

        self.edit_model_btn.setEnabled(enabled)
        self.delete_model_btn.setEnabled(enabled)
        self.set_default_btn.setEnabled(enabled)

        if not selected:
            self.detail_id.setText("Selecciona un modelo")
            self.detail_name.setText("")
            self.detail_provider.setText("")
            self.detail_base.setText("")
            self.detail_default.setText("")
            return

        model_id = selected[0].data(Qt.ItemDataRole.UserRole)
        pid = self.current_provider_id()
        pdata = self.providers().get(pid, {})
        model_data = pdata.get("models", {}).get(model_id, {})

        name = model_display_name(model_id, model_data)
        base = (
            pdata.get("options", {}).get("baseURL", "")
            if isinstance(pdata.get("options"), dict)
            else ""
        )

        self.detail_id.setText(f"<b>ID:</b> {model_id}")
        self.detail_name.setText(f"<b>Nombre visible:</b> {name}")
        self.detail_provider.setText(
            f"<b>Proveedor:</b> {pdata.get('name', pid)} [{pid}]"
        )
        self.detail_base.setText(f"<b>Base URL:</b> {base}")

        full_id = f"{pid}/{model_id}"
        current_default = self.data.get("model", "")
        current_small = self.data.get("small_model", "")
        if current_default == full_id:
            status = "Modelo predeterminado: SÍ"
        elif current_small == full_id:
            status = "small_model: SÍ"
        else:
            status = "Modelo predeterminado: NO"
        self.detail_default.setText(status)

    def add_model(self):
        pid = self.current_provider_id()
        if not pid:
            QMessageBox.warning(
                self, "Sin proveedor",
                "Primero crea o selecciona un proveedor."
            )
            return

        pdata = self.providers()[pid]
        models = pdata.setdefault("models", {})
        if not isinstance(models, dict):
            pdata["models"] = {}
            models = pdata["models"]

        dlg = ModelDialog(self, existing_ids=models.keys())
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        model_id, name, modelid = dlg.get_data()
        if model_id in models:
            QMessageBox.warning(
                self, "ID duplicado",
                f"Ya existe el modelo:\n{model_id}"
            )
            return

        model_data = {"name": name}
        if modelid:
            model_data["modelID"] = modelid

        models[model_id] = model_data
        self.refresh()
        self.select_model(model_id)

    def edit_model(self):
        selected = self.models_list.selectedItems()
        pid = self.current_provider_id()
        if not selected or not pid:
            return

        old_id = selected[0].data(Qt.ItemDataRole.UserRole)
        pdata = self.providers()[pid]
        models = pdata.get("models", {})
        old_data = models.get(old_id, {})

        dlg = ModelDialog(
            self,
            model_id=old_id,
            model_data=old_data,
            existing_ids=models.keys(),
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_id, name, modelid = dlg.get_data()

        if new_id != old_id and new_id in models:
            QMessageBox.warning(
                self, "ID duplicado",
                f"Ya existe otro modelo con el ID:\n{new_id}"
            )
            return

        # Conserva cualquier propiedad adicional (limit, options, variants, etc.).
        new_data = deepcopy(old_data)
        new_data["name"] = name

        if modelid:
            new_data["modelID"] = modelid
        else:
            new_data.pop("modelID", None)

        if new_id != old_id:
            models[new_id] = new_data
            del models[old_id]
            self.update_default_references(pid, old_id, new_id)

        self.refresh()
        self.select_model(new_id)

    def update_default_references(self, pid, old_id, new_id):
        old_full = f"{pid}/{old_id}"
        new_full = f"{pid}/{new_id}"

        if self.data.get("model") == old_full:
            self.data["model"] = new_full
        if self.data.get("small_model") == old_full:
            self.data["small_model"] = new_full

    def delete_model(self):
        selected = self.models_list.selectedItems()
        pid = self.current_provider_id()
        if not selected or not pid:
            return

        model_id = selected[0].data(Qt.ItemDataRole.UserRole)
        pdata = self.providers()[pid]
        model_data = pdata.get("models", {}).get(model_id, {})
        name = model_display_name(model_id, model_data)

        reply = QMessageBox.question(
            self,
            "Confirmar eliminación",
            f"¿Eliminar este modelo de opencode.json?\n\n"
            f"Nombre: {name}\n"
            f"ID: {model_id}\n\n"
            f"La credencial de /connect NO será tocada.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        pdata["models"].pop(model_id, None)
        full = f"{pid}/{model_id}"
        if self.data.get("model") == full:
            self.data.pop("model", None)
        if self.data.get("small_model") == full:
            self.data.pop("small_model", None)

        self.refresh()

    def set_default_model(self):
        selected = self.models_list.selectedItems()
        pid = self.current_provider_id()
        if not selected or not pid:
            return
        model_id = selected[0].data(Qt.ItemDataRole.UserRole)
        self.data["model"] = f"{pid}/{model_id}"
        self.refresh()
        self.select_model(model_id)

    def refresh_defaults(self):
        all_models = []
        for pid, pdata in self.providers().items():
            if not isinstance(pdata, dict):
                continue
            models = pdata.get("models", {})
            if not isinstance(models, dict):
                continue
            for mid, mdata in models.items():
                name = model_display_name(mid, mdata)
                all_models.append((f"{name}  [{pid}/{mid}]", f"{pid}/{mid}"))

        self.default_combo.blockSignals(True)
        self.small_combo.blockSignals(True)
        self.default_combo.clear()
        self.small_combo.clear()

        self.default_combo.addItem("(sin modelo predeterminado)", "")
        self.small_combo.addItem("(automático)", "")

        for label, full_id in all_models:
            self.default_combo.addItem(label, full_id)
            self.small_combo.addItem(label, full_id)

        current = self.data.get("model", "")
        idx = self.default_combo.findData(current)
        if idx >= 0:
            self.default_combo.setCurrentIndex(idx)

        small = self.data.get("small_model", "")
        idx = self.small_combo.findData(small)
        if idx >= 0:
            self.small_combo.setCurrentIndex(idx)

        self.default_combo.blockSignals(False)
        self.small_combo.blockSignals(False)

    def apply_defaults(self):
        default = self.default_combo.currentData()
        small = self.small_combo.currentData()

        if default:
            self.data["model"] = default
        else:
            self.data.pop("model", None)

        if small:
            self.data["small_model"] = small
        else:
            self.data.pop("small_model", None)

        self.refresh()
        self.statusBar().showMessage("Predeterminados actualizados (aún no guardados).")

    def add_provider(self):
        dlg = ProviderDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        d = dlg.get_data()
        providers = self.providers()

        if d["id"] in providers:
            QMessageBox.warning(
                self, "Proveedor existente",
                f"Ya existe el proveedor:\n{d['id']}"
            )
            return

        providers[d["id"]] = {
            "npm": d["npm"],
            "name": d["name"],
            "options": {"baseURL": d["baseURL"]},
            "models": {},
        }
        self.refresh_provider_combo()
        idx = self.provider_combo.findData(d["id"])
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)
        self.refresh()

    def edit_provider(self):
        pid = self.current_provider_id()
        if not pid:
            return

        pdata = self.providers()[pid]
        dlg = ProviderDialog(self, pid, pdata)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        d = dlg.get_data()
        pdata["name"] = d["name"]
        pdata["npm"] = d["npm"]
        pdata.setdefault("options", {})["baseURL"] = d["baseURL"]

        self.refresh()
        self.statusBar().showMessage("Proveedor actualizado (aún no guardado).")

    def select_model(self, model_id):
        for i in range(self.models_list.count()):
            item = self.models_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == model_id:
                self.models_list.setCurrentItem(item)
                break

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

    def create_backup(self):
        if not self.config_path.exists():
            QMessageBox.warning(
                self, "Sin archivo",
                "No existe un archivo para respaldar."
            )
            return

        backup_dir = self.config_path.parent / "opencode-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = backup_dir / f"{self.config_path.stem}_{timestamp}.json"

        try:
            shutil.copy2(self.config_path, backup)
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo crear la copia:\n{e}"
            )
            return

        QMessageBox.information(
            self, "Copia creada",
            f"Backup guardado en:\n\n{backup}"
        )

    def save_config(self, quiet: bool = False):
        try:
            json_text = json.dumps(
                self.data, indent=2, ensure_ascii=False
            )
            json.loads(json_text)
        except Exception as e:
            QMessageBox.critical(
                self, "JSON inválido",
                f"No se puede guardar la configuración:\n{e}"
            )
            return

        if self.config_path.exists():
            backup = self.config_path.with_suffix(
                self.config_path.suffix + ".backup"
            )
            try:
                shutil.copy2(self.config_path, backup)
            except Exception:
                pass

        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config_path.open("w", encoding="utf-8") as f:
                f.write(json_text)
                f.write("\n")
        except Exception as e:
            QMessageBox.critical(
                self, "Error al guardar",
                f"No se pudo guardar:\n{e}"
            )
            return

        self.refresh()
        if quiet:
            self.statusBar().showMessage(
                f"Guardado: {self.config_path}"
            )
            return

        QMessageBox.information(
            self,
            "Guardado",
            "opencode.json se guardó correctamente.\n\n"
            "La API key almacenada por /connect no fue modificada."
        )

    def closeEvent(self, event):
        """Guarda tamaño y posición de la ventana para la próxima sesión."""
        self.settings.setValue("geometry", self.saveGeometry())
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(APP_NAME)

    window = OpenCodeModelManager()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
