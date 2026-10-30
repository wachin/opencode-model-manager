"""Integración catálogo ↔ configuración opencode.json.

Todo lo que aquí se escribe va a la configuración REAL del usuario
(opencode.json); nada se escribe solo por existir en el catálogo. Las
funciones son puras sobre dicts, sin PyQt, para poder testearlas sin GUI.

Reglas:
  - Preservar propiedades desconocidas de proveedores/modelos existentes.
  - El alta de un modelo del catálogo escribe solo datos fiables conocidos
    (nombre, límites, coste, modalidades, capacidades).
  - Borrar de la configuración NUNCA toca el catálogo ni auth.json.
"""

from __future__ import annotations

from copy import deepcopy

from omm.catalog import (
    ModelEntry,
    Pricing,
    ProviderEntry,
    normalize_base_url,
    resolve_protocol,
)

MODEL_CONFIG_FIELDS = (
    "name", "modelID", "limit", "cost", "modalities", "reasoning",
    "tool_call", "temperature", "attachment", "status", "release_date",
    "family", "options", "headers", "variants", "provider",
)


def full_id(provider_id: str, model_id: str) -> str:
    return f"{provider_id}/{model_id}"


def config_providers(data: dict) -> dict[str, dict]:
    providers = data.get("provider")
    return providers if isinstance(providers, dict) else {}


def configured_full_ids(data: dict) -> frozenset[str]:
    result: set[str] = set()
    for pid, pdata in config_providers(data).items():
        if not isinstance(pdata, dict):
            continue
        models = pdata.get("models")
        if isinstance(models, dict):
            for mid in models:
                result.add(full_id(pid, str(mid)))
    return frozenset(result)


def config_base_url(pdata: dict | None) -> str:
    if not isinstance(pdata, dict):
        return ""
    options = pdata.get("options")
    if isinstance(options, dict):
        value = options.get("baseURL")
        if isinstance(value, str):
            return value
    return ""


def provider_from_config(pid: str, pdata: dict | None) -> ProviderEntry:
    """Vista de catálogo de un proveedor ya registrado (aunque no exista en el catálogo)."""
    pdata = pdata if isinstance(pdata, dict) else {}
    entry = ProviderEntry(
        id=pid,
        name=str(pdata.get("name") or pid),
        npm=str(pdata.get("npm") or ""),
        api=config_base_url(pdata),
        env=[str(e) for e in pdata.get("env", []) if isinstance(e, str)]
        if isinstance(pdata.get("env"), list) else [],
        source="config",
        raw=pdata,
    )
    models = pdata.get("models")
    if isinstance(models, dict):
        for mid, mdata in models.items():
            if not isinstance(mdata, dict):
                continue
            entry.models[str(mid)] = model_from_config(entry, str(mid), mdata)
    return entry


def model_from_config(
    provider: ProviderEntry, mid: str, mdata: dict
) -> ModelEntry:
    limit = mdata.get("limit") if isinstance(mdata.get("limit"), dict) else {}
    modalities = (
        mdata.get("modalities") if isinstance(mdata.get("modalities"), dict) else {}
    )
    npm = provider.npm
    provider_meta = mdata.get("provider")
    if isinstance(provider_meta, dict) and provider_meta.get("npm"):
        npm = str(provider_meta["npm"])
    return ModelEntry(
        id=mid,
        name=str(mdata.get("name") or mid),
        provider_id=provider.id,
        provider_name=provider.name,
        model_type="chat",
        npm=npm,
        base_url=provider.api,
        protocol=resolve_protocol(npm, provider.api or None),
        context=_num(limit.get("context")),
        output_limit=_num(limit.get("output")),
        input_modalities=_list(modalities.get("input")),
        output_modalities=_list(modalities.get("output")),
        tool_call=_bool(mdata.get("tool_call")),
        reasoning=_bool(mdata.get("reasoning")),
        temperature=_bool(mdata.get("temperature")),
        status=str(mdata.get("status") or ""),
        release_date=str(mdata.get("release_date") or ""),
        pricing=_pricing_from_config(mdata.get("cost")),
        source="config",
        raw=mdata,
    )


