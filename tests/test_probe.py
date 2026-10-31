"""Prueba de conexión: planificación, diagnóstico y garantías de seguridad.

Dos capas, y ninguna toca Internet:

  - un ``opener`` falso inyectado, que permite reproducir cada respuesta y
    cada fallo de transporte sin abrir un socket;
  - un ``http.server`` en 127.0.0.1, para ejercitar el urllib de verdad
    (incluido que NO se siguen redirecciones) sobre loopback.

La clave de los tests se busca en todos los textos que produce el módulo:
si aparece una sola vez, el test falla.
"""

from __future__ import annotations

import gzip
import io
import json
import os
import socket
import ssl
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

from support import ROOT  # noqa: F401  (deja `tests/` y la raíz en sys.path)
from omm.probe import (
    KIND_AUTH, KIND_BLOCKED, KIND_DENIED, KIND_DNS, KIND_INVALID,
    KIND_NOT_FOUND, KIND_OK, KIND_RATE_LIMITED, KIND_REDIRECT, KIND_REFUSED,
    KIND_SERVER, KIND_TIMEOUT, KIND_TLS, KIND_UNREADABLE, KIND_UNSUPPORTED,
    ProbeResult, default_opener, env_status, extract_model_ids,
    first_present_env, host_of, is_blocked_url, key_offer, key_transport_ok,
    models_url, probe_endpoint, unproposable_reason,
)

KEY = "sk-prueba-NO-DEBE-SALIR-0123456789"
URL = "https://api.acme.test/v1"


class FakeResponse:
    """Lo mínimo de una respuesta HTTP: status, cabeceras, read() y close()."""

    def __init__(self, status: int = 200, payload=None, raw: bytes | None = None,
                 headers: dict | None = None) -> None:
        self.status = status
        self.code = status
        self.headers = headers or {}
        if raw is not None:
            self._body = raw
        elif payload is None:
            self._body = b"{}"
        else:
            self._body = json.dumps(payload).encode("utf-8")
        self.closed = False

    def read(self, amount: int = -1) -> bytes:
        return self._body[:amount] if amount >= 0 else self._body

    def close(self) -> None:
        self.closed = True


class RecordingOpener:
    """opener(request, timeout) que guarda la petición y devuelve/lanza."""

    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.requests: list = []
        self.timeouts: list = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        self.timeouts.append(timeout)
        if self.error is not None:
            raise self.error
        return self.response

    # -- ayudas de lectura ---------------------------------------------
    def header(self, name: str) -> str:
        return self.requests[-1].get_header(name) or ""

    def headers(self) -> dict:
        return {k.lower(): v for k, v in self.requests[-1].header_items()}


def forbidden_opener(request, timeout):  # pragma: no cover - debe no llamarse
    raise AssertionError(f"no debía hacerse ninguna petición: {request.full_url}")


def forbidden(*_args, **_kwargs):
    raise AssertionError("no debía hacerse ninguna petición")


class TestModelsUrl(unittest.TestCase):
    """La ruta que se prueba tiene que ser la que el SDK usará de verdad."""

    def test_a_local_root_gets_v1(self):
        self.assertEqual(
            models_url("http://localhost:11434", "openai-compatible"),
            "http://localhost:11434/v1/models",
        )

    def test_a_base_that_already_ends_in_v1_is_not_doubled(self):
        self.assertEqual(
            models_url("https://api.deepseek.com/v1/", "openai-compatible"),
            "https://api.deepseek.com/v1/models",
        )

    def test_openai_hosts(self):
        self.assertEqual(
            models_url("https://api.openai.com/v1", "openai"),
            "https://api.openai.com/v1/models",
        )
        self.assertEqual(
            models_url("https://api.groq.com/openai/v1", "openai-compatible"),
            "https://api.groq.com/openai/v1/models",
        )

    def test_anthropic_adds_v1_and_keeps_a_root(self):
        self.assertEqual(
            models_url("https://api.anthropic.com", "anthropic"),
            "https://api.anthropic.com/v1/models",
        )
        self.assertEqual(
            models_url("https://proxy.test/anthropic/v1", "anthropic"),
            "https://proxy.test/anthropic/v1/models",
        )

    def test_a_full_models_url_is_left_alone(self):
        self.assertEqual(
            models_url("https://api.acme.test/v1/models", "openai"),
            "https://api.acme.test/v1/models",
        )


