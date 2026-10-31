"""Idioma de la interfaz: inglés como idioma fuente y español al lado.

Cada texto visible se escribe con ``tr("English", es="Español")``. Así la
traducción vive junto al texto que traduce: no hay una tabla aparte que se
pueda quedar desincronizada. ``set_language()`` cambia el idioma en caliente
y persiste la elección en QSettings desde la ventana principal.

Precedencia al arrancar: ``OMM_LANG`` (útil para pruebas y terminal) manda
sobre el valor guardado, y el valor guardado sobre el inglés.
"""

from __future__ import annotations

import os

LANGUAGES = {"en": "English", "es": "Español"}
DEFAULT_LANGUAGE = "en"

_language = DEFAULT_LANGUAGE


def get_language() -> str:
    return _language


def set_language(code: str) -> str:
    """Fija el idioma; un código desconocido vuelve al inglés."""
    global _language
    code = str(code or "").strip().lower()
    _language = code if code in LANGUAGES else DEFAULT_LANGUAGE
    return _language


def resolve_language(env: str | None, stored: str | None) -> str:
    """Idioma efectivo: entorno > preferencia guardada > inglés."""
    candidate = str(env or "").strip().lower()
    if candidate in LANGUAGES:
        return candidate
    candidate = str(stored or "").strip().lower()
    return candidate if candidate in LANGUAGES else DEFAULT_LANGUAGE


def init_language(settings=None) -> str:
    """Resuelve y aplica el idioma al arrancar la aplicación."""
    stored = None
    if settings is not None:
        try:
            stored = settings.value("language", DEFAULT_LANGUAGE)
        except Exception:
            stored = None
    return set_language(resolve_language(os.environ.get("OMM_LANG"), stored))


def tr(text: str, es: str | None = None) -> str:
    """Texto en el idioma activo; sin traducción devuelve el inglés."""
    if _language == "es" and es is not None:
        return es
    return text


def trn(
    count: int,
    one: str,
    many: str,
    es_one: str | None = None,
    es_many: str | None = None,
) -> str:
    """Singular o plural según ``count``, en el idioma activo."""
    if _language == "es" and es_one is not None and es_many is not None:
        return es_one if count == 1 else es_many
    return one if count == 1 else many


def format_int(value: int) -> str:
    """Separador de miles del idioma: 1,234 (en) / 1.234 (es)."""
    text = f"{int(value):,}"
    return text.replace(",", ".") if _language == "es" else text