def _num(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if isinstance(value, float) and value.is_integer() else value
    return None


def _bool(value):
    return value if isinstance(value, bool) else None


def _list(value):
    return [str(v) for v in value] if isinstance(value, list) else []


def _pricing_from_config(cost) -> Pricing:
    if isinstance(cost, list) and cost:
        cost = cost[0]
    return Pricing.from_dict(cost if isinstance(cost, dict) else None)


# ---------------------------------------------------------------------------
# Alta / baja en la configuración
# ---------------------------------------------------------------------------

def add_provider_to_config(data: dict, spec: dict) -> str:
    """Registra un proveedor en data['provider']. Devuelve el id usado.

    `spec` sale del diálogo/JSON importado y ya está validado por
    validate_provider_spec(). Las claves desconocidas se conservan.
    """
    pid = spec["id"]
    providers = data.setdefault("provider", {})
    existing = providers.get(pid)
    pdata = deepcopy(existing) if isinstance(existing, dict) else {}
    pdata["npm"] = spec["npm"]
    pdata["name"] = spec["name"]
    options = deepcopy(pdata.get("options")) if isinstance(pdata.get("options"), dict) else {}
    options["baseURL"] = spec["baseURL"]
    if spec.get("headers"):
        options["headers"] = dict(spec["headers"])
    pdata["options"] = options
    if spec.get("env"):
        pdata["env"] = list(spec["env"])
    models = deepcopy(pdata.get("models")) if isinstance(pdata.get("models"), dict) else {}
    for mid, mdata in (spec.get("models") or {}).items():
        if mid not in models or not isinstance(models[mid], dict):
            models[mid] = {
                "name": mdata.get("name") or mid,
            }
            if mdata.get("modelID"):
                models[mid]["modelID"] = mdata["modelID"]
            if isinstance(mdata.get("limit"), dict):
                models[mid]["limit"] = deepcopy(mdata["limit"])
            if isinstance(mdata.get("cost"), dict):
                models[mid]["cost"] = deepcopy(mdata["cost"])
            if isinstance(mdata.get("modalities"), dict):
                models[mid]["modalities"] = deepcopy(mdata["modalities"])
    if "options" in spec and isinstance(spec["options"], dict) and spec["options"]:
        pdata["options"].update(deepcopy(spec["options"]))
    for key, value in spec.items():
        if key not in (
            "id", "name", "npm", "baseURL", "env", "headers", "models", "options",
            "protocol",
        ) and not key.startswith("_"):
            pdata[key] = deepcopy(value)
    if models:
        pdata["models"] = models
    providers[pid] = pdata
    return pid


def add_catalog_model_to_config(
    data: dict, model: ModelEntry, provider: ProviderEntry | None = None
) -> str:
    """Da de alta un modelo del catálogo en opencode.json.

    Si el proveedor aún no está registrado, se crea a partir de los datos
    del catálogo (npm, nombre, baseURL, env). El alta NUNCA incluye claves
    de API. Devuelve el full id del modelo.
    """
    pid = model.provider_id
    pdata = config_providers(data).get(pid)
    if not isinstance(pdata, dict):
        pdata = {}
        data.setdefault("provider", {})[pid] = pdata
    if provider is not None:
        pdata.setdefault("npm", provider.npm or "@ai-sdk/openai-compatible")
        pdata.setdefault("name", provider.name)
        if provider.api:
            options = pdata.setdefault("options", {})
            if isinstance(options, dict):
                options.setdefault("baseURL", provider.api)
        if provider.env and "env" not in pdata:
            pdata["env"] = list(provider.env)
    models = pdata.setdefault("models", {})
    if not isinstance(models, dict):
        models = {}
        pdata["models"] = models

    entry = deepcopy(models.get(model.id)) if isinstance(models.get(model.id), dict) else {}
    entry["name"] = model.name

    limit = {}
    if model.context:
        limit["context"] = model.context
    if model.output_limit:
        limit["output"] = model.output_limit
    if limit:
        existing_limit = entry.get("limit") if isinstance(entry.get("limit"), dict) else {}
        entry["limit"] = {**existing_limit, **limit}

    if model.pricing.known:
        cost = {}
        if model.pricing.input is not None:
            cost["input"] = model.pricing.input
        if model.pricing.output is not None:
            cost["output"] = model.pricing.output
        if model.pricing.cache_read is not None:
            cost["cache_read"] = model.pricing.cache_read
        if model.pricing.cache_write is not None:
            cost["cache_write"] = model.pricing.cache_write
        if cost:
            entry["cost"] = cost

    if model.input_modalities or model.output_modalities:
        modalities = {}
        if model.input_modalities:
            modalities["input"] = list(model.input_modalities)
        if model.output_modalities:
            modalities["output"] = list(model.output_modalities)
        entry["modalities"] = modalities
    if model.tool_call is not None:
        entry["tool_call"] = model.tool_call
    if model.reasoning is not None:
        entry["reasoning"] = model.reasoning
    if model.temperature is not None:
        entry["temperature"] = model.temperature

    models[model.id] = entry
    return full_id(pid, model.id)


def remove_model_from_config(data: dict, pid: str, mid: str) -> bool:
    """Quita un modelo de opencode.json. No toca el catálogo."""
    providers = config_providers(data)
    pdata = providers.get(pid)
    if not isinstance(pdata, dict):
        return False
    models = pdata.get("models")
    if not isinstance(models, dict) or mid not in models:
        return False
    del models[mid]
    _drop_default_references(data, full_id(pid, mid))
    return True


def remove_provider_from_config(data: dict, pid: str) -> bool:
    """Quita un proveedor completo (con todos sus modelos) de opencode.json."""
    providers = config_providers(data)
    if pid not in providers:
        return False
    del providers[pid]
    for key in ("model", "small_model"):
        value = data.get(key)
        if isinstance(value, str) and value.startswith(f"{pid}/"):
            data.pop(key, None)
    return True


def _drop_default_references(data: dict, ref: str) -> None:
    for key in ("model", "small_model"):
        if data.get(key) == ref:
            data.pop(key, None)


def set_default_model(data: dict, ref: str | None, small: bool = False) -> None:
    key = "small_model" if small else "model"
    if ref:
        data[key] = ref
    else:
        data.pop(key, None)


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Vistas combinadas para el árbol y el panel de detalle
# ---------------------------------------------------------------------------

def tree_data(
    catalog_providers: dict[str, ProviderEntry],
    config_data: dict,
) -> list[dict]:
    """Filas del árbol lateral: proveedor + sus modelos (catálogo ∪ config).

    Cada fila: {id, name, configured, protocol, npm, base_url, count,
    models: [(model_id, visible_name, configured, source)]} ordenada
    alfabéticamente por nombre visible.
    """
    rows: list[dict] = []
    for pid, name, catalog, pdata, configured in provider_union(
        catalog_providers, config_data
    ):
        models: dict[str, tuple[str, bool, str]] = {}
        if catalog is not None:
            for mid, m in catalog.models.items():
                models[mid] = (m.name, False, m.source)
        if isinstance(pdata, dict):
            pmodels = pdata.get("models")
            if isinstance(pmodels, dict):
                for mid, mdata in pmodels.items():
                    visible = mid
                    if isinstance(mdata, dict) and mdata.get("name"):
                        visible = str(mdata["name"])
                    elif isinstance(mdata, dict) and mdata.get("modelID"):
                        visible = str(mdata["modelID"])
                    prev = models.get(mid)
                    models[mid] = (
                        prev[0] if prev else visible,
                        True,
                        prev[2] if prev else "config",
                    )
        model_rows = sorted(
            (
                {
                    "id": mid,
                    "name": info[0],
                    "configured": info[1],
                    "source": info[2],
                }
                for mid, info in models.items()
            ),
            key=lambda r: r["name"].lower(),
        )
        protocol = ""
        if catalog is not None:
            protocol = catalog.protocol
        npm = ""
        base_url = ""
        if isinstance(pdata, dict):
            npm = str(pdata.get("npm") or "")
            base_url = config_base_url(pdata)
        if not npm and catalog is not None:
            npm = catalog.npm
        if not base_url and catalog is not None:
            base_url = catalog.api
        rows.append({
            "id": pid,
            "name": name,
            "configured": configured,
            "protocol": protocol or resolve_protocol(npm, base_url or None),
            "npm": npm,
            "base_url": base_url,
            "count": len(model_rows),
            "models": model_rows,
        })
    return rows


def provider_union(
    catalog_providers: dict[str, ProviderEntry],
    config_data: dict,
) -> list[tuple[str, str, ProviderEntry | None, dict | None, bool]]:
    """Proveedores del catálogo ∪ registrados en opencode.json, alfabéticos.

    Cada fila: (id, nombre_visible, entrada_catalogo|None, config|None,
    está_registrado). Los registrados que no existen en el catálogo se
    muestran igualmente (el usuario los configuró a mano).
    """
    config = config_providers(config_data)
    ids = set(catalog_providers) | set(config)
    rows = []
    for pid in ids:
        pdata = config.get(pid)
        pdata = pdata if isinstance(pdata, dict) else None
        catalog = catalog_providers.get(pid)
        name = ""
        if pdata:
            name = str(pdata.get("name") or "")
        if not name and catalog:
            name = catalog.name
        rows.append((pid, name or pid, catalog, pdata, pdata is not None))
    rows.sort(key=lambda row: (row[1].lower(), row[0].lower()))
    return rows


def _fmt_count(tokens: int | None) -> str:
    if tokens is None:
        return "Desconocido"
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.2f} M".replace(".00", "")
    if tokens >= 1_000:
        return f"{tokens / 1_000:.0f}k"
    return str(tokens)


