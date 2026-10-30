"""Diálogos de alta/edición.

ProviderDialog: formulario guiado con protocolo, SDK, auth por variable de
entorno, cabeceras personalizadas, modelos iniciales y pestaña de
importación JSON validada. NUNCA pide ni guarda API keys: OpenCode las
gestiona aparte con /connect.

ModelDialog: nombre visible, ID y modelID (conserva el resto de propiedades).
PreviewDialog: vista previa del opencode.json resultante.
"""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)

from omm.catalog import PROTOCOL_LABELS, normalize_base_url, resolve_protocol
from omm.registry import validate_provider_spec

DEFAULT_NPM = "@ai-sdk/openai-compatible"

PROTOCOL_DEFAULT_NPM = {
    "openai-compatible": "@ai-sdk/openai-compatible",
    "openai": "@ai-sdk/openai",
    "anthropic": "@ai-sdk/anthropic",
    "google": "@ai-sdk/google",
    "azure": "@ai-sdk/azure",
    "bedrock": "@ai-sdk/amazon-bedrock",
    "other": DEFAULT_NPM,
}

KNOWN_ADAPTERS = (
    "@ai-sdk/openai-compatible",
    "@ai-sdk/openai",
    "@ai-sdk/anthropic",
    "@ai-sdk/google",
    "@ai-sdk/google-vertex",
    "@ai-sdk/azure",
    "@ai-sdk/amazon-bedrock",
    "@ai-sdk/cohere",
    "@ai-sdk/mistral",
    "@ai-sdk/perplexity",
    "@openrouter/ai-sdk-provider",
)


