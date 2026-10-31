"""Motor de búsqueda y filtros para el catálogo.

Busca sobre proveedor (nombre/ID), modelo (nombre/ID), endpoint,
descripción, familia, tipo y modalidades. Sin dependencias de GUI, para
que los filtros se evalúen sobre miles de entradas por pulsación de tecla
(en la UI se combina con debounce).

Las coincidencias se calculan sobre los DATOS del catálogo, nunca sobre la
visibilidad del árbol: un proveedor colapsado sigue apareciendo en la
búsqueda.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from omm.catalog import ModelEntry, ProviderEntry
from omm.i18n import tr

# Ámbito de proveedores.
SCOPE_ALL = "all"
SCOPE_CONFIGURED = "configured"
SCOPE_UNCONFIGURED = "unconfigured"

# Protocolo.
PROTOCOL_ANY = "any"
# "Otros" = cualquier protocolo no listado expresamente (bedrock, azure…).
PROTOCOL_OTHER = "other"
NAMED_PROTOCOLS = frozenset(
    {"openai-compatible", "openai", "anthropic", "google"}
)

# Orden.
SORT_NAME = "name"
SORT_PROVIDER = "provider"
SORT_CONTEXT = "context"
SORT_PRICE = "price"

# Contexto considerado "grande" para el filtro homónimo.
LARGE_CONTEXT_MIN = 200_000

MAX_RESULTS_HARD_CAP = 1000


@dataclass
class Filters:
    """Conjunto de filtros activos. Todos combinables (AND)."""

    text: str = ""
    scope: str = SCOPE_ALL
    protocol: str = PROTOCOL_ANY
    local_only: bool = False
    free: bool = False
    paid: bool = False
    free_tier: bool = False
    coding: bool = False
    reasoning: bool = False
    vision: bool = False
    tools: bool = False
    multimodal: bool = False
    large_context: bool = False
    sort: str = SORT_NAME
    descending: bool = False
    max_results: int = MAX_RESULTS_HARD_CAP

    def is_active(self) -> bool:
        return bool(
            self.text.strip()
            or self.scope != SCOPE_ALL
            or self.protocol != PROTOCOL_ANY
            or self.local_only
            or self.free or self.paid or self.free_tier
            or self.coding or self.reasoning or self.vision or self.tools
            or self.multimodal or self.large_context
        )

    def summary(self) -> str:
        """Descripción compacta de los filtros activos (para la barra de estado)."""
        parts: list[str] = []
        if self.scope == SCOPE_CONFIGURED:
            parts.append(tr("registered in OpenCode", es="registrados en OpenCode"))
        elif self.scope == SCOPE_UNCONFIGURED:
            parts.append(tr("unregistered", es="sin registrar"))
        if self.protocol == PROTOCOL_OTHER:
            parts.append(tr("other protocols", es="otros protocolos"))
        elif self.protocol != PROTOCOL_ANY:
            parts.append(self.protocol)
        if self.local_only:
            parts.append(tr("local", es="local"))
        flags = {
            tr("free", es="gratis"): self.free,
            tr("paid", es="de pago"): self.paid,
            tr("with free tier", es="con nivel gratis"): self.free_tier,
            tr("coding", es="de código"): self.coding,
            tr("reasoning", es="razonamiento"): self.reasoning,
            tr("vision", es="visión"): self.vision,
            tr("tool calling", es="tool calling"): self.tools,
            tr("multimodal", es="multimodal"): self.multimodal,
            tr("context ≥ 200k", es="contexto ≥ 200k"): self.large_context,
        }
        parts.extend(name for name, on in flags.items() if on)
        return " · ".join(parts)

    def with_(self, **changes) -> "Filters":
        return replace(self, **changes)


def matches_text(model: ModelEntry, text: str) -> bool:
    """Todas las palabras del texto deben aparecer (AND, sin distinción de mayúsculas)."""
    if not text:
        return True
    haystack = model.search_text
    return all(term in haystack for term in text.lower().split())


def matches_filters(
    model: ModelEntry,
    provider: ProviderEntry,
    filters: Filters,
    configured_full_ids: frozenset[str] | None = None,
) -> bool:
    """True si el modelo supera TODOS los filtros activos."""
    if not matches_text(model, filters.text):
        return False

    if configured_full_ids is not None:
        registered = model.full_id in configured_full_ids
        if filters.scope == SCOPE_CONFIGURED and not registered:
            return False
        if filters.scope == SCOPE_UNCONFIGURED and registered:
            return False

    if filters.protocol != PROTOCOL_ANY:
        if filters.protocol == PROTOCOL_OTHER:
            if model.protocol in NAMED_PROTOCOLS:
                return False
        elif model.protocol != filters.protocol:
            return False

    if filters.local_only and not provider.is_local:
        return False

    if filters.free and not model.pricing.is_free:
        return False
    if filters.paid and (not model.pricing.known or model.pricing.is_free):
        return False
    if filters.free_tier and not (model.pricing.is_free or model.free_variant):
        return False
    if filters.coding and not model.coding:
        return False
    if filters.reasoning and model.reasoning is not True:
        return False
    if filters.vision and not model.vision:
        return False
    if filters.tools and model.tool_call is not True:
        return False
    if filters.multimodal and not model.is_multimodal:
        return False
    if filters.large_context and (model.context or 0) < LARGE_CONTEXT_MIN:
        return False

    return True


def _flip(text: str, descending: bool):
    """Orden alfabético invertido sin cmp_to_key (comparación por bytes)."""
    if not descending:
        return text
    return tuple(255 - b for b in text.encode("utf-8"))


def sort_key(model: ModelEntry, sort: str, descending: bool = False):
    """Clave de ordenación; los valores desconocidos van siempre al final.

    Por defecto: contexto = mayor primero, precio = menor primero.
    `descending` invierte el criterio principal.
    """
    if sort == SORT_CONTEXT:
        value = model.context
        sign = 1 if descending else -1
        return (value is None, sign * (value or 0), model.name.lower())
    if sort == SORT_PRICE:
        value = model.pricing.sort_value
        return (
            value is None,
            -(value or 0.0) if descending else (value or 0.0),
            model.name.lower(),
        )
    if sort == SORT_PROVIDER:
        return (
            _flip(model.provider_name.lower(), descending),
            _flip(model.name.lower(), not descending),
        )
    return (
        _flip(model.name.lower(), descending),
        _flip(model.provider_name.lower(), descending),
    )


def catalog_pairs(providers: dict[str, ProviderEntry]):
    """Genera pares (proveedor, modelo) para `search()`."""
    for provider in providers.values():
        for model in provider.models.values():
            yield provider, model


def search(
    pairs,
    filters: Filters,
    configured_full_ids: frozenset[str] | None = None,
) -> tuple[list[ModelEntry], int]:
    """Aplica filtros y ordenación.

    `pairs`: iterable de (ProviderEntry, ModelEntry).
    Devuelve (resultados_recortados, nº total de coincidencias). El recorte
    afecta solo a la vista: el conteo siempre es el total real.
    """
    collected: list[ModelEntry] = []
    total = 0
    for provider, model in pairs:
        if matches_filters(model, provider, filters, configured_full_ids):
            total += 1
            if len(collected) < filters.max_results:
                collected.append(model)

    collected.sort(key=lambda m: sort_key(m, filters.sort, filters.descending))
    return collected, total