class TestRefusals(unittest.TestCase):
    """Cuando no se puede (o no se debe) probar, se dice y no se llama."""

    def test_without_a_url_there_is_nothing_to_probe(self):
        result = probe_endpoint("", "openai-compatible", opener=forbidden)
        self.assertEqual(result.kind, KIND_INVALID)
        self.assertFalse(result.alive)
        self.assertIn("No hay URL", result.detail)

    def test_a_non_http_scheme_is_rejected(self):
        result = probe_endpoint("file:///etc/passwd", "openai", opener=forbidden)
        self.assertEqual(result.kind, KIND_INVALID)

    def test_cloud_metadata_addresses_are_never_contacted(self):
        for url in (
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
        ):
            self.assertTrue(is_blocked_url(url), url)
            result = probe_endpoint(url, "openai-compatible", opener=forbidden)
            self.assertEqual(result.kind, KIND_BLOCKED, url)
            self.assertIn("metadatos", result.detail)

    def test_unsupported_protocols_are_admitted_honestly(self):
        result = probe_endpoint(
            "https://bedrock-runtime.us-east-1.amazonaws.com",
            "bedrock", opener=forbidden,
        )
        self.assertEqual(result.kind, KIND_UNSUPPORTED)
        self.assertIn("no querría decir nada", result.detail)

    def test_reason_matches_the_refusal(self):
        self.assertIn("baseURL", unproposable_reason("", "openai"))
        self.assertIn("metadatos", unproposable_reason(
            "http://169.254.169.254/", "openai"))
        self.assertIn("azure", unproposable_reason("https://x.test", "azure"))
        self.assertEqual(unproposable_reason(URL, "openai-compatible"), "")


class TestTransport(unittest.TestCase):
    """Cada fallo de red tiene su explicación, sin inventar causas."""

    def probe(self, error: Exception) -> ProbeResult:
        return probe_endpoint(URL, "openai-compatible", opener=RecordingOpener(error=error))

    def test_anonymous_requests_carry_no_credentials(self):
        opener = RecordingOpener(FakeResponse(payload={"data": []}))
        probe_endpoint(URL, "openai-compatible", opener=opener)
        headers = opener.headers()
        self.assertNotIn("authorization", headers)
        self.assertNotIn("x-api-key", headers)
        self.assertEqual(headers["accept"], "application/json")

    def test_the_key_travels_as_bearer_only_when_explicitly_asked(self):
        opener = RecordingOpener(FakeResponse(payload={"data": []}))
        probe_endpoint(URL, "openai-compatible", api_key=KEY, opener=opener)
        self.assertEqual(opener.header("Authorization"), f"Bearer {KEY}")

    def test_anthropic_uses_its_own_header(self):
        opener = RecordingOpener(FakeResponse(payload={"data": []}))
        probe_endpoint(
            "https://api.anthropic.com", "anthropic", api_key=KEY, opener=opener,
        )
        headers = opener.headers()
        self.assertEqual(headers["x-api-key"], KEY)
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertNotIn("authorization", headers)
        self.assertTrue(opener.requests[-1].full_url.endswith("/v1/models"))

    def test_a_key_is_never_sent_in_cleartext_to_a_remote_host(self):
        result = probe_endpoint(
            "http://api.acme.test/v1", "openai-compatible",
            api_key=KEY, opener=forbidden,
        )
        self.assertEqual(result.kind, KIND_BLOCKED)
        self.assertIn("sin cifrar", result.summary)
        self.assertNotIn(KEY, result.report())

    def test_a_key_may_go_in_cleartext_to_loopback(self):
        opener = RecordingOpener(FakeResponse(payload={"data": []}))
        result = probe_endpoint(
            "http://127.0.0.1:11434/v1", "openai-compatible",
            api_key=KEY, opener=opener,
        )
        self.assertEqual(result.kind, KIND_OK)
        self.assertEqual(opener.header("Authorization"), f"Bearer {KEY}")

    def test_dns_failure(self):
        result = self.probe(urllib.error.URLError(socket.gaierror(-2, "Name or service not known")))
        self.assertEqual(result.kind, KIND_DNS)
        self.assertIn("no resuelve", result.summary)

    def test_connection_refused(self):
        result = self.probe(urllib.error.URLError(ConnectionRefusedError(111, "refused")))
        self.assertEqual(result.kind, KIND_REFUSED)
        self.assertIn("Ollama", result.detail)

    def test_timeout(self):
        result = self.probe(urllib.error.URLError(socket.timeout("timed out")))
        self.assertEqual(result.kind, KIND_TIMEOUT)
        self.assertIn("12", result.summary)

    def test_tls_failure(self):
        error = ssl.SSLCertVerificationError(1, "certificate verify failed")
        result = self.probe(urllib.error.URLError(error))
        self.assertEqual(result.kind, KIND_TLS)
        self.assertIn("certificado", result.detail)

    def test_an_unexpected_failure_is_still_reported(self):
        result = self.probe(urllib.error.URLError("proxy caído"))
        self.assertEqual(result.kind, "error")
        self.assertIn("proxy caído", result.detail)

    def test_the_key_is_redacted_from_any_message(self):
        # Un opener hostil podría hacer eco de la cabecera en el error.
        error = urllib.error.URLError(f"rechazado: Bearer {KEY}")
        result = probe_endpoint(
            URL, "openai-compatible", api_key=KEY,
            opener=RecordingOpener(error=error),
        )
        self.assertNotIn(KEY, result.report())
        self.assertNotIn(KEY, result.summary)
        self.assertIn("«clave»", result.detail)

    def test_latency_is_measured_and_the_response_is_closed(self):
        response = FakeResponse(payload={"data": []})
        opener = RecordingOpener(response)
        result = probe_endpoint(URL, "openai", opener=opener, timeout=7)
        self.assertIsInstance(result.latency_ms, int)
        self.assertGreaterEqual(result.latency_ms, 0)
        self.assertTrue(response.closed)
        self.assertEqual(opener.timeouts, [7])