class ProviderDialog(QDialog):
    """Alta/edición guiada de un proveedor externo de OpenCode."""

    def __init__(
        self,
        parent=None,
        provider_id: str = "",
        provider_data: dict | None = None,
        existing_ids=(),
    ):
        super().__init__(parent)
        self.editing = provider_data is not None
        self.setWindowTitle("Editar proveedor" if self.editing else "Agregar proveedor")
        self.setMinimumWidth(680)
        self._existing_ids = set(existing_ids)
        self._provider_data = dict(provider_data or {})

        root = QVBoxLayout(self)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        # ---- pestaña Formulario ----
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(14, 14, 14, 8)
        form.setSpacing(8)

        self.id_edit = QLineEdit(provider_id)
        self.id_edit.setPlaceholderText("Ej.: bai  (debe coincidir con el ID usado en /connect)")
        if self.editing:
            self.id_edit.setReadOnly(True)
        form.addRow("ID del proveedor *", self.id_edit)

        self.name_edit = QLineEdit(str(self._provider_data.get("name", provider_id)))
        self.name_edit.setPlaceholderText("Nombre visible en OpenCode")
        form.addRow("Nombre visible *", self.name_edit)

        options = self._provider_data.get("options")
        options = options if isinstance(options, dict) else {}
        self.base_edit = QLineEdit(str(options.get("baseURL", "")))
        self.base_edit.setPlaceholderText("https://api.example.com/v1")
        form.addRow("API Base URL *", self.base_edit)

        self.protocol_combo = QComboBox()
        for key, label in PROTOCOL_LABELS.items():
            self.protocol_combo.addItem(label, key)
        current_protocol = resolve_protocol(
            str(self._provider_data.get("npm", "")),
            str(options.get("baseURL", "")) or None,
        )
        idx = self.protocol_combo.findData(current_protocol)
        if idx >= 0:
            self.protocol_combo.setCurrentIndex(idx)
        self.protocol_combo.setToolTip(
            "Define qué adapter del AI SDK se usará. «OpenAI-compatible» sirve\n"
            "para la mayoría de APIs externas (/v1/chat/completions)."
        )
        self.protocol_combo.currentIndexChanged.connect(self._protocol_changed)
        form.addRow("Protocolo de API", self.protocol_combo)

        self.npm_edit = QComboBox()
        self.npm_edit.setEditable(True)
        self.npm_edit.addItems(KNOWN_ADAPTERS)
        self.npm_edit.setCurrentText(
            str(self._provider_data.get("npm", DEFAULT_NPM))
        )
        self.npm_edit.setToolTip("Paquete AI SDK que instalará/invocará OpenCode.")
        form.addRow("Paquete AI SDK (npm)", self.npm_edit)

        env_list = self._provider_data.get("env")
        env_first = ""
        if isinstance(env_list, list) and env_list:
            env_first = str(env_list[0])
        self.env_edit = QLineEdit(env_first)
        self.env_edit.setPlaceholderText("Ej.: MYPROVIDER_API_KEY (nombre de variable; vacío = /connect)")
        self.env_edit.setToolTip(
            "OpenCode tomará la API key de esta variable de entorno o de\n"
            "/connect. Este diálogo NUNCA pide ni guarda claves."
        )
        form.addRow("Variable de entorno para la API key", self.env_edit)

        headers = options.get("headers")
        header_text = ""
        if isinstance(headers, dict):
            header_text = "\n".join(f"{k}: {v}" for k, v in headers.items())
        self.headers_edit = QPlainTextEdit(header_text)
        self.headers_edit.setPlaceholderText(
            "Opcional, una cabecera por línea — Cabecera: valor"
        )
        self.headers_edit.setFixedHeight(72)
        form.addRow("Cabeceras HTTP personalizadas", self.headers_edit)

        self.models_edit = QPlainTextEdit()
        existing_models = self._provider_data.get("models")
        if isinstance(existing_models, dict):
            self.models_edit.setPlainText("\n".join(
                f"{mid}|{mdata.get('name')}" if isinstance(mdata, dict) and mdata.get("name") else mid
                for mid, mdata in existing_models.items()
            ))
        self.models_edit.setPlaceholderText(
            "Opcional. ID de modelo por línea; nombre con «id|Nombre»."
        )
        self.models_edit.setFixedHeight(84)
        form.addRow("Modelos iniciales", self.models_edit)

        note = QLabel(
            "Las credenciales se gestionan aparte: usa /connect en OpenCode o la\n"
            "variable de entorno indicada. Esta herramienta no lee auth.json."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        form.addRow(note)
        self.tabs.addTab(form_widget, "Formulario")

        # ---- pestaña Importar JSON ----
        import_widget = QWidget()
        import_layout = QVBoxLayout(import_widget)
        import_layout.setContentsMargins(14, 14, 14, 8)
        info = QLabel(
            "Pega un JSON de proveedor (bloque `\"provider\": { \"<id>\": … }` de\n"
            "opencode.json, o el objeto del proveedor directamente con \"id\").\n"
            "Se valida antes de aceptarlo; nada se instala ni se ejecuta."
        )
        info.setObjectName("mutedLabel")
        import_layout.addWidget(info)
        self.json_edit = QPlainTextEdit()
        mono = QFont("Monospace", 10)
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        self.json_edit.setFont(mono)
        import_layout.addWidget(self.json_edit)
        btns = QHBoxLayout()
        self.validate_btn = QPushButton("Validar")
        self.validate_btn.clicked.connect(self._validate_import)
        self.apply_btn = QPushButton("Aplicar al formulario")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply_import)
        btns.addWidget(self.validate_btn)
        btns.addWidget(self.apply_btn)
        btns.addStretch()
        import_layout.addLayout(btns)
        self.import_msg = QLabel("")
        self.import_msg.setWordWrap(True)
        self.import_msg.setObjectName("mutedLabel")
        import_layout.addWidget(self.import_msg)
        self._imported: dict | None = None
        self.tabs.addTab(import_widget, "Importar JSON")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ------------------------------------------------------------------
    def _protocol_changed(self, _index: int) -> None:
        key = self.protocol_combo.currentData()
        self.npm_edit.setCurrentText(PROTOCOL_DEFAULT_NPM.get(key, DEFAULT_NPM))

    def _validate_import(self) -> None:
        text = self.json_edit.toPlainText().strip()
        if not text:
            self.import_msg.setText("Pega primero un JSON.")
            self._imported = None
            self.apply_btn.setEnabled(False)
            return
        try:
            payload = json.loads(text)
        except ValueError as exc:
            self.import_msg.setText(f"JSON inválido: {exc}")
            self._imported = None
            self.apply_btn.setEnabled(False)
            return
        spec = _spec_from_payload(payload)
        if spec is None:
            self.import_msg.setText(
                "No se reconoció un proveedor: usa {\"id\": …} directo o\n"
                "{\"<pid>\": {…}} / {\"provider\": {\"<pid>\": {…}}}."
            )
            self._imported = None
            self.apply_btn.setEnabled(False)
            return
        errors = validate_provider_spec(spec)
        if errors:
            self.import_msg.setText("Errores:\n• " + "\n• ".join(errors))
            self._imported = None
            self.apply_btn.setEnabled(False)
            return
        self._imported = spec
        self.import_msg.setText(
            f"Válido: «{spec['id']}» con "
            f"{len(spec.get('models') or {}) } modelo(s)."
        )
        self.apply_btn.setEnabled(True)

    def _apply_import(self) -> None:
        if not self._imported:
            return
        spec = self._imported
        self.id_edit.setText(spec["id"])
        self.name_edit.setText(spec.get("name", spec["id"]))
        self.base_edit.setText(spec.get("baseURL", ""))
        self.npm_edit.setCurrentText(spec.get("npm") or DEFAULT_NPM)
        idx = self.protocol_combo.findData(
            resolve_protocol(spec.get("npm"), spec.get("baseURL"))
        )
        if idx >= 0:
            self.protocol_combo.setCurrentIndex(idx)
        if spec.get("env"):
            self.env_edit.setText(", ".join(spec["env"]))
        headers = spec.get("headers") or {}
        self.headers_edit.setPlainText(
            "\n".join(f"{k}: {v}" for k, v in headers.items())
        )
        models = spec.get("models") or {}
        if isinstance(models, dict):
            self.models_edit.setPlainText("\n".join(
                f"{mid}|{mdata.get('name')}"
                if isinstance(mdata, dict) and mdata.get("name") else mid
                for mid, mdata in models.items()
            ))
        self.tabs.setCurrentIndex(0)

    # ------------------------------------------------------------------
    def validate(self) -> None:
        spec = self.get_spec()
        errors = self.errors_for(spec)
        if spec["id"] and not self.editing and spec["id"] in self._existing_ids:
            errors.append(f"Ya existe un proveedor registrado con el ID «{spec['id']}».")
        if errors:
            QMessageBox.warning(
                self, "Validación",
                "Revisa la definición:\n\n• " + "\n• ".join(errors),
            )
            return
        self.accept()

    def get_spec(self) -> dict:
        """Recoge el estado del formulario como un spec validable."""
        headers: dict[str, str] = {}
        header_errors: list[str] = []
        for line in self.headers_edit.toPlainText().splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" not in line:
                header_errors.append(f"Cabecera sin «: » → {line!r}")
                continue
            key, _, value = line.partition(":")
            headers[key.strip()] = value.strip()

        models: dict[str, dict] = {}
        model_errors: list[str] = []
        for line in self.models_edit.toPlainText().splitlines():
            line = line.strip()
            if not line:
                continue
            if "|" in line:
                mid, _, display = line.partition("|")
                models[mid.strip()] = {"name": display.strip() or mid.strip()}
            else:
                models[line] = {"name": line}

        env = [
            part.strip()
            for part in self.env_edit.text().replace(";", ",").split(",")
            if part.strip()
        ]
        base = self.base_edit.text().strip()
        spec = {
            "id": self.id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "npm": self.npm_edit.currentText().strip(),
            "baseURL": base,
            "protocol": self.protocol_combo.currentData(),
            "env": env,
            "headers": headers,
            "models": models,
            "_header_errors": header_errors,
        }
        return spec

    def errors_for(self, spec: dict) -> list[str]:
        errors = list(spec.get("_header_errors", []))
        errors.extend(validate_provider_spec(spec))
        base = normalize_base_url(spec.get("baseURL", ""))
        if not base:
            errors.append("La Base URL es obligatoria y debe ser http(s) válida.")
        if not spec.get("name"):
            errors.append("El nombre visible es obligatorio.")
        return errors


