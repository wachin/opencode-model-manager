"""Prueba de conexión contra el endpoint de un proveedor.

La pregunta concreta: ¿ese ``baseURL`` funciona de verdad, podrá OpenCode
hablar con él? La prueba es una **lectura** (``GET`` de la lista de
modelos), nunca una generación: no gasta tokens, no escribe en
opencode.json ni en la caché del catálogo.

Reglas que no cambian:

- Sin clave no se envía ninguna cabecera de autenticación.
- Con clave, el valor se lee de ``os.environ`` dentro del worker y solo
  viaja a un endpoint https (o loopback, que es Ollama/LM Studio).
- El valor de la clave no aparece en ningún mensaje: se redacta.
- No se siguen redirecciones: una ``Location`` a otro host convertiría un
  éxito aparente en la filtración de la cabecera de autenticación.
- auth.json no se lee ni se escribe. Las credenciales siguen siendo de
  OpenCode (``/connect``).

Solo stdlib: PyQt6 es la única dependencia externa del proyecto, y esta
prueba tiene que poder ejecutarse en headless y sin red.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from omm.catalog import (
    USER_AGENT, is_local_url, normalize_base_url, resolve_protocol,
)
from omm.i18n import tr, trn

PROBE_TIMEOUT_SECONDS = 12
MAX_BODY_BYTES = 256 * 1024
MAX_MODEL_IDS = 300
ANTHROPIC_VERSION = "2023-06-01"

# Protocolos cuyo formato de lista de modelos conocemos. Para el resto, un
# 404 aquí no significaría nada, así que lo honesto es decirlo.
TESTABLE_PROTOCOLS = frozenset({"openai", "openai-compatible", "anthropic"})

# Direcciones de metadatos del proveedor de nube. Ningún proveedor de IA
# vive ahí, y una petición con clave sería el robo de un rol de instancia.
BLOCKED_HOSTS = frozenset({
    "169.254.169.254",
    "169.254.170.2",
    "metadata.google.internal",
    "metadata.goog",
    "fd00:ec2::254",
})

# Tipos de resultado. `ok` y los que se consideran "el endpoint está vivo"
# se agrupan en ALIVE_KINDS: respondan 200 o 401, OpenCode podrá usarlo.
KIND_OK = "ok"
KIND_AUTH = "auth"
KIND_DENIED = "denied"
KIND_RATE_LIMITED = "rate_limited"
KIND_NOT_FOUND = "not_found"
KIND_REDIRECT = "redirect"
KIND_SERVER = "server"
KIND_UNREADABLE = "unreadable"
KIND_STATUS = "status"
KIND_DNS = "dns"
KIND_REFUSED = "refused"
KIND_TIMEOUT = "timeout"
KIND_TLS = "tls"
KIND_ERROR = "error"
KIND_INVALID = "invalid"
KIND_BLOCKED = "blocked"
KIND_UNSUPPORTED = "unsupported"
KIND_NO_ENV = "no_env"

ALIVE_KINDS = frozenset({KIND_OK, KIND_AUTH, KIND_RATE_LIMITED})


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    """Qué se ha encontrado al probar un endpoint. Nunca lleva credenciales."""

    kind: str
    summary: str
    detail: str = ""
    url: str = ""
    status: int | None = None
    latency_ms: int | None = None
    models: tuple[str, ...] = ()
    present: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    env_name: str = ""
    with_key: bool = False

    @property
    def alive(self) -> bool:
        """True si el endpoint respondió algo con lo que OpenCode puede trabajar."""
        return self.kind in ALIVE_KINDS

    @property
    def ok(self) -> bool:
        return self.kind == KIND_OK

    @property
    def wanted(self) -> int:
        return len(self.present) + len(self.missing)

    def line(self) -> str:
        """Una línea para la ficha y la barra de estado (sin valores de clave)."""
        parts = [self.summary]
        if self.status is not None:
            parts.append(f"HTTP {self.status}")
        if self.latency_ms is not None:
            parts.append(f"{self.latency_ms} ms")
        if self.models:
            total = len(self.models)
            parts.append(trn(
                total,
                "{count} model announced", "{count} models announced",
                es_one="{count} modelo anunciado",
                es_many="{count} modelos anunciados",
            ).format(count=total))
        if self.wanted:
            parts.append(tr(
                "your models: {present}/{wanted}",
                es="tus modelos: {present}/{wanted}",
            ).format(present=len(self.present), wanted=self.wanted))
        if self.missing:
            parts.append(tr("missing ", es="faltan ") + ", ".join(self.missing))
        return " · ".join(parts)

    def report(self) -> str:
        """Línea + detalle + a dónde se ha llamado exactamente (para la ficha)."""
        blocks = [self.line()]
        if self.detail:
            blocks.append(self.detail)
        if self.url:
            blocks.append(tr("Request: GET {url}", es="Petición: GET {url}")
                          .format(url=self.url))
        return "\n".join(blocks)


# ---------------------------------------------------------------------------
# Planificación: decidir si se puede probar, y a qué URL
# ---------------------------------------------------------------------------

def host_of(url: str) -> str:
    """Host (en minúsculas, sin puerto) de una URL ya validada."""
    try:
        return urllib.parse.urlsplit(url).hostname or ""
    except ValueError:
        return ""


def is_blocked_url(url: str) -> bool:
    """True si la URL apunta a metadatos del proveedor de nube."""
    return host_of(url).lower() in BLOCKED_HOSTS


def key_transport_ok(url: str) -> bool:
    """HTTPS, o HTTP solo en loopback (Ollama, LM Studio, llama.cpp…)."""
    lowered = (url or "").lower()
    return lowered.startswith("https://") or (
        lowered.startswith("http://") and is_local_url(url)
    )


def models_url(base_url: str, protocol: str) -> str:
    """Ruta real de la lista de modelos para este ``baseURL``.

    OpenCode guarda en ``baseURL`` la raíz del SDK: a veces con ``/v1``
    incluido (``https://api.deepseek.com/v1``) y a veces sin él
    (``http://localhost:11434``). Probar la ruta equivocada daría un 404
    que parecería «el proveedor está roto».
    """
    root = (base_url or "").rstrip("/")
    if protocol == "anthropic":
        return f"{root}/models" if root.endswith("/v1") else f"{root}/v1/models"
    if root.endswith("/v1"):
        return f"{root}/models"
    if root.endswith("/models"):
        return root
    return f"{root}/v1/models"


def unproposable_reason(base_url: str, protocol: str) -> str:
    """Devuelve "" si hay una prueba que hacer; si no, por qué no la hay.

    Es la única fuente de la explicación: la usan a la vez el tooltip del
    botón y la propia prueba, para que el aviso nunca contradiga al hecho.
    """
    url = normalize_base_url(base_url)
    if not url:
        return tr(
            "There is no URL to test: neither opencode.json nor the catalog "
            "declares a baseURL for this provider.",
            es="No hay URL que probar: ni opencode.json ni el catálogo "
               "declaran un baseURL para este proveedor.",
        )
    if is_blocked_url(url):
        return tr(
            "{host} is a cloud metadata address, not an AI endpoint. "
            "Not contacted.",
            es="{host} es una dirección de metadatos del proveedor de nube, "
               "no un endpoint de IA. No se contacta.",
        ).format(host=host_of(url))
    if protocol not in TESTABLE_PROTOCOLS:
        return tr(
            "I don't know how to test protocol «{protocol}»: its SDK decides "
            "the format and a 404 here would mean nothing. This test does "
            "cover openai, openai-compatible and anthropic.",
            es="No sé probar el protocolo «{protocol}»: el formato lo decide "
               "su SDK y un 404 aquí no querría decir nada. Esta prueba sí "
               "cubre openai, openai-compatible y anthropic.",
        ).format(protocol=protocol)
    return ""


def env_status(names) -> list[tuple[str, bool]]:
    """Nombre → está definido en el entorno de este proceso. Jamás el valor."""
    out = []
    for name in names or ():
        text = str(name)
        out.append((text, bool(os.environ.get(text, "").strip())))
    return out


def first_present_env(names) -> tuple[str, str]:
    """(variable, valor) de la primera variable declarada y definida.

    Devuelve ("", "") si ninguna lo está. El valor sale de aquí solo para
    viajar a la cabecera de la petición: nunca se muestra ni se guarda.
    """
    for name, value in ((n, os.environ.get(str(n), "")) for n in names or ()):
        if value.strip():
            return str(name), value.strip()
    return "", ""


def key_offer(base_url: str, protocol: str, env_names) -> tuple[bool, str]:
    """Puede ofrecerse «Probar con mi clave», y si no, por qué.

    Se ofrece solo si hay una variable declarada Y definida Y el transporte
    no la mandaría en claro. Nunca se adivina una variable que el
    proveedor no haya declarado.
    """
    blocked = unproposable_reason(base_url, protocol)
    if blocked:
        return False, blocked
    url = normalize_base_url(base_url) or ""
    names = [str(n) for n in env_names or ()]
    if not names:
        return False, tr(
            "This provider does not declare any environment variable in the "
            "catalog: there is no key to send. Credentials are set with "
            "/connect.",
            es="Este proveedor no declara ninguna variable de entorno en el "
               "catálogo: no hay clave que enviar. Las credenciales se ponen "
               "con /connect.",
        )
    if not first_present_env(names)[0]:
        return False, tr(
            "{names} is not defined in this window's environment. If you "
            "export it in a terminal, relaunch the app from it (or use "
            "/connect).",
            es="{names} no está definida en el entorno de esta ventana. Si la "
               "exportas en un terminal, hay que relanzar la app desde él (o "
               "usar /connect).",
        ).format(names=", ".join(names))
    if not key_transport_ok(url):
        return False, tr(
            "{host} answers over unencrypted HTTP: I won't send your key in "
            "the clear. Change the baseURL to https:// or test on loopback.",
            es="{host} contesta por HTTP sin cifrar: no envío tu clave en "
               "claro. Cambia el baseURL a https:// o prueba en loopback.",
        ).format(host=host_of(url))
    return True, ""


def auth_headers(protocol: str, api_key: str) -> dict[str, str]:
    """Cabeceras de autenticación según el protocolo. Vacías si no hay clave."""
    if not api_key:
        return {}
    if protocol == "anthropic":
        return {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}
    return {"Authorization": f"Bearer {api_key}"}


# ---------------------------------------------------------------------------
# Lectura de la respuesta
# ---------------------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Corta las redirecciones en vez de seguirlas."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        return None


def default_opener(request, timeout: float):
    """urllib sin redirecciones. Solo se llama desde un worker, nunca la GUI."""
    opener = urllib.request.build_opener(_NoRedirect)
    return opener.open(request, timeout=timeout)


def build_request(url: str, protocol: str, api_key: str):
    """La petición: anónima salvo que haya clave explícita para este host."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    headers.update(auth_headers(protocol, api_key))
    return urllib.request.Request(url, headers=headers, method="GET")


def _decode_body(response) -> bytes:
    body = response.read(MAX_BODY_BYTES)
    if isinstance(body, str):
        body = body.encode("utf-8", "replace")
    encoding = ""
    headers = getattr(response, "headers", None)
    if headers is not None:
        encoding = (headers.get("Content-Encoding") or "").lower()
    if "gzip" in encoding:
        try:
            body = gzip.GzipFile(fileobj=io.BytesIO(body)).read()
        except OSError:
            pass
    return body


def extract_model_ids(payload) -> list[str]:
    """IDs de modelo de una respuesta estilo OpenAI o Anthropic.

    Defensivo: no da por supuesto el formato (``{"data": [...]}``,
    ``{"models": {"id": {...}}}``, ``{"model": "..."}``…) y si no hay lista
    devuelve [] en lugar de inventarla.
    """
    def take(item) -> list[str]:
        """IDs de una entrada, o [] si no se reconoce su forma."""
        if isinstance(item, str):
            return [item.strip()] if item.strip() else []
        if not isinstance(item, dict):
            return []
        for key in ("id", "model", "modelId", "name", "display_name"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return [value.strip()]
        # Mapa id -> definición de modelo: las claves son los identificadores.
        if item and all(isinstance(value, dict) for value in item.values()):
            return [str(identifier).strip() for identifier in item
                    if str(identifier).strip()]
        return []

    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = []
        for key in ("data", "models", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                entries.extend(value)
            elif isinstance(value, dict):
                entries.append(value)
    else:
        entries = []

    found: list[str] = []
    for entry in entries:
        found.extend(take(entry))

    unique: list[str] = []
    seen: set[str] = set()
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[:MAX_MODEL_IDS]


# ---------------------------------------------------------------------------
# Diagnóstico
# ---------------------------------------------------------------------------

def _redact(text: str, api_key: str) -> str:
    """Quita el valor de la clave de cualquier mensaje generado."""
    if api_key and api_key in text:
        return text.replace(api_key, "«clave»")
    return text


def _classify_exception(exc: Exception, host: str, timeout: float) -> tuple[str, str, str]:
    """(kind, summary, detail) a partir del fallo de transporte.

    urllib envuelve el error de socket en ``URLError(reason=…)``: se mira el
    ``reason`` y, si no, la excepción, porque según el camino del fallo el
    error real aparece en uno u otro sitio.
    """
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    for candidate in (reason, exc):
        if isinstance(candidate, ssl.SSLError):
            return (
                KIND_TLS,
                tr("The TLS certificate fails", es="El certificado TLS falla"),
                _ssl_reason(candidate),
            )
        if isinstance(candidate, socket.gaierror):
            return (
                KIND_DNS,
                tr("{host} does not resolve", es="{host} no resuelve")
                .format(host=host),
                tr("The domain name does not exist or DNS is not "
                   "responding: check the baseURL.",
                   es="El nombre de dominio no existe o el DNS no responde: "
                      "revisa el baseURL."),
            )
        if isinstance(candidate, ConnectionRefusedError):
            return (
                KIND_REFUSED,
                tr("Nothing is listening on that port",
                   es="Nada escucha en ese puerto"),
                tr("{host} has rejected the connection. If it is a local "
                   "service (Ollama, LM Studio, llama.cpp), start it before "
                   "testing.",
                   es="{host} ha rechazado la conexión. Si es un servicio "
                      "local (Ollama, LM Studio, llama.cpp), levántalo antes "
                      "de probar.").format(host=host),
            )
        if isinstance(candidate, (socket.timeout, TimeoutError)):
            return (
                KIND_TIMEOUT,
                tr("Silence after {seconds} s", es="Silencio tras {seconds} s")
                .format(seconds=int(timeout)),
                tr("{host} did not answer in time. It may be down, or a "
                   "firewall is dropping packets.",
                   es="{host} no ha contestado a tiempo. Puede estar caído, o "
                      "el firewall está soltando los paquetes.")
                .format(host=host),
            )
    detail = _first_line(str(reason) or str(exc) or exc.__class__.__name__)
    return (
        KIND_ERROR,
        tr("Could not connect", es="No se ha podido conectar"),
        f"{host}: {detail}",
    )


def _ssl_reason(exc) -> str:
    """El detalle de un fallo de certificado vive en ``verify_message``."""
    info = getattr(exc, "verify_message", None)
    if isinstance(info, dict):
        host = info.get("hostname") or ""
        reason = info.get("reason") or ""
        if host and reason:
            return tr(
                "The certificate is not valid for {host}: {reason}. "
                "No credential was sent.",
                es="El certificado no vale para {host}: {reason}. "
                   "No se ha enviado ninguna credencial.",
            ).format(host=host, reason=reason)
    text = _first_line(str(exc) or exc.__class__.__name__)
    return tr(
        "The certificate could not be verified: {text}.",
        es="El certificado no se ha podido verificar: {text}.",
    ).format(text=text)


def _first_line(text: str) -> str:
    return " ".join(text.strip().splitlines()[:1])[:220]


def _from_status(status: int, api_key: str, url: str) -> tuple[str, str, str]:
    """(kind, summary, detail) para un código HTTP concreto."""
    host = host_of(url)
    path = urllib.parse.urlsplit(url).path or "/"
    if status in (401, 403):
        if api_key:
            return (
                KIND_DENIED,
                tr("The endpoint exists, but it rejects your key",
                   es="El endpoint existe, pero rechaza tu clave"),
                tr("{host} answered {status} with the key from the "
                   "environment variable. Correct endpoint, invalid "
                   "credential or missing permissions.",
                   es="{host} ha contestado {status} con la clave de la "
                      "variable de entorno. Endpoint correcto, credencial "
                      "inválida o sin permisos.")
                .format(host=host, status=status),
            )
        return (
            KIND_AUTH,
            tr("Endpoint alive: it asks for credentials",
               es="Endpoint vivo: pide credenciales"),
            tr("{host} responds {status} at {path} without a key, which is "
               "expected. The route exists; OpenCode will use it as soon as "
               "you set the credential with /connect.",
               es="{host} responde {status} en {path} sin clave, que es lo "
                  "esperado. La ruta existe; OpenCode la usará en cuanto "
                  "pongas la credencial con /connect.")
            .format(host=host, status=status, path=path),
        )
    if status in (404, 405, 400):
        return (
            KIND_NOT_FOUND,
            tr("Does not expose {path}", es="No expone {path}").format(path=path),
            tr("Host {host} responds, but {path} returns {status}. It is "
               "usually a baseURL missing (or with an extra) /v1 suffix.",
               es="El host {host} responde, pero {path} da {status}. Suele "
                  "ser un baseURL al que le falta (o le sobra) el sufijo "
                  "/v1.").format(host=host, path=path, status=status),
        )
    if status == 429:
        return (
            KIND_RATE_LIMITED,
            tr("Alive, but saturated (429)", es="Vivo, pero saturado (429)"),
            tr("{host} rate-limited the request. The endpoint exists; retry "
               "later.",
               es="{host} ha limitado la petición. El endpoint existe; "
                  "reintenta más tarde.").format(host=host),
        )
    if 500 <= status <= 599:
        return (
            KIND_SERVER,
            tr("The server fails ({status})", es="El servidor falla ({status})")
            .format(status=status),
            tr("{host} responded with a server error at {path}. The name and "
               "route exist: it is a problem on their side.",
               es="{host} ha respondido con un error de servidor en {path}. "
                  "El nombre y la ruta existen: es un problema de su lado.")
            .format(host=host, path=path),
        )
    if 300 <= status <= 399:
        return (
            KIND_REDIRECT,
            tr("Redirects outside your baseURL",
               es="Redirige fuera de tu baseURL"),
            tr("{host} answers {status}. We do not follow the redirect: it "
               "could carry the authentication header to another origin.",
               es="{host} contesta {status}. No seguimos la redirección: "
                  "podría llevar la cabecera de autenticación a otro origen.")
            .format(host=host, status=status),
        )
    return (
        KIND_STATUS,
        tr("Unexpected response ({status})",
           es="Respuesta inesperada ({status})").format(status=status),
        tr("{host} answered {status} to {path}, which is not a result this "
           "test knows how to interpret.",
           es="{host} ha contestado {status} a {path}, que no es un resultado "
              "que esta prueba sepa interpretar.")
        .format(host=host, status=status, path=path),
    )


def _result(kind: str, summary: str, detail: str = "", *, url: str = "",
            status: int | None = None, latency_ms: int | None = None,
            env_name: str = "", with_key: bool = False,
            models=(), present=(), missing=(), api_key: str = "") -> ProbeResult:
    """Constructor único: todo texto pasa por la redacción de la clave."""
    clean = (lambda text: _redact(text, api_key) if api_key else text)
    return ProbeResult(
        kind=kind,
        summary=clean(summary),
        detail=clean(detail),
        url=clean(url),
        status=status,
        latency_ms=latency_ms,
        models=tuple(models),
        present=tuple(present),
        missing=tuple(missing),
        env_name=env_name,
        with_key=with_key,
    )


def _compare(ids, wanted) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(presentes, faltan) entre los modelos anunciados y los buscados."""
    pool = {str(i).lower() for i in ids}
    present, missing = [], []
    for item in wanted or ():
        text = str(item)
        (present if text.lower() in pool else missing).append(text)
    return tuple(present), tuple(missing)


def probe_endpoint(
    base_url: str,
    protocol: str = "",
    api_key: str = "",
    env_name: str = "",
    wanted_models=(),
    opener=None,
    timeout: int = PROBE_TIMEOUT_SECONDS,
) -> ProbeResult:
    """Prueba real contra el endpoint. No toca disco ni configuración.

    ``opener`` es inyectable para poder probar todo el diagnóstico sin red.
    ``api_key`` se usa solo para la cabecera: se redacta en cada mensaje.
    """
    url = normalize_base_url(base_url) or ""
    protocol = protocol or resolve_protocol("", url or None)
    reason = unproposable_reason(base_url, protocol)
    if reason:
        kind = (
            KIND_BLOCKED if url and is_blocked_url(url)
            else KIND_UNSUPPORTED if url
            else KIND_INVALID
        )
        summary = {
            KIND_BLOCKED: tr("Endpoint rejected for security",
                             es="Endpoint rechazado por seguridad"),
            KIND_UNSUPPORTED: tr("I don't know how to test this protocol",
                                 es="No sé probar este protocolo"),
            KIND_INVALID: tr("No endpoint to test",
                             es="Sin endpoint que probar"),
        }[kind]
        return _result(kind, summary, reason, url=url, api_key=api_key)

    if api_key and not key_transport_ok(url):
        return _result(
            KIND_BLOCKED,
            tr("I won't send the key over unencrypted HTTP",
               es="No envío la clave por HTTP sin cifrar"),
            tr("{host} answers over http://; your key would travel in the "
               "clear. Set https:// in the baseURL or test without a key.",
               es="{host} contesta por http://; tu clave viajaría en claro. "
                  "Pon https:// en el baseURL o prueba sin clave.")
            .format(host=host_of(url)),
            url=url, env_name=env_name, with_key=True, api_key=api_key,
        )

    target = models_url(url, protocol)
    request = build_request(target, protocol, api_key)
    opener = opener or default_opener
    host = host_of(target)

    started = time.perf_counter()
    try:
        response = opener(request, timeout)
        try:
            status = int(getattr(response, "status", None) or response.code)
            body = _decode_body(response)
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()
    except urllib.error.HTTPError as exc:  # 3xx cortados y cualquier 4xx/5xx
        latency = _latency(started)
        kind, summary, detail = _from_status(exc.code, api_key, target)
        result = _result(
            kind, summary, detail, url=target, status=exc.code,
            latency_ms=latency, env_name=env_name, with_key=bool(api_key),
            api_key=api_key,
        )
        if kind == KIND_REDIRECT:
            headers = getattr(exc, "headers", None)
            location = host_of((headers.get("Location") if headers else "") or "")
            if location:
                result.detail += tr(
                    " The destination is {location}.",
                    es=" El destino es {location}.",
                ).format(location=location)
        return result
    except Exception as exc:  # DNS, conexión rehusada, timeout, TLS, proxy…
        return _result(
            *_classify_exception(exc, host, timeout),
            url=target, latency_ms=_latency(started), env_name=env_name,
            with_key=bool(api_key), api_key=api_key,
        )

    latency = _latency(started)
    if not 200 <= status < 300:
        kind, summary, detail = _from_status(status, api_key, target)
        return _result(
            kind, summary, detail, url=target, status=status,
            latency_ms=latency, env_name=env_name, with_key=bool(api_key),
            api_key=api_key,
        )

    try:
        payload = json.loads(body.decode("utf-8", "replace"))
    except (ValueError, UnicodeDecodeError):
        return _result(
            KIND_UNREADABLE,
            tr("Responds 200, but it is not JSON",
               es="Responde 200, pero no es JSON"),
            tr("{host} returned {size} bytes that are not a readable model "
               "list. The host is alive; the format is not the one this "
               "protocol expects.",
               es="{host} ha devuelto {size} bytes que no son una lista de "
                  "modelos legible. El host está vivo; el formato no es el "
                  "que espera este protocolo.")
            .format(host=host, size=len(body)),
            url=target, status=status, latency_ms=latency,
            env_name=env_name, with_key=bool(api_key), api_key=api_key,
        )

    if not isinstance(payload, (dict, list)):
        return _result(
            KIND_UNREADABLE,
            tr("Response without catalog shape",
               es="Respuesta sin forma de catálogo"),
            tr("{host} answered a JSON of type {type}: it is not an object "
               "or a list of models.",
               es="{host} ha contestado un JSON de tipo {type}: no es un "
                  "objeto ni una lista de modelos.")
            .format(host=host, type=type(payload).__name__),
            url=target, status=status, latency_ms=latency,
            env_name=env_name, with_key=bool(api_key), api_key=api_key,
        )

    ids = extract_model_ids(payload)
    present, missing = _compare(ids, wanted_models)
    if not ids:
        return _result(
            KIND_OK,
            tr("Endpoint working, no models listed",
               es="Endpoint operativo, sin modelos listados"),
            tr("{host} responded 200 on the models route but the list is "
               "empty or in another format. The connection works; we could "
               "not check which models it offers.",
               es="{host} ha respondido 200 en la ruta de modelos pero la "
                  "lista viene vacía o con otro formato. La conexión "
                  "funciona; no hemos podido comprobar qué modelos ofrece.")
            .format(host=host),
            url=target, status=status, latency_ms=latency,
            env_name=env_name, with_key=bool(api_key), present=present,
            missing=missing, api_key=api_key,
        )
    models_word = trn(
        len(ids), "model", "models", es_one="modelo", es_many="modelos",
    )
    detail = tr(
        "{host} responds {count} {models} on the models route.",
        es="{host} responde {count} {models} en la ruta de modelos.",
    ).format(host=host, count=len(ids), models=models_word)
    if missing:
        detail += tr(
            " Warning: {missing} does not appear among the announced ones.",
            es=" Ojo: {missing} no aparece entre los anunciados.",
        ).format(missing=", ".join(missing))
    return _result(
        KIND_OK,
        tr("Endpoint working", es="Endpoint operativo"),
        detail,
        url=target, status=status, latency_ms=latency, models=ids,
        present=present, missing=missing, env_name=env_name,
        with_key=bool(api_key), api_key=api_key,
    )


def _latency(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))