class TestStatuses(unittest.TestCase):
    """El código HTTP se traduce a algo que el usuario pueda accionar."""

    @staticmethod
    def probe(status: int, headers: dict | None = None, api_key: str = "") -> ProbeResult:
        error = urllib.error.HTTPError(
            URL, status, "msg", headers or {}, io.BytesIO(b"{}"),
        )
        return probe_endpoint(
            URL, "openai-compatible", api_key=api_key,
            opener=RecordingOpener(error=error),
        )

    def test_401_without_a_key_means_the_endpoint_is_alive(self):
        result = self.probe(401)
        self.assertEqual(result.kind, KIND_AUTH)
        self.assertTrue(result.alive)
        self.assertIn("/connect", result.detail)

    def test_401_with_a_key_means_the_credential_is_wrong(self):
        result = self.probe(401, api_key=KEY)
        self.assertEqual(result.kind, KIND_DENIED)
        self.assertFalse(result.alive)
        self.assertNotIn(KEY, result.report())

    def test_403_is_treated_as_alive(self):
        self.assertEqual(self.probe(403).kind, KIND_AUTH)

    def test_404_points_at_the_v1_suffix(self):
        result = self.probe(404)
        self.assertEqual(result.kind, KIND_NOT_FOUND)
        self.assertIn("/v1", result.detail)
        self.assertEqual(result.status, 404)

    def test_429_is_alive_but_saturated(self):
        result = self.probe(429)
        self.assertEqual(result.kind, KIND_RATE_LIMITED)
        self.assertTrue(result.alive)

    def test_5xx_is_the_server_fault(self):
        result = self.probe(503)
        self.assertEqual(result.kind, KIND_SERVER)
        self.assertIn("de su lado", result.detail)

    def test_a_redirect_is_reported_and_never_followed(self):
        result = self.probe(302, {"Location": "https://otro.example/robo"})
        self.assertEqual(result.kind, KIND_REDIRECT)
        self.assertIn("otro.example", result.detail)
        self.assertIn("No seguimos", result.detail)