class ModelDialog(QDialog):
    """Edición de un modelo registrado: ID, nombre visible, modelID y límites."""

    def __init__(self, parent=None, model_id="", model_data=None, existing_ids=None):
        super().__init__(parent)
        from copy import deepcopy
        self.setWindowTitle("Editar modelo" if model_data is not None else "Agregar modelo")
        self.setMinimumWidth(640)
        model_data = deepcopy(model_data) if isinstance(model_data, dict) else {}
        self._original = model_data
        self._existing = set(existing_ids or [])
        self._original_id = model_id

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.id_edit = QLineEdit(model_id)
        self.id_edit.setPlaceholderText("Ej.: deepseek-v4-flash")
        form.addRow("ID del modelo *", self.id_edit)

        name = str(model_data.get("name") or model_id)
        self.name_edit = QLineEdit(name)
        self.name_edit.setPlaceholderText("Nombre visible en /models")
        form.addRow("Nombre visible *", self.name_edit)

        self.modelid_edit = QLineEdit(str(model_data.get("modelID", "") or ""))
        self.modelid_edit.setPlaceholderText("Opcional: ID real enviado al proveedor")
        self.modelid_edit.setToolTip(
            "«modelID» mapea la clave local a otro ID enviado al proveedor.\n"
            "Normalmente déjalo vacío."
        )
        form.addRow("modelID", self.modelid_edit)

        limit = model_data.get("limit") if isinstance(model_data.get("limit"), dict) else {}
        self.ctx_edit = QLineEdit(str(limit.get("context", "") or ""))
        self.ctx_edit.setPlaceholderText("Ej.: 128000")
        form.addRow("Contexto (tokens)", self.ctx_edit)

        self.out_edit = QLineEdit(str(limit.get("output", "") or ""))
        self.out_edit.setPlaceholderText("Ej.: 8192")
        form.addRow("Salida máx. (tokens)", self.out_edit)

        root.addLayout(form)

        note = QLabel(
            "Se conservan el resto de propiedades del modelo (cost, options,\n"
            "headers, variants…). No se tocan credenciales."
        )
        note.setObjectName("mutedLabel")
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _numeric(self, edit: QLineEdit, label: str, errors: list[str]) -> int | None:
        text = edit.text().strip()
        if not text:
            return None
        try:
            value = int(text.replace("_", "").replace(" ", ""))
        except ValueError:
            errors.append(f"«{label}» debe ser un número de tokens: {text!r}")
            return None
        if value <= 0:
            errors.append(f"«{label}» debe ser mayor que 0.")
            return None
        return value

    def validate(self) -> None:
        errors: list[str] = []
        model_id = self.id_edit.text().strip()
        if not model_id:
            errors.append("El ID del modelo es obligatorio.")
        if not self.name_edit.text().strip():
            errors.append("El nombre visible es obligatorio.")
        self._numeric(self.ctx_edit, "Contexto", errors)
        self._numeric(self.out_edit, "Salida máx.", errors)
        if errors:
            QMessageBox.warning(self, "Validación", "\n".join(f"• {e}" for e in errors))
            return
        self.accept()

    def get_data(self) -> tuple[str, str, str, dict]:
        """(model_id, name, modelID, limit) — limit puede venir vacío."""
        limit: dict[str, int] = {}
        ctx = self._numeric(self.ctx_edit, "Contexto", [])
        out = self._numeric(self.out_edit, "Salida máx.", [])
        if ctx:
            limit["context"] = ctx
        if out:
            limit["output"] = out
        return (
            self.id_edit.text().strip(),
            self.name_edit.text().strip(),
            self.modelid_edit.text().strip(),
            limit,
        )