def _fmt_bool(value: bool | None, yes: str = "Sí", no: str = "No") -> str:
    if value is None:
        return "Desconocido"
    return yes if value else no


def _fmt_price(pricing: Pricing) -> str:
    if not pricing.known:
        return "Sin datos de precio"
    if pricing.is_free:
        return "Gratis"
    return (
        f"Entrada ${pricing.input or 0:.2f} / salida "
        f"${pricing.output or 0:.2f} (USD/M tokens)"
    )


def model_detail_rows(
    model: ModelEntry | None,
    provider: ProviderEntry | None,
    config_model: dict | None,
    config_provider: dict | None,
) -> list[tuple[str, str]]:
    """Filas (etiqueta, valor) para el panel de detalle.

    Mezcla catálogo + configuración registrada; muestra "Desconocido" o
    "No disponible" cuando el catálogo no aporta datos fiables. No inventa.
    """
    if model is None and isinstance(config_model, dict):
        pid = (config_provider or {}).get("id") or ""
        model = model_from_config(
            provider or ProviderEntry(id=pid, name=pid), "", config_model
        )
    rows: list[tuple[str, str]] = []
    if provider is not None or config_provider is not None:
        # El id del proveedor también vive en ProviderEntry: un modelo que no
        # está ni en el catálogo ni en opencode.json sólo tiene esa fuente, y
        # sin ella la ficha mostraba «ID del proveedor» vacío.
        pid = (
            (model.provider_id if model else "")
            or (provider.id if provider else "")
            or (config_provider or {}).get("id", "")
        )
        pname = (provider.name if provider else "") or (config_provider or {}).get("name", "")
        rows.append(("Proveedor", pname or pid))
        rows.append(("ID del proveedor", pid))
    if model is not None:
        rows.append(("Modelo", model.name))
        rows.append(("ID del modelo", model.id))
    base_url = ""
    if isinstance(config_provider, dict):
        base_url = config_base_url(config_provider)
    if not base_url and provider is not None:
        base_url = provider.api
    rows.append(("API / Base URL", base_url or "Desconocida"))
    npm = model.npm if model else ""
    protocol = model.protocol if model else "other"
    if npm:
        rows.append(("Protocolo API", f"{protocol} · {npm}"))
    else:
        rows.append(("Protocolo API", "Desconocido"))
    rows.append(("Ventana de contexto", _fmt_count(model.context if model else None)))
    rows.append(("Salida máxima (tokens)", _fmt_count(model.output_limit if model else None)))
    if model:
        rows.append((
            "Modalidades de entrada",
            ", ".join(model.input_modalities) or "Desconocido",
        ))
        rows.append((
            "Modalidades de salida",
            ", ".join(model.output_modalities) or "Desconocido",
        ))
        rows.append(("Tool calling", _fmt_bool(model.tool_call)))
        rows.append(("Razonamiento", _fmt_bool(model.reasoning)))
        rows.append(("Visión", _fmt_bool(model.vision or None)))
        rows.append(("Streaming", "Desconocido"))
        rows.append(("Precio", _fmt_price(model.pricing)))
        rows.append(("Estado", model.status or "Sin estado"))
    registered = config_model is not None
    rows.append((
        "Configuración en OpenCode",
        "Registrado" if registered else "Solo en catálogo (no registrado)",
    ))
    return rows