class TestBodies(unittest.TestCase):
    """Del cuerpo solo se sacan los IDs; nada se guarda ni se ejecuta."""

    def probe(self, payload=None, raw: bytes | None = None, headers=None,
              wanted=()) -> ProbeResult:
        return probe_endpoint(
            URL, "openai-compatible", wanted_models=wanted,
            opener=RecordingOpener(
                FakeResponse(payload=payload, raw=raw, headers=headers)
            ),
        )

    def test_openai_listing(self):
        result = self.probe({"object": "list", "data": [
            {"id": "acme-coder"}, {"id": "acme-lite"},
        ]}, wanted=("acme-coder", "no-existe"))
        self.assertEqual(result.kind, KIND_OK)
        self.assertTrue(result.alive)
        self.assertEqual(result.models, ("acme-coder", "acme-lite"))
        self.assertEqual(result.present, ("acme-coder",))
        self.assertEqual(result.missing, ("no-existe",))
        self.assertIn("no-existe", result.line())

    def test_anthropic_listing(self):
        result = self.probe({"data": [
            {"id": "claude-x", "display_name": "Claude X"},
        ]})
        self.assertEqual(result.models, ("claude-x",))

    def test_a_map_of_models(self):
        self.assertEqual(
            extract_model_ids({"models": {"m1": {}, "m2": {}}}), ["m1", "m2"],
        )

    def test_a_bare_list(self):
        self.assertEqual(extract_model_ids(["a", "b", "a"]), ["a", "b"])

    def test_an_empty_listing_is_still_an_operational_endpoint(self):
        result = self.probe({"data": []})
        self.assertEqual(result.kind, KIND_OK)
        self.assertIn("sin modelos listados", result.summary)

    def test_html_is_not_json(self):
        result = self.probe(raw=b"<!doctype html><h1>404</h1>")
        self.assertEqual(result.kind, KIND_UNREADABLE)
        self.assertIn("no es JSON", result.summary)

    def test_json_that_is_not_a_catalog(self):
        result = self.probe(raw=b"42")
        self.assertEqual(result.kind, KIND_UNREADABLE)
        self.assertIn("int", result.detail)

    def test_gzip_is_understood(self):
        body = gzip.compress(json.dumps({"data": [{"id": "m1"}]}).encode())
        result = self.probe(raw=body, headers={"Content-Encoding": "gzip"})
        self.assertEqual(result.kind, KIND_OK)
        self.assertEqual(result.models, ("m1",))

    def test_the_report_says_what_was_requested(self):
        result = self.probe({"data": [{"id": "m1"}]})
        self.assertIn("GET https://api.acme.test/v1/models", result.report())
        self.assertIn("Endpoint operativo", result.report())

    def test_plural_agreement(self):
        one = self.probe({"data": [{"id": "m1"}]})
        self.assertIn("1 modelo anunciado", one.line())
        two = self.probe({"data": [{"id": "m1"}, {"id": "m2"}]})
        self.assertIn("2 modelos anunciados", two.line())


class TestEnvironmentHelpers(unittest.TestCase):
    """Presencia y ausencia de la variable: el valor no sale de aquí."""

    def test_status_never_returns_the_value(self):
        with mock.patch.dict(os.environ, {"OMM_PRESENT": KEY}, clear=False):
            os.environ.pop("OMM_ABSENT", None)
            status = env_status(["OMM_PRESENT", "OMM_ABSENT"])
        self.assertEqual(status, [("OMM_PRESENT", True), ("OMM_ABSENT", False)])
        self.assertNotIn(KEY, repr(status))

    def test_an_empty_variable_counts_as_absent(self):
        with mock.patch.dict(os.environ, {"OMM_EMPTY": "   "}, clear=False):
            self.assertEqual(first_present_env(["OMM_EMPTY"]), ("", ""))

    def test_the_first_present_variable_wins(self):
        with mock.patch.dict(os.environ, {"OMM_B": "b-value"}, clear=False):
            os.environ.pop("OMM_A", None)
            self.assertEqual(
                first_present_env(["OMM_A", "OMM_B"]), ("OMM_B", "b-value"),
            )

    def test_key_offer_needs_a_declared_variable(self):
        can, why = key_offer(URL, "openai", [])
        self.assertFalse(can)
        self.assertIn("no declara", why)

    def test_key_offer_needs_the_variable_to_exist(self):
        os.environ.pop("OMM_NOPE", None)
        can, why = key_offer(URL, "openai", ["OMM_NOPE"])
        self.assertFalse(can)
        self.assertIn("no está definida", why)

    def test_key_offer_refuses_cleartext_to_a_remote_host(self):
        with mock.patch.dict(os.environ, {"OMM_KEY": KEY}, clear=False):
            can, why = key_offer("http://api.acme.test/v1", "openai", ["OMM_KEY"])
        self.assertFalse(can)
        self.assertIn("sin cifrar", why)

    def test_key_offer_allows_loopback_and_https(self):
        with mock.patch.dict(os.environ, {"OMM_KEY": KEY}, clear=False):
            self.assertTrue(key_offer(URL, "openai", ["OMM_KEY"])[0])
            self.assertTrue(
                key_offer("http://localhost:8080/v1", "openai", ["OMM_KEY"])[0]
            )

    def test_key_offer_is_never_made_for_an_unproposable_endpoint(self):
        self.assertEqual(key_offer("", "openai", ["PATH"]), (False, unproposable_reason("", "openai")))