class PreviewDialog(QDialog):
    """Vista previa del JSON resultante antes de guardar."""

    def __init__(self, parent=None, data: dict | None = None, path_note: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Vista previa de opencode.json")
        self.resize(760, 640)
        root = QVBoxLayout(self)
        if path_note:
            label = QLabel(path_note)
            label.setObjectName("mutedLabel")
            root.addWidget(label)
        self.view = QTextEdit()
        self.view.setReadOnly(True)
        mono = QFont("Monospace", 10)
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        self.view.setFont(mono)
        try:
            self.view.setPlainText(
                json.dumps(data or {}, indent=2, ensure_ascii=False)
            )
        except (TypeError, ValueError) as exc:
            self.view.setPlainText(f"(no serializable: {exc})")
        root.addWidget(self.view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)


def _spec_from_payload(payload):
    """Normaliza formas aceptadas de importación a un spec validable."""
    if not isinstance(payload, dict):
        return None
    if "provider" in payload and isinstance(payload["provider"], dict):
        payload = payload["provider"]
    if "id" in payload and isinstance(payload.get("id"), str):
        base = dict(payload)
    elif len(payload) == 1:
        (pid, pdata), = payload.items()
        if not isinstance(pdata, dict):
            return None
        base = {**pdata, "id": pid}
    else:
        return None
    options = base.get("options") if isinstance(base.get("options"), dict) else {}
    headers = base.get("headers")
    if not isinstance(headers, dict):
        headers = options.get("headers") if isinstance(options.get("headers"), dict) else {}
    models = base.get("models")
    if isinstance(models, dict):
        models = {
            str(k): (v if isinstance(v, dict) else {"name": str(v)})
            for k, v in models.items()
        }
    return {
        "id": str(base.get("id") or ""),
        "name": str(base.get("name") or base.get("id") or ""),
        "npm": str(base.get("npm") or base.get("package") or DEFAULT_NPM),
        "baseURL": str(options.get("baseURL") or base.get("api") or ""),
        "env": [str(e) for e in base.get("env", []) if isinstance(e, str)]
        if isinstance(base.get("env"), list) else [],
        "headers": {
            str(k): str(v)
            for k, v in headers.items()
            if isinstance(v, str)
        },
        "models": models or {},
    }