def validate_provider_spec(spec: dict) -> list[str]:
    """Valida la definición de proveedor antes de escribirla.

    Devuelve la lista de errores (vacía si es válida). Nunca ejecuta ni
    instala nada: solo estructura y valores.
    """
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["La definición del proveedor debe ser un objeto JSON."]
    pid = spec.get("id")
    if not isinstance(pid, str) or not pid.strip():
        errors.append("Falta el ID del proveedor (clave \"id\").")
    elif any(c in pid for c in " /\t"):
        errors.append("El ID del proveedor no puede contener espacios ni \"/\".")
    name = spec.get("name")
    if name is not None and not isinstance(name, str):
        errors.append("\"name\" debe ser un texto.")
    npm = spec.get("npm", "@ai-sdk/openai-compatible")
    if not isinstance(npm, str) or not npm.strip():
        errors.append("\"npm\" debe ser un texto con el paquete AI SDK.")
    base = normalize_base_url(spec.get("baseURL", ""))
    if spec.get("baseURL") and base is None:
        errors.append(
            "La Base URL debe empezar por http:// o https:// y no contener espacios."
        )
    headers = spec.get("headers")
    if headers is not None:
        if not isinstance(headers, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in headers.items()
        ):
            errors.append("\"headers\" debe ser un objeto de texto a texto.")
    env = spec.get("env")
    if env is not None and (
        not isinstance(env, list) or not all(isinstance(e, str) for e in env)
    ):
        errors.append("\"env\" debe ser una lista de nombres de variable.")
    models = spec.get("models")
    if models is not None:
        if isinstance(models, dict):
            for mid, mdata in models.items():
                if not isinstance(mid, str) or not mid.strip():
                    errors.append(f"ID de modelo inválido: {mid!r}")
                if not isinstance(mdata, dict):
                    errors.append(f"El modelo {mid!r} debe ser un objeto JSON.")
        elif isinstance(models, list):
            for item in models:
                if not isinstance(item, dict) or not item.get("id"):
                    errors.append("Cada modelo de la lista necesita un \"id\".")
        else:
            errors.append("\"models\" debe ser un objeto o una lista.")
    return errors


