"""Catálogo de proveedores y modelos de IA.

Separado de la configuración real de OpenCode (opencode.json): el catálogo
describe qué proveedores y modelos EXISTEN; la configuración describe qué
está REGISTRADO. Ninguna entrada del catálogo se escribe en opencode.json
por aparecer en resultados de búsqueda.

Fuentes:
  - Catálogo semilla incluido (curado, funciona sin Internet).
  - Models.dev (https://models.dev/api.json), licencia MIT, datos de
    proveedores y modelos con límites, precios y capacidades.

La última descarga se cachea en disco para navegación offline. El parsing
y la red nunca se ejecutan en el hilo GUI (ver omm/workers.py).

Este módulo NO importa PyQt: es lógica pura, testeable en headless.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import urllib.error
import urllib.request
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

MODELS_DEV_URL = "https://models.dev/api.json"
MODELS_DEV_LICENSE = "MIT (sst/models.dev)"
CATALOG_APP = "opencode-model-manager"
FETCH_TIMEOUT_SECONDS = 30
USER_AGENT = "OpenCodeModelManager/2.0 (+https://github.com/wachin)"

# Protocolos de API reconocidos → paquete AI SDK habitual en OpenCode.
PROTOCOL_LABELS = {
    "openai-compatible": "OpenAI-compatible (/v1/chat/completions)",
    "openai": "OpenAI",
    "anthropic": "Anthropic (Messages)",
    "google": "Google (Gemini)",
    "azure": "Azure OpenAI",
    "bedrock": "AWS Bedrock",
    "other": "Otro / específico del SDK",
}

NPM_TO_PROTOCOL = {
    "@ai-sdk/openai-compatible": "openai-compatible",
    "@ai-sdk/openai": "openai",
    "@ai-sdk/azure": "azure",
    "@ai-sdk/anthropic": "anthropic",
    "@ai-sdk/google": "google",
    "@ai-sdk/google-vertex": "google",
    "@aws-sdk/client-bedrock-runtime": "bedrock",
    "@ai-sdk/amazon-bedrock": "bedrock",
}


def resolve_protocol(npm: str | None, base_url: str | None = None) -> str:
    """Clasifica un proveedor por su paquete AI SDK (y URL como pista)."""
    if npm:
        exact = NPM_TO_PROTOCOL.get(npm)
        if exact:
            return exact
        lowered = npm.lower()
        if "openai" in lowered:
            return "openai-compatible"
        if "anthropic" in lowered or "claude" in lowered:
            return "anthropic"
        if "google" in lowered or "gemini" in lowered:
            return "google"
        if "bedrock" in lowered:
            return "bedrock"
        if "azure" in lowered:
            return "azure"
    if base_url and is_local_url(base_url):
        return "openai-compatible"
    return "other"


def is_local_url(base_url: str | None) -> bool:
    """True si la URL apunta a una máquina local (host loopback)."""
    if not base_url:
        return False
    lowered = base_url.lower()
    return "://" in lowered and any(
        marker in lowered.split("://", 1)[1].split("/", 1)[0]
        for marker in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "host.docker.internal")
    )


def normalize_base_url(url: str | None) -> str | None:
    """Valida y normaliza una Base URL. Devuelve None si es inválida."""
    if not url:
        return None
    candidate = url.strip()
    if not candidate:
        return None
    for scheme in ("http://", "https://"):
        if candidate.lower().startswith(scheme):
            rest = candidate[len(scheme):]
            host = rest.split("/", 1)[0].split("?", 1)[0]
            if host and " " not in host and "@" not in host:
                return candidate
    return None


# ---------------------------------------------------------------------------
# Modelo de datos
# ---------------------------------------------------------------------------

@dataclass
class Pricing:
    """Precios en USD por millón de tokens (esquema de OpenCode/models.dev)."""

    input: float | None = None
    output: float | None = None
    cache_read: float | None = None
    cache_write: float | None = None

    @property
    def known(self) -> bool:
        return self.input is not None or self.output is not None

    @property
    def is_free(self) -> bool:
        return (
            self.input is not None
            and self.output is not None
            and self.input == 0
            and self.output == 0
        )

    @property
    def sort_value(self) -> float | None:
        """Suma input+output para ordenar; None si no hay datos fiables."""
        if self.input is None and self.output is None:
            return None
        return (self.input or 0.0) + (self.output or 0.0)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Pricing":
        if not isinstance(data, dict):
            return cls()
        def num(key: str) -> float | None:
            value = data.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
            return None
        return cls(
            input=num("input"),
            output=num("output"),
            cache_read=num("cache_read"),
            cache_write=num("cache_write"),
        )


@dataclass
class ModelEntry:
    """Un modelo dentro del catálogo (no implica estar registrado)."""

    id: str
    name: str
    provider_id: str
    provider_name: str = ""
    model_type: str = "chat"
    description: str = ""
    family: str = ""
    npm: str = ""
    base_url: str = ""
    protocol: str = "other"
    context: int | None = None
    output_limit: int | None = None
    input_modalities: list[str] = field(default_factory=list)
    output_modalities: list[str] = field(default_factory=list)
    tool_call: bool | None = None
    reasoning: bool | None = None
    temperature: bool | None = None
    structured_output: bool | None = None
    streaming: bool | None = None
    open_weights: bool | None = None
    status: str = ""
    release_date: str = ""
    pricing: Pricing = field(default_factory=Pricing)
    env: list[str] = field(default_factory=list)
    source: str = "seed"
    raw: dict = field(default_factory=dict, repr=False)
    _search_text: str | None = field(default=None, repr=False)

    @property
    def vision(self) -> bool:
        return "image" in self.input_modalities or self.attachment is True

    @property
    def attachment(self) -> bool | None:
        raw_attachment = self.raw.get("attachment")
        return bool(raw_attachment) if raw_attachment is not None else None

    @property
    def full_id(self) -> str:
        return f"{self.provider_id}/{self.id}"

    @property
    def is_multimodal(self) -> bool:
        non_text = [m for m in self.input_modalities if m != "text"]
        return bool(non_text)

    @property
    def large_context(self) -> bool:
        return (self.context or 0) >= 200_000

    @property
    def coding(self) -> bool:
        haystack = f"{self.id} {self.name} {self.family} {self.description}".lower()
        markers = (
            "coder", "codestral", "codegemma", "devstral", "starcoder",
            "wizardcoder", "code llama", "deepseek-coder", "qwen2.5-coder",
            "qwen3-coder",
        )
        family = (self.family or "").lower()
        return any(marker in haystack for marker in markers) or "code" in family

    @property
    def free_variant(self) -> bool:
        """Variante gratuita anunciada (p. ej. OpenRouter ':free')."""
        return self.id.lower().endswith(":free") or "(free" in self.name.lower()

    @property
    def search_text(self) -> str:
        if self._search_text is None:
            self._search_text = " ".join((
                self.provider_name, self.provider_id, self.name, self.id,
                self.description, self.family, self.base_url, self.npm,
                self.model_type, self.status, " ".join(self.input_modalities),
                " ".join(self.output_modalities),
            )).lower()
        return self._search_text

    @classmethod
    def from_models_dev(
        cls,
        provider: "ProviderEntry",
        model_id: str,
        data: dict,
        source: str = "models.dev",
    ) -> "ModelEntry":
        limit = data.get("limit") if isinstance(data.get("limit"), dict) else {}
        modalities = data.get("modalities") if isinstance(data.get("modalities"), dict) else {}
        model_npm = ""
        provider_meta = data.get("provider")
        if isinstance(provider_meta, dict) and provider_meta.get("npm"):
            model_npm = str(provider_meta["npm"])
        npm = model_npm or provider.npm
        return cls(
            id=str(model_id),
            name=str(data.get("name") or model_id),
            provider_id=provider.id,
            provider_name=provider.name,
            model_type=str(data.get("type") or "chat"),
            description=str(data.get("description") or ""),
            family=str(data.get("family") or ""),
            npm=npm,
            base_url=provider.api,
            protocol=resolve_protocol(npm, provider.api),
            context=_as_int(limit.get("context")),
            output_limit=_as_int(limit.get("output")),
            input_modalities=_str_list(modalities.get("input")),
            output_modalities=_str_list(modalities.get("output")),
            tool_call=_as_bool(data.get("tool_call")),
            reasoning=_as_bool(data.get("reasoning")),
            temperature=_as_bool(data.get("temperature")),
            structured_output=_as_bool(data.get("structured_output")),
            open_weights=_as_bool(data.get("open_weights")),
            status=str(data.get("status") or ""),
            release_date=str(data.get("release_date") or ""),
            pricing=Pricing.from_dict(data.get("cost")),
            env=list(provider.env),
            source=source,
            raw=data,
        )


@dataclass
class ProviderEntry:
    """Un proveedor del catálogo."""

    id: str
    name: str
    npm: str = "@ai-sdk/openai-compatible"
    api: str = ""
    env: list[str] = field(default_factory=list)
    doc: str = ""
    models: dict[str, ModelEntry] = field(default_factory=dict)
    source: str = "seed"
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def protocol(self) -> str:
        return resolve_protocol(self.npm, self.api or None)

    @property
    def is_local(self) -> bool:
        return is_local_url(self.api)

    @property
    def model_count(self) -> int:
        return len(self.models)

    def sorted_models(self) -> list[ModelEntry]:
        return sorted(self.models.values(), key=lambda m: m.name.lower())


def _as_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return None


def _as_bool(value) -> bool | None:
    return value if isinstance(value, bool) else None


def _str_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [part.strip() for part in value.split("+") if part.strip()]
    return []


# ---------------------------------------------------------------------------
# Catálogo semilla (funciona sin Internet; no se inventan capacidades)
# ---------------------------------------------------------------------------

SEED_PROVIDERS: dict[str, dict] = {
    "bai": {
        "name": "B.AI",
        "npm": "@ai-sdk/openai-compatible",
        "api": "https://api.b.ai/v1",
        "doc": "https://chat.b.ai",
        "models": {
            "deepseek-v4-flash": {
                "name": "DeepSeek V4 Flash (B.AI)",
                "description": "DeepSeek V4 Flash servido por B.AI",
                "limit": {"context": 1_000_000},
            },
            "hy3": {
                "name": "Hy3 (B.AI)",
                "description": "Hy3 servido por B.AI",
            },
        },
    },
    "ollama": {
        "name": "Ollama (local)",
        "npm": "@ai-sdk/openai-compatible",
        "api": "http://localhost:11434/v1",
        "doc": "https://ollama.com",
        "models": {},
    },
    "lmstudio": {
        "name": "LM Studio (local)",
        "npm": "@ai-sdk/openai-compatible",
        "api": "http://127.0.0.1:1234/v1",
        "doc": "https://lmstudio.ai",
        "models": {},
    },
    "llama.cpp": {
        "name": "llama-server (local)",
        "npm": "@ai-sdk/openai-compatible",
        "api": "http://127.0.0.1:8080/v1",
        "doc": "https://github.com/ggml-org/llama.cpp",
        "models": {},
    },
    "openrouter": {
        "name": "OpenRouter",
        "npm": "@ai-sdk/openrouter",
        "api": "https://openrouter.ai/api/v1",
        "env": ["OPENROUTER_API_KEY"],
        "doc": "https://openrouter.ai/docs",
        "models": {},
    },
}


def seed_providers() -> dict[str, ProviderEntry]:
    """Proveedores curados incluidos con la aplicación."""
    result: dict[str, ProviderEntry] = {}
    for pid, pdata in SEED_PROVIDERS.items():
        entry = ProviderEntry(
            id=pid,
            name=pdata.get("name", pid),
            npm=pdata.get("npm", "@ai-sdk/openai-compatible"),
            api=pdata.get("api", ""),
            env=list(pdata.get("env", [])),
            doc=pdata.get("doc", ""),
            source="seed",
        )
        for mid, mdata in (pdata.get("models") or {}).items():
            entry.models[mid] = ModelEntry.from_models_dev(entry, mid, mdata, source="seed")
        result[pid] = entry
    return result


# ---------------------------------------------------------------------------
# Parsing de Models.dev
# ---------------------------------------------------------------------------

def parse_models_dev(payload: dict) -> dict[str, ProviderEntry]:
    """Convierte models.dev/api.json en ProviderEntry sin tocar el disco.

    Ignora proveedores malformados; preserva `raw` por entrada para no
    perder metadatos desconocidos.
    """
    result: dict[str, ProviderEntry] = {}
    if not isinstance(payload, dict):
        return result
    for pid, pdata in payload.items():
        if not isinstance(pdata, dict) or not isinstance(pdata.get("models"), dict):
            continue
        entry = ProviderEntry(
            id=str(pdata.get("id") or pid),
            name=str(pdata.get("name") or pid),
            npm=str(pdata.get("npm") or ""),
            api=str(pdata.get("api") or ""),
            env=[str(e) for e in pdata.get("env", []) if isinstance(e, str)],
            doc=str(pdata.get("doc") or ""),
            source="models.dev",
            raw=pdata,
        )
        for mid, mdata in entry_raw_models(pdata).items():
            if not isinstance(mdata, dict):
                continue
            entry.models[str(mid)] = ModelEntry.from_models_dev(entry, str(mid), mdata)
        result[entry.id] = entry
    return result


def entry_raw_models(pdata: dict) -> dict:
    models = pdata.get("models")
    return models if isinstance(models, dict) else {}


# ---------------------------------------------------------------------------
# Caché en disco + fuente remota
# ---------------------------------------------------------------------------

def cache_dir() -> Path:
    """Directorio de caché (respeta XDG_CACHE_HOME)."""
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".cache"
    return root / CATALOG_APP


class CatalogStore:
    """Orquestador del catálogo: semilla + caché de Models.dev + refresco.

    Nunca escribe en opencode.json. Solo ofrece datos de catálogo.
    """

    def __init__(self, directory: Path | None = None):
        self.directory = directory or cache_dir()
        self.raw_file = self.directory / "models_dev.json"
        self.meta_file = self.directory / "models_dev.meta.json"
        self.providers: dict[str, ProviderEntry] = seed_providers()
        self.last_updated: str | None = None
        self.loaded_source: str = "seed"

    # -- carga local ----------------------------------------------------
    def load_cache(self) -> bool:
        """Carga la última descarga en caché. True si hubo caché válida."""
        try:
            meta = json.loads(self.meta_file.read_text(encoding="utf-8"))
            raw = json.loads(self.raw_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if not isinstance(raw, dict):
            return False
        self._merge_source(parse_models_dev(raw))
        self.last_updated = meta.get("fetched_at")
        self.loaded_source = "cache"
        return True

    def adopt(
        self,
        providers: dict[str, ProviderEntry],
        last_updated: str | None = None,
        source: str | None = None,
    ) -> None:
        """Acepta un catálogo ya construido (lo que publica el worker).

        El hilo de trabajo nunca muta este store: los datos llegan completos
        por señal y aquí se publican, así la GUI jamás lee a medio cargar.
        """
        self.providers = providers
        if last_updated is not None:
            self.last_updated = last_updated
        if source:
            self.loaded_source = source

    def _merge_source(self, source: dict[str, ProviderEntry]) -> None:
        """Fusiona una fuente sobre el catálogo actual (models.dev > seed)."""
        for pid, entry in source.items():
            existing = self.providers.get(pid)
            if existing is None:
                self.providers[pid] = entry
                continue
            if entry.source == "models.dev" or not existing.models:
                for mid, model in entry.models.items():
                    if mid not in existing.models or model.source == "models.dev":
                        existing.models[mid] = model
                existing.npm = entry.npm or existing.npm
                existing.api = entry.api or existing.api
                existing.name = entry.name or existing.name
                existing.env = entry.env or existing.env
                existing.doc = entry.doc or existing.doc

    # -- red ------------------------------------------------------------
    @staticmethod
    def fetch(url: str = MODELS_DEV_URL, timeout: int = FETCH_TIMEOUT_SECONDS) -> dict:
        """Descarga Models.dev (solo se llama desde un worker, nunca la GUI).

        No envía credenciales: la petición es anónima y sin cabeceras de
        autenticación.
        """
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
            },
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                body = gzip.GzipFile(fileobj=io.BytesIO(body)).read()
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Models.dev no devolvió un objeto JSON")
        return payload

    def refresh(self, url: str = MODELS_DEV_URL, timeout: int = FETCH_TIMEOUT_SECONDS) -> int:
        """Descarga + cachea + refresca en memoria. Devuelve el total de modelos.

        Lanza urllib.error.URLError / OSError / ValueError en fallo.
        """
        payload = self.fetch(url=url, timeout=timeout)
        parsed = parse_models_dev(payload)
        self._merge_source(parsed)
        self._write_cache(payload)
        self.loaded_source = "remote"
        return self.model_count

    def _write_cache(self, payload: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        text = json.dumps(payload, ensure_ascii=False)
        tmp = self.raw_file.with_suffix(".json.tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, self.raw_file)
        meta = {
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source": MODELS_DEV_URL,
            "license": MODELS_DEV_LICENSE,
            "providers": len(self.providers),
            "models": self.model_count,
        }
        tmp_meta = self.meta_file.with_suffix(".meta.tmp")
        tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        os.replace(tmp_meta, self.meta_file)
        self.last_updated = meta["fetched_at"]

    # -- consulta ---------------------------------------------------------
    @property
    def model_count(self) -> int:
        return sum(p.model_count for p in self.providers.values())

    def all_models(self) -> list[ModelEntry]:
        result: list[ModelEntry] = []
        for entry in self.providers.values():
            result.extend(entry.models.values())
        return result

    def model(self, provider_id: str, model_id: str) -> ModelEntry | None:
        entry = self.providers.get(provider_id)
        if entry is None:
            return None
        return entry.models.get(model_id)

    def provider(self, provider_id: str) -> ProviderEntry | None:
        return self.providers.get(provider_id)

    def describe_source(self) -> str:
        stamp = "desconocida"
        if self.last_updated:
            try:
                stamp = datetime.fromisoformat(self.last_updated).strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
            except ValueError:
                stamp = self.last_updated
        return (
            f"Catálogo: {len(self.providers)} proveedores / "
            f"{self.model_count} modelos · "
            f"última actualización: {stamp} · fuentes: semilla + models.dev ({MODELS_DEV_LICENSE})"
        )