class TestLoopback(unittest.TestCase):
    """El urllib real, contra un servidor local: sin red exterior."""

    @classmethod
    def setUpClass(cls):
        cls.hits: list[tuple[str, str]] = []
        cls.second_hits: list[str] = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 (nombre impuesto por http.server)
                cls.hits.append((self.path, self.headers.get("Authorization", "")))
                if self.path.startswith("/redirect"):
                    self.send_response(302)
                    self.send_header("Location", cls.second_url + "/models")
                    self.end_headers()
                    return
                if self.path.startswith("/unauthorized"):
                    self._json(401, {"error": "no key"})
                    return
                if self.path.startswith("/missing"):
                    self._json(404, {"error": "not found"})
                    return
                self._json(200, {"object": "list", "data": [{"id": "local-model"}]})

            def _json(self, status, payload):
                body = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):  # silencio en la salida del test
                pass

        class Second(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                cls.second_hits.append(self.path)
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        cls.second = ThreadingHTTPServer(("127.0.0.1", 0), Second)
        cls.second_url = f"http://127.0.0.1:{cls.second.server_port}"
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        for server in (cls.server, cls.second):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

    @classmethod
    def tearDownClass(cls):
        for server in (cls.server, cls.second):
            server.shutdown()
            server.server_close()

    def setUp(self):
        # Que ningún proxy del entorno se interponga en loopback.
        patcher = mock.patch.dict(os.environ, {"no_proxy": "*", "NO_PROXY": "*"})
        patcher.start()
        self.addCleanup(patcher.stop)
        type(self).hits = []
        type(self).second_hits = []

    def test_a_200_listing(self):
        result = probe_endpoint(self.base + "/v1", "openai-compatible", timeout=5)
        self.assertEqual(result.kind, KIND_OK, result.report())
        self.assertEqual(result.models, ("local-model",))
        self.assertEqual(type(self).hits[-1][0], "/v1/models")

    def test_a_401_is_a_live_endpoint(self):
        result = probe_endpoint(self.base + "/unauthorized", "openai", timeout=5)
        self.assertEqual(result.kind, KIND_AUTH, result.report())

    def test_a_404(self):
        result = probe_endpoint(self.base + "/missing", "openai", timeout=5)
        self.assertEqual(result.kind, KIND_NOT_FOUND, result.report())

    def test_a_redirect_is_never_followed(self):
        result = probe_endpoint(self.base + "/redirect", "openai", timeout=5,
                                api_key=KEY)
        self.assertEqual(result.kind, KIND_REDIRECT, result.report())
        self.assertEqual(type(self).second_hits, [])
        self.assertIn("127.0.0.1", result.detail)

    def test_the_key_is_sent_when_asked_on_loopback(self):
        probe_endpoint(self.base + "/v1", "openai", api_key=KEY, timeout=5)
        self.assertEqual(type(self).hits[-1][1], f"Bearer {KEY}")

    def test_a_port_with_nobody_home_is_refused(self):
        closed = socket.socket()
        closed.bind(("127.0.0.1", 0))
        port = closed.getsockname()[1]
        closed.close()
        result = probe_endpoint(
            f"http://127.0.0.1:{port}/v1", "openai-compatible", timeout=2,
        )
        self.assertIn(result.kind, (KIND_REFUSED, KIND_TIMEOUT), result.report())

    def test_the_default_opener_stops_redirects_at_the_urllib_level(self):
        request = urllib.request.Request(self.base + "/redirect")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            default_opener(request, 5)
        self.assertEqual(caught.exception.code, 302)
        self.assertEqual(type(self).second_hits, [])

    def test_transport_helpers(self):
        self.assertEqual(host_of(self.base + "/v1"), "127.0.0.1")
        self.assertTrue(key_transport_ok(self.base))
        self.assertTrue(key_transport_ok("https://x.test"))
        self.assertFalse(key_transport_ok("http://x.test"))


if __name__ == "__main__":
    unittest.main()