def validate_config(data: dict) -> list[str]:
    """Valida la configuración completa antes de guardar."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["La configuración raíz debe ser un objeto JSON."]
    if "$schema" in data and not isinstance(data["$schema"], str):
        errors.append("\"$schema\" debe ser un texto.")
    providers = data.get("provider")
    if providers is not None:
        if not isinstance(providers, dict):
            errors.append("\"provider\" debe ser un objeto.")
        else:
            for pid, pdata in providers.items():
                prefix = f"provider.{pid}"
                if not isinstance(pdata, dict):
                    errors.append(f"{prefix} debe ser un objeto.")
                    continue
                if "npm" in pdata and not isinstance(pdata["npm"], str):
                    errors.append(f"{prefix}.npm debe ser un texto.")
                if "name" in pdata and not isinstance(pdata["name"], str):
                    errors.append(f"{prefix}.name debe ser un texto.")
                if "env" in pdata and not (
                    isinstance(pdata["env"], list)
                    and all(isinstance(e, str) for e in pdata["env"])
                ):
                    errors.append(f"{prefix}.env debe ser una lista de textos.")
                options = pdata.get("options")
                if options is not None:
                    if not isinstance(options, dict):
                        errors.append(f"{prefix}.options debe ser un objeto.")
                    else:
                        base = options.get("baseURL")
                        if base is not None and not isinstance(base, str):
                            errors.append(f"{prefix}.options.baseURL debe ser texto.")
                        if isinstance(base, str) and normalize_base_url(base) is None:
                            errors.append(
                                f"{prefix}.options.baseURL no es una URL http(s) válida."
                            )
                        headers = options.get("headers")
                        if headers is not None and not (
                            isinstance(headers, dict)
                            and all(
                                isinstance(k, str) and isinstance(v, str)
                                for k, v in headers.items()
                            )
                        ):
                            errors.append(
                                f"{prefix}.options.headers debe ser texto→texto."
                            )
                models = pdata.get("models")
                if models is not None and not isinstance(models, dict):
                    errors.append(f"{prefix}.models debe ser un objeto.")
                elif isinstance(models, dict):
                    for mid, mdata in models.items():
                        if not isinstance(mdata, dict):
                            errors.append(f"{prefix}.models.{mid} debe ser un objeto.")
                            continue
                        limit = mdata.get("limit")
                        if limit is not None:
                            if not isinstance(limit, dict):
                                errors.append(
                                    f"{prefix}.models.{mid}.limit debe ser un objeto."
                                )
                            else:
                                for key in ("context", "output", "input"):
                                    if key in limit and not isinstance(limit[key], (int, float)):
                                        errors.append(
                                            f"{prefix}.models.{mid}.limit.{key} debe ser numérico."
                                        )
                        cost = mdata.get("cost")
                        if cost is not None and not isinstance(cost, (dict, list)):
                            errors.append(f"{prefix}.models.{mid}.cost debe ser objeto o lista.")
    for key in ("model", "small_model"):
        value = data.get(key)
        if value is not None and not isinstance(value, str):
            if isinstance(value, dict):
                if not (isinstance(value.get("providerID"), str) and isinstance(value.get("model"), str)):
                    errors.append(
                        f"\"{key}\" como objeto necesita \"providerID\" y \"model\"."
                    )
            else:
                errors.append(f"\"{key}\" debe ser un texto \"proveedor/modelo\".")
        elif isinstance(value, str) and "/" not in value:
            errors.append(
                f"\"{key}\" = {value!r} no tiene el formato proveedor/modelo."
            )
    return errors
