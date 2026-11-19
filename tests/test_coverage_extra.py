from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from swarmlab.api import build_server
from swarmlab.mcp import McpDispatcher
from swarmlab.store import SwarmError, SwarmStore


def _req(method, url, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            try:
                payload = json.loads(raw or b"{}")
            except ValueError:
                payload = {"raw": raw.decode("utf-8", "replace")}
            return r.status, payload, dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), dict(e.headers)


class ExtraStoreTests(unittest.TestCase):
    def test_store_edges(self) -> None:
        s = SwarmStore(":memory:")
        try:
            s.register("a", ["x"])
            self.assertEqual(s.heartbeat("a")["agent_id"], "a")
            with self.assertRaises(SwarmError):
                s.heartbeat("nope")
            task = s.submit("x", {})
            claimed = s.claim("a", "x")
            renewed = s.renew(task["task_id"], "a", 10, claimed["lease_epoch"])
            self.assertIn("lease_until", renewed)
            self.assertEqual(s.tasks("claimed")[0]["task_id"], task["task_id"])
            self.assertEqual(s.tasks()[0]["task_id"], task["task_id"])
            self.assertIn("events", s.stats())
        finally:
            s.close()


class ExtraApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SwarmStore(":memory:")
        self.server = build_server(self.store, "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.store.close()

    def test_ready_failure(self) -> None:
        def boom():
            raise RuntimeError("db down")
        self.store.stats = boom
        try:
            status, _, _ = _req("GET", self.base + "/ready")
            self.assertEqual(status, 503)
        finally:
            del self.store.stats

    def test_body_limit(self) -> None:
        from swarmlab import api
        old = api.MAX_BODY
        api.MAX_BODY = 4
        other = build_server(SwarmStore(":memory:"), "127.0.0.1", 0)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{other.server_address[1]}"
        try:
            req = urllib.request.Request(base + "/v1/tasks", data=b'{"capability":"long"}', method="POST")
            req.add_header("Content-Type", "application/json")
            try:
                urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 400)
        finally:
            other.shutdown(); other.server_close(); thread.join(timeout=5)
            api.MAX_BODY = old

    def test_api_backpressure(self) -> None:
        import os
        os.environ["SWARMLAB_MAX_PENDING"] = "1"
        try:
            _req("POST", self.base + "/v1/tasks", {"capability": "bp"})
            status, _, _ = _req("POST", self.base + "/v1/tasks", {"capability": "bp"})
            self.assertIn(status, (409, 429))
        finally:
            os.environ.pop("SWARMLAB_MAX_PENDING", None)

    def test_message_stream_keepalive(self) -> None:
        resp = urllib.request.urlopen(self.base + "/v1/messages/stream?after=999999&limit=1&timeout_s=1.4", timeout=5)
        body = resp.read()
        self.assertIn(b"keepalive", body)

    def test_message_stream_head(self) -> None:
        import http.client
        from urllib.parse import urlparse
        parsed = urlparse(self.base)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
        conn.request("HEAD", "/v1/messages/stream?after=0&limit=1&timeout_s=0.2")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.read(), b"")

    def test_stream_keepalive(self) -> None:
        resp = urllib.request.urlopen(self.base + "/v1/stream?after=999999&limit=1&timeout_s=1.4", timeout=5)
        try:
            self.assertIn(b": keepalive", resp.read())
        finally:
            resp.close()

    def test_task_capability_filter(self) -> None:
        _req("POST", self.base + "/v1/tasks", {"capability": "filter"})
        _, body, _ = _req("GET", self.base + "/v1/tasks?capability=filter")
        self.assertTrue(body["data"])
        self.assertTrue(all(t["capability"] == "filter" for t in body["data"]))
        self.assertEqual(_req("GET", self.base + "/v1/tasks?capability=nope")[1]["data"], [])

    def test_agent_api(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "prof", "capabilities": ["p"]})
        status, body, _ = _req("GET", self.base + "/v1/agents/prof")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["agent_id"], "prof")
        self.assertEqual(_req("GET", self.base + "/v1/agents/nope")[0], 404)

    def test_api_error_branches(self) -> None:
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "err"})
        task_id = body["data"]["task_id"]
        status, _, _ = _req("POST", self.base + f"/v1/tasks/{task_id}/renew", {"agent_id": "x", "lease_s": "bad"})
        self.assertEqual(status, 400)
        from swarmlab.store import SwarmError
        self.store.tasks = lambda *a, **k: (_ for _ in ()).throw(SwarmError("BAD_REQUEST", "boom"))
        try:
            self.assertEqual(_req("GET", self.base + "/v1/tasks")[0], 400)
        finally:
            del self.store.tasks

    def test_log_message_json(self) -> None:
        import contextlib
        import io
        import json
        import os

        from swarmlab.api import SwarmHandler
        handler = object.__new__(SwarmHandler)
        handler.request_id = "req"
        handler.address_string = lambda: "127.0.0.1"
        os.environ["SWARMLAB_LOG_FORMAT"] = "json"
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                handler.log_message("hello %s", "world")
        finally:
            os.environ.pop("SWARMLAB_LOG_FORMAT", None)
        record = json.loads(buf.getvalue().strip())
        self.assertEqual(record["msg"], "hello world")
        self.assertEqual(record["request_id"], "req")

    def test_json_logs(self) -> None:
        import contextlib
        import io
        import json
        import os
        os.environ["SWARMLAB_LOG_FORMAT"] = "json"
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                _req("GET", self.base + "/health")
        finally:
            os.environ.pop("SWARMLAB_LOG_FORMAT", None)
        records = []
        for line in buf.getvalue().splitlines():
            try:
                records.append(json.loads(line))
            except ValueError:
                pass
        matches = [r for r in records if r.get("path") == "/health" and r.get("status") == 200]
        self.assertTrue(matches)
        self.assertTrue(matches[0].get("request_id"))

    def test_message_stream_disconnect(self) -> None:
        import os
        import socket
        import time
        from urllib.parse import urlparse
        parsed = urlparse(self.base)
        sock = socket.create_connection((parsed.hostname, parsed.port), timeout=2)
        os.environ["SWARMLAB_STREAM_KEEPALIVE_S"] = "0.1"
        try:
            sock.sendall(b"GET /v1/messages/stream?after=999999&limit=1&timeout_s=2 HTTP/1.1\r\nHost: x\r\n\r\n")
            sock.close()
            time.sleep(1.2)
        finally:
            os.environ.pop("SWARMLAB_STREAM_KEEPALIVE_S", None)

    def test_message_stream_broken_pipe(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        from swarmlab.api import SwarmHandler
        h = object.__new__(SwarmHandler)
        h.send_response = MagicMock()
        h.send_header = MagicMock()
        h.end_headers = MagicMock()
        h.wfile = MagicMock()
        h.wfile.write.side_effect = BrokenPipeError()
        h._head = False
        h.server = SimpleNamespace(store=SimpleNamespace(messages=lambda *a: [{"id": 1, "body": "x"}]))
        h._messages_stream(0, "", None, 1, 1)

    def test_stream_disconnect(self) -> None:
        import socket
        import time
        from urllib.parse import urlparse
        parsed = urlparse(self.base)
        sock = socket.create_connection((parsed.hostname, parsed.port), timeout=3)
        sock.sendall(b"GET /v1/stream?after=999999&limit=1&timeout_s=2 HTTP/1.1\r\nHost: x\r\n\r\n")
        sock.recv(64)
        sock.close()
        time.sleep(1.2)
        self.assertEqual(_req("GET", self.base + "/health")[0], 200)

    def test_stream_keepalive_env(self) -> None:
        import os
        os.environ["SWARMLAB_STREAM_KEEPALIVE_S"] = "0.1"
        try:
            resp = urllib.request.urlopen(self.base + "/v1/stream?after=999999&limit=1&timeout_s=0.4", timeout=5)
            try:
                self.assertIn(b": keepalive", resp.read())
            finally:
                resp.close()
        finally:
            os.environ.pop("SWARMLAB_STREAM_KEEPALIVE_S", None)

    def test_stream_listener_success(self) -> None:
        import threading
        from unittest.mock import patch

        from swarmlab.api import build_server
        store = SwarmStore(":memory:")
        store.dsn = "postgresql://x"
        store.backend = "postgres"
        other = build_server(store, "127.0.0.1", 0)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{other.server_address[1]}"
        class FakeListener:
            def wait(self, timeout=None):
                return None
            def close(self):
                return None
        try:
            with patch("swarmlab.events.PgEventStream", return_value=FakeListener()):
                resp = urllib.request.urlopen(base + "/v1/stream?after=0&limit=1&timeout_s=0.1", timeout=5)
                try:
                    self.assertEqual(resp.status, 200)
                    resp.read()
                finally:
                    resp.close()
        finally:
            other.shutdown(); other.server_close(); thread.join(timeout=5)

    def test_stream_listener_failure(self) -> None:
        import threading
        from unittest.mock import patch

        from swarmlab.api import build_server
        store = SwarmStore(":memory:")
        store.dsn = "postgresql://x"
        store.backend = "postgres"
        other = build_server(store, "127.0.0.1", 0)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{other.server_address[1]}"
        try:
            with patch("swarmlab.events.PgEventStream", side_effect=RuntimeError("no pg")):
                resp = urllib.request.urlopen(base + "/v1/stream?after=0&limit=1&timeout_s=0.1", timeout=5)
                try:
                    self.assertEqual(resp.status, 200)
                    resp.read()
                finally:
                    resp.close()
        finally:
            other.shutdown(); other.server_close(); thread.join(timeout=5)

    def test_stream_empty(self) -> None:
        with urllib.request.urlopen(self.base + "/v1/stream?after=999999&limit=1&timeout_s=0.1", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            resp.read()

    def test_lease_env(self) -> None:
        import os
        import time
        os.environ["SWARMLAB_LEASE_S"] = "120"
        try:
            _req("POST", self.base + "/v1/agents", {"agent_id": "le", "capabilities": ["le"]})
            _req("POST", self.base + "/v1/tasks", {"capability": "le"})
            _, claim, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "le", "capability": "le"})
            self.assertGreater(claim["data"]["lease_until"], time.time() + 100)
        finally:
            os.environ.pop("SWARMLAB_LEASE_S", None)

    def test_tokens_invalid(self) -> None:
        import os

        from swarmlab.api import build_server
        os.environ["SWARMLAB_TOKENS"] = "not-json"
        try:
            other = build_server(SwarmStore(":memory:"), "127.0.0.1", 0)
        finally:
            os.environ.pop("SWARMLAB_TOKENS", None)
        other.server_close()

    def test_delete_rate(self) -> None:
        import os
        os.environ["SWARMLAB_RATE_RPS"] = "1"
        try:
            req = urllib.request.Request(self.base + "/v1/agents/x", method="DELETE")
            codes = []
            for _ in range(2):
                try:
                    urllib.request.urlopen(req, timeout=3)
                except urllib.error.HTTPError as exc:
                    codes.append(exc.code)
            self.assertIn(429, codes)
        finally:
            os.environ.pop("SWARMLAB_RATE_RPS", None)

    def test_jwt(self) -> None:
        import base64
        import hashlib
        import hmac
        import json
        import os
        import time

        def b64(value: bytes) -> str:
            return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

        def make(payload: dict, secret: str) -> str:
            head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
            body = b64(json.dumps(payload).encode())
            sig = b64(hmac.new(secret.encode(), f"{head}.{body}".encode(), hashlib.sha256).digest())
            return f"{head}.{body}.{sig}"

        os.environ["SWARMLAB_JWT_SECRET"] = "jwt-secret"
        try:
            token = make({"sub": "a", "exp": int(time.time()) + 60}, "jwt-secret")
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, token)[0], 200)
            readonly = make({"sub": "a", "scope": "read", "exp": int(time.time()) + 60}, "jwt-secret")
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, readonly)[0], 200)
            self.assertEqual(_req("POST", self.base + "/v1/tasks", {"capability": "j"}, readonly)[0], 403)
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, make({"exp": int(time.time()) - 1}, "jwt-secret"))[0], 401)
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, make({"exp": int(time.time()) + 60}, "wrong"))[0], 401)
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, make({"nbf": int(time.time()) + 60}, "jwt-secret"))[0], 401)
            none_head = b64(json.dumps({"alg": "none", "typ": "JWT"}).encode())
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, f"{none_head}.e30.e30")[0], 401)
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, "a.b.c")[0], 401)
            rs_head = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
            rs_body = b64(json.dumps({"exp": int(time.time()) + 60}).encode())
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, f"{rs_head}.{rs_body}.e30")[0], 401)
            os.environ["SWARMLAB_JWT_PUBLIC_KEY"] = "not-a-pem"
            try:
                self.assertEqual(_req("GET", self.base + "/v1/stats", None, f"{rs_head}.{rs_body}.e30")[0], 401)
            finally:
                os.environ.pop("SWARMLAB_JWT_PUBLIC_KEY", None)
            import os as _os
            _os.environ["SWARMLAB_JWT_ISSUER"] = "issuer"
            _os.environ["SWARMLAB_JWT_AUDIENCE"] = "swarm"
            try:
                ok = make({"iss": "issuer", "aud": "swarm", "exp": int(time.time()) + 60}, "jwt-secret")
                self.assertEqual(_req("GET", self.base + "/v1/stats", None, ok)[0], 200)
                bad = make({"iss": "other", "aud": "swarm", "exp": int(time.time()) + 60}, "jwt-secret")
                self.assertEqual(_req("GET", self.base + "/v1/stats", None, bad)[0], 401)
                bad_aud = make({"iss": "issuer", "aud": "other", "exp": int(time.time()) + 60}, "jwt-secret")
                self.assertEqual(_req("GET", self.base + "/v1/stats", None, bad_aud)[0], 401)
                list_aud = make({"iss": "issuer", "aud": ["swarm", "other"], "exp": int(time.time()) + 60}, "jwt-secret")
                self.assertEqual(_req("GET", self.base + "/v1/stats", None, list_aud)[0], 200)
                wrong_list = make({"iss": "issuer", "aud": ["other"], "exp": int(time.time()) + 60}, "jwt-secret")
                self.assertEqual(_req("GET", self.base + "/v1/stats", None, wrong_list)[0], 401)
            finally:
                _os.environ.pop("SWARMLAB_JWT_ISSUER", None)
                _os.environ.pop("SWARMLAB_JWT_AUDIENCE", None)
        finally:
            os.environ.pop("SWARMLAB_JWT_SECRET", None)

    def test_jwt_rs256(self) -> None:
        import base64
        import json
        import os
        import time

        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        def b64(value: bytes) -> str:
            return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_pem = private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        head = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        body = b64(json.dumps({"sub": "rsa", "exp": int(time.time()) + 60}).encode())
        signature = private.sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256())
        token = f"{head}.{body}.{b64(signature)}"
        os.environ["SWARMLAB_JWT_PUBLIC_KEY"] = public_pem
        try:
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, token)[0], 200)
            hs_head = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
            hs_body = b64(json.dumps({"exp": int(time.time()) + 60}).encode())
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, f"{hs_head}.{hs_body}.e30")[0], 401)
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, f"{head}.{body}.{b64(b'bad')}")[0], 401)
        finally:
            os.environ.pop("SWARMLAB_JWT_PUBLIC_KEY", None)

    def test_jwt_jwks(self) -> None:
        import base64
        import json
        import os
        import threading
        import time
        from http.server import BaseHTTPRequestHandler, HTTPServer

        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa

        def b64(value: bytes) -> str:
            return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        numbers = private.public_key().public_numbers()
        jwk = {"kty": "RSA", "kid": "k1", "alg": "RS256",
               "n": b64(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")),
               "e": b64(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big"))}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                data = {"keys": [jwk]} if self.path == "/jwks" else {"keys": "bad"}
                body = json.dumps(data).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:
                return

        srv = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        head = b64(json.dumps({"alg": "RS256", "typ": "JWT", "kid": "k1"}).encode())
        body = b64(json.dumps({"sub": "j", "exp": int(time.time()) + 60}).encode())
        sig = b64(private.sign(f"{head}.{body}".encode(), padding.PKCS1v15(), hashes.SHA256()))
        token = f"{head}.{body}.{sig}"
        os.environ["SWARMLAB_JWT_JWKS_URL"] = f"http://127.0.0.1:{srv.server_port}/jwks"
        try:
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, token)[0], 200)
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, token)[0], 200)
            bad_head = b64(json.dumps({"alg": "RS256", "typ": "JWT", "kid": "no"}).encode())
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, f"{bad_head}.{body}.{sig}")[0], 401)
            os.environ["SWARMLAB_JWT_JWKS_URL"] = f"http://127.0.0.1:{srv.server_port}/bad"
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, token)[0], 401)
            os.environ["SWARMLAB_JWT_JWKS_URL"] = "http://127.0.0.1:1/jwks"
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, token)[0], 401)
        finally:
            os.environ.pop("SWARMLAB_JWT_JWKS_URL", None)
            srv.shutdown()
            srv.server_close()

    def test_delete_auth(self) -> None:
        from swarmlab.api import build_server
        other = build_server(SwarmStore(":memory:"), "127.0.0.1", 0, "tok")
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{other.server_address[1]}"
        try:
            req = urllib.request.Request(base + "/v1/agents/x", method="DELETE")
            try:
                urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 401)
            req = urllib.request.Request(base + "/nope", method="DELETE")
            req.add_header("Authorization", "Bearer tok")
            try:
                urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 404)
        finally:
            other.shutdown(); other.server_close(); thread.join(timeout=5)

    def test_query_filters(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "q", "capabilities": ["q"]})
        _req("POST", self.base + "/v1/tasks", {"capability": "q"})
        self.assertEqual(_req("GET", self.base + "/v1/agents?capability=q&limit=1")[0], 200)
        self.assertEqual(_req("GET", self.base + "/v1/tasks?status=pending&limit=1")[0], 200)
        self.assertEqual(_req("GET", self.base + "/v1/events?after=0&limit=1")[0], 200)
        self.assertEqual(_req("GET", self.base + "/v1/tasks?limit=bad")[0], 400)
        self.assertEqual(_req("GET", self.base + "/v1/agents?limit=bad")[0], 400)

    def test_openapi(self) -> None:
        status, body, _ = _req("GET", self.base + "/v1/openapi")
        self.assertEqual(status, 200)
        self.assertEqual(body["openapi"], "3.1.0")
        self.assertIn("/v1/tasks/{task_id}/complete", body["paths"])

    def test_version_capabilities(self) -> None:
        status, body, _ = _req("GET", self.base + "/v1/version")
        self.assertEqual(status, 200)
        self.assertIn("version", body["data"])
        status, body, _ = _req("GET", self.base + "/v1/capabilities")
        self.assertEqual(status, 200)
        self.assertIn("batch", body["data"]["features"])

    def test_deregister_api(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "del", "capabilities": ["x"]})
        req = urllib.request.Request(self.base + "/v1/agents/del", method="DELETE")
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
        self.assertEqual(_req("GET", self.base + "/v1/agents?capability=x")[1]["data"], [])
        req = urllib.request.Request(self.base + "/nope", method="DELETE")
        try:
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)

    def test_max_attempts_api(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "ma", "capabilities": ["ma"]})
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "ma", "max_attempts": 1})
        task_id = body["data"]["task_id"]
        _, claim, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "ma", "capability": "ma"})
        self.assertEqual(claim["data"]["attempts"], 1)
        _, task, _ = _req("GET", self.base + f"/v1/tasks/{task_id}")
        self.assertEqual(task["data"]["max_attempts"], 1)

    def test_batch_maintenance(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "bm", "capabilities": ["bm"]})
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "bm"})
        task_id = body["data"]["task_id"]
        _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "bm", "capability": "bm"})
        status, body, _ = _req("POST", self.base + "/v1/batch", {"ops": [
            {"op": "cancel", "task_id": task_id, "agent_id": "bm"},
            {"op": "requeue", "task_id": task_id},
            {"op": "expire"},
        ]})
        self.assertEqual(status, 200)
        self.assertTrue(all(r.get("ok") for r in body["data"]))
        # пустое тело POST
        req = urllib.request.Request(self.base + "/v1/batch", data=b"", method="POST")
        try:
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)

    def test_dependencies_api(self) -> None:
        _, first, _ = _req("POST", self.base + "/v1/tasks", {"capability": "dep"})
        first_id = first["data"]["task_id"]
        _, second, _ = _req("POST", self.base + "/v1/tasks", {"capability": "dep", "depends_on": first_id})
        second_id = second["data"]["task_id"]
        _req("POST", self.base + "/v1/agents", {"agent_id": "dep", "capabilities": ["dep"]})
        _, claim, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "dep", "capability": "dep"})
        self.assertEqual(claim["data"]["task_id"], first_id)
        _, claim2, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "dep", "capability": "dep"})
        self.assertIsNone(claim2["data"])
        _req("POST", self.base + f"/v1/tasks/{first_id}/complete", {"agent_id": "dep", "fence": claim["data"]["lease_epoch"]})
        _, claim3, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "dep", "capability": "dep"})
        self.assertEqual(claim3["data"]["task_id"], second_id)

    def test_audit_failure(self) -> None:
        original = self.store.audit
        self.store.audit = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            status, _, _ = _req("POST", self.base + "/v1/tasks", {"capability": "fail"})
            self.assertEqual(status, 200)
        finally:
            self.store.audit = original

    def test_audit_filter_api(self) -> None:
        _req("POST", self.base + "/v1/tasks", {"capability": "au2"})
        status, body, _ = _req("GET", self.base + "/v1/audit?action=api.mutation&limit=1")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["data"]), 1)

    def test_root(self) -> None:
        status, body, _ = _req("GET", self.base + "/")
        self.assertEqual(status, 200)
        self.assertIn("swarm-lab", body.get("raw", ""))
        self.assertIn("/ready", body.get("raw", ""))

    def test_agent_register(self) -> None:
        import os
        self.server.token = "admin"
        os.environ["SWARMLAB_JOIN_CODE"] = "join-me"
        try:
            status, body, _ = _req("POST", self.base + "/v1/agents/register", {
                "agent_id": "self1", "capabilities": ["x"], "join_code": "join-me",
            })
            self.assertEqual(status, 201)
            token = body["data"]["token"]
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, token)[0], 200)
            self.assertEqual(_req("POST", self.base + "/v1/agents/register", {
                "agent_id": "self2", "join_code": "wrong",
            })[0], 403)
            os.environ.pop("SWARMLAB_JOIN_CODE", None)
            self.assertEqual(_req("POST", self.base + "/v1/agents/register", {
                "agent_id": "self3", "join_code": "join-me",
            })[0], 403)
            os.environ["SWARMLAB_JOIN_CODE"] = "join-me"
            self.assertEqual(_req("DELETE", self.base + "/v1/agents/self1", None, token)[0], 200)
            self.assertEqual(_req("GET", self.base + "/v1/stats", None, token)[0], 401)
        finally:
            os.environ.pop("SWARMLAB_JOIN_CODE", None)
            self.server.token = ""

    def test_agent_register_errors(self) -> None:
        import os
        from unittest.mock import patch
        os.environ["SWARMLAB_JOIN_CODE"] = "join-me"
        try:
            self.assertEqual(_req("POST", self.base + "/v1/agents/register", {
                "agent_id": "bad", "capabilities": "x", "join_code": "join-me",
            })[0], 400)
            with patch("swarmlab.api.SwarmHandler._rate_ok", return_value=False):
                self.assertEqual(_req("POST", self.base + "/v1/agents/register", {
                    "agent_id": "rate", "join_code": "join-me",
                })[0], 429)
            original = self.store.issue_agent_token
            self.store.issue_agent_token = lambda *a, **k: (_ for _ in ()).throw(TypeError("boom"))
            try:
                self.assertEqual(_req("POST", self.base + "/v1/agents/register", {
                    "agent_id": "boom", "join_code": "join-me",
                })[0], 400)
            finally:
                self.store.issue_agent_token = original
        finally:
            os.environ.pop("SWARMLAB_JOIN_CODE", None)

    def test_messaging(self) -> None:
        import os
        self.server.token = "admin"
        os.environ["SWARMLAB_JOIN_CODE"] = "join-me"
        try:
            def reg(name):
                status, body, _ = _req("POST", self.base + "/v1/agents/register", {
                    "agent_id": name, "capabilities": ["chat"], "join_code": "join-me",
                })
                self.assertEqual(status, 201)
                return body["data"]["token"]
            t1 = reg("m1")
            t2 = reg("m2")
            status, body, _ = _req("POST", self.base + "/v1/messages", {
                "to_agent": "m2", "body": "hello",
            }, t1)
            self.assertEqual(status, 201)
            msg_id = body["data"]["id"]
            status, body, _ = _req("GET", self.base + "/v1/messages", None, t2)
            self.assertEqual(status, 200)
            self.assertEqual(body["data"][0]["body"], "hello")
            self.assertEqual(_req("POST", self.base + "/v1/messages", {"body": "x"}, t1)[0], 400)
            self.assertEqual(_req("POST", self.base + "/v1/messages", {"to_agent": "m2"}, t1)[0], 400)
            self.assertEqual(_req("POST", self.base + f"/v1/messages/{msg_id}/read", {}, t2)[0], 200)
            self.assertEqual(_req("POST", self.base + "/v1/messages", {"channel": "room", "body": "hi"}, t1)[0], 201)
            status, body, _ = _req("GET", self.base + "/v1/channels", None, t2)
            self.assertEqual(status, 200)
            self.assertTrue(body["data"])
            status, body, _ = _req("GET", self.base + "/v1/messages?channel=room", None, t2)
            self.assertEqual(body["data"][0]["channel"], "room")
            req = urllib.request.Request(self.base + "/v1/messages/stream?agent_id=m2&limit=1&timeout_s=1")
            req.add_header("Authorization", f"Bearer {t2}")
            with urllib.request.urlopen(req, timeout=3) as resp:
                self.assertIn(b"hello", resp.read())
        finally:
            os.environ.pop("SWARMLAB_JOIN_CODE", None)
            self.server.token = ""

    def test_artifacts_api(self) -> None:
        status, body, _ = _req("POST", self.base + "/v1/artifacts", {
            "name": "doc", "content": "hello", "owner": "a", "channel": "room",
        })
        self.assertEqual(status, 201)
        self.assertEqual(body["data"]["version"], 1)
        status, body, _ = _req("GET", self.base + "/v1/artifacts/doc")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["content"], "hello")
        self.assertEqual(_req("GET", self.base + "/v1/artifacts")[0], 200)
        self.assertEqual(_req("GET", self.base + "/v1/artifacts/nope")[0], 404)
        self.assertEqual(_req("DELETE", self.base + "/v1/artifacts/doc")[0], 200)

    def test_sandbox_run(self) -> None:
        from swarmlab.sandbox import run_wasm
        self.assertEqual(run_wasm('(module (func (export "run") (result i32) i32.const 7))')["result"], 7)
        with self.assertRaises(Exception):
            run_wasm("")
        with self.assertRaises(Exception):
            run_wasm("!!!")
        with self.assertRaises(Exception):
            run_wasm('(module (func (export "other") (result i32) i32.const 1))')
        with self.assertRaises(Exception):
            run_wasm('(module (import "x" "y" (func)) (func (export "run")))')

    def test_plugins_api(self) -> None:
        import os
        self.server.token = "admin"
        os.environ["SWARMLAB_JOIN_CODE"] = "join-me"
        try:
            status, body, _ = _req("POST", self.base + "/v1/agents/register", {
                "agent_id": "p1", "capabilities": ["dev"], "join_code": "join-me",
            })
            token = body["data"]["token"]
            status, body, _ = _req("POST", self.base + "/v1/plugins", {
                "name": "p", "version": "1", "code": "x", "description": "d",
            }, token)
            self.assertEqual(status, 201)
            self.assertEqual(_req("POST", self.base + "/v1/plugins", {"name": "bad", "version": "1", "code": "x", "runtime": "python"}, token)[0], 400)
            self.assertEqual(_req("POST", self.base + "/v1/plugins/p/1/approve", {}, token)[0], 403)
            self.assertEqual(_req("POST", self.base + "/v1/plugins/p/1/approve", {}, "admin")[0], 200)
            status, body, _ = _req("GET", self.base + "/v1/plugins", None, "admin")
            self.assertEqual(status, 200)
            self.assertTrue(body["data"])
            self.assertEqual(_req("GET", self.base + "/v1/plugins/p/1", None, "admin")[0], 200)
            self.assertEqual(_req("POST", self.base + "/v1/plugins/p/1/reject", {}, "admin")[0], 200)
            wat = '(module (func (export "run") (result i32) i32.const 42))'
            self.assertEqual(_req("POST", self.base + "/v1/plugins", {"name": "runner", "version": "1", "code": wat}, token)[0], 201)
            self.assertEqual(_req("POST", self.base + "/v1/plugins/runner/1/run", {}, token)[0], 403)
            self.assertEqual(_req("POST", self.base + "/v1/plugins/runner/1/approve", {}, "admin")[0], 200)
            status, body, _ = _req("POST", self.base + "/v1/plugins/runner/1/run", {}, token)
            self.assertEqual(status, 200)
            self.assertEqual(body["data"]["result"], 42)
            self.assertEqual(_req("POST", self.base + "/v1/plugins", {"name": "none", "version": "1", "code": "x", "runtime": "none"}, token)[0], 201)
            self.assertEqual(_req("POST", self.base + "/v1/plugins/none/1/approve", {}, "admin")[0], 200)
            self.assertEqual(_req("POST", self.base + "/v1/plugins/none/1/run", {}, token)[0], 400)
            self.assertEqual(_req("POST", self.base + "/v1/plugins/missing/9/run", {}, token)[0], 404)
            self.assertEqual(_req("GET", self.base + "/v1/plugins/bad", None, "admin")[0], 404)
            self.assertEqual(_req("GET", self.base + "/v1/plugins/p/99", None, "admin")[0], 404)
            self.assertEqual(_req("POST", self.base + "/v1/plugins/p/1", {}, "admin")[0], 404)
        finally:
            os.environ.pop("SWARMLAB_JOIN_CODE", None)
            self.server.token = ""

    def test_reputation_api(self) -> None:
        import os
        self.server.token = "admin"
        os.environ["SWARMLAB_JOIN_CODE"] = "join-me"
        try:
            def reg(name):
                status, body, _ = _req("POST", self.base + "/v1/agents/register", {
                    "agent_id": name, "capabilities": ["rep"], "join_code": "join-me",
                })
                return body["data"]["token"]
            t1 = reg("rep1")
            t2 = reg("rep2")
            status, body, _ = _req("POST", self.base + "/v1/reputation/feedback", {
                "to_agent": "rep2", "score": 1, "comment": "ok",
            }, t1)
            self.assertEqual(status, 201)
            status, body, _ = _req("GET", self.base + "/v1/reputation/rep2", None, t2)
            self.assertEqual(body["data"]["feedback_count"], 1)
            self.assertEqual(_req("GET", self.base + "/v1/reputation", None, t2)[0], 200)
            self.assertEqual(_req("POST", self.base + "/v1/reputation/feedback", {"to_agent": "rep2", "score": 9}, t1)[0], 400)
        finally:
            os.environ.pop("SWARMLAB_JOIN_CODE", None)
            self.server.token = ""

    def test_roles_api(self) -> None:
        import os
        self.server.token = "admin"
        os.environ["SWARMLAB_JOIN_CODE"] = "join-me"
        try:
            def reg(name):
                status, body, _ = _req("POST", self.base + "/v1/agents/register", {
                    "agent_id": name, "capabilities": ["coord"], "join_code": "join-me",
                })
                return body["data"]["token"]
            t1 = reg("r1")
            t2 = reg("r2")
            self.assertEqual(_req("POST", self.base + "/v1/roles/claim", {"scope": "s", "name": "leader"}, t1)[0], 200)
            self.assertEqual(_req("POST", self.base + "/v1/roles/claim", {"scope": "s", "name": "leader"}, t2)[0], 409)
            self.assertEqual(_req("POST", self.base + "/v1/roles/renew", {"scope": "s", "name": "leader"}, t1)[0], 200)
            status, body, _ = _req("GET", self.base + "/v1/roles?scope=s", None, t2)
            self.assertEqual(status, 200)
            self.assertEqual(body["data"][0]["agent_id"], "r1")
            self.assertEqual(_req("POST", self.base + "/v1/roles/release", {"scope": "s", "name": "leader"}, t1)[0], 200)
        finally:
            os.environ.pop("SWARMLAB_JOIN_CODE", None)
            self.server.token = ""

    def test_channel_actions(self) -> None:
        import os
        self.server.token = "admin"
        os.environ["SWARMLAB_JOIN_CODE"] = "join-me"
        try:
            status, body, _ = _req("POST", self.base + "/v1/agents/register", {
                "agent_id": "ch1", "capabilities": ["chat"], "join_code": "join-me",
            })
            token = body["data"]["token"]
            self.assertEqual(_req("POST", self.base + "/v1/channels/room/join", {}, token)[0], 200)
            status, body, _ = _req("GET", self.base + "/v1/channels/room/members", None, token)
            self.assertEqual(status, 200)
            self.assertEqual(body["data"][0]["agent_id"], "ch1")
            self.assertEqual(_req("POST", self.base + "/v1/channels/room/roles", {"agent_id": "ch1", "role": "admin"}, "admin")[0], 200)
            self.assertEqual(_req("POST", self.base + "/v1/channels/room/roles", {"agent_id": "ch1", "role": "admin"}, token)[0], 403)
            self.assertEqual(_req("POST", self.base + "/v1/channels/room/leave", {}, token)[0], 200)
        finally:
            os.environ.pop("SWARMLAB_JOIN_CODE", None)
            self.server.token = ""

    def test_discovery(self) -> None:
        for path in ("/llms.txt", "/robots.txt", "/sitemap.xml"):
            status, body, _ = _req("GET", self.base + path)
            self.assertEqual(status, 200)
            self.assertTrue(body.get("raw"))
        status, body, _ = _req("GET", self.base + "/agents.json")
        self.assertEqual(status, 200)
        self.assertEqual(body["name"], "swarm-lab")
        status, body, _ = _req("GET", self.base + "/.well-known/ai-plugin.json")
        self.assertEqual(status, 200)
        self.assertEqual(body["api"]["type"], "openapi")

    def test_dashboard(self) -> None:
        status, body, _ = _req("GET", self.base + "/dashboard")
        self.assertEqual(status, 200)
        self.assertIn("production", body.get("raw", "").lower())

    def test_audit_api(self) -> None:
        _req("POST", self.base + "/v1/tasks", {"capability": "au"})
        status, body, _ = _req("GET", self.base + "/v1/audit")
        self.assertEqual(status, 200)
        self.assertTrue(any(row["action"] == "api.mutation" for row in body["data"]))

    def test_task_events_api(self) -> None:
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "ev"})
        task_id = body["data"]["task_id"]
        status, payload, _ = _req("GET", self.base + f"/v1/tasks/{task_id}/events")
        self.assertEqual(status, 200)
        self.assertIsInstance(payload["data"], list)

    def test_prune_api(self) -> None:
        status, body, _ = _req("POST", self.base + "/v1/maintenance/prune", {"older_than_s": 60})
        self.assertEqual(status, 200)
        self.assertIn("tasks", body["data"])

    def test_vacuum_api(self) -> None:
        status, body, _ = _req("POST", self.base + "/v1/maintenance/vacuum", {})
        self.assertEqual(status, 200)
        self.assertTrue(body["data"]["ok"])

    def test_expire_api(self) -> None:
        import time
        _req("POST", self.base + "/v1/tasks", {"capability": "exp", "ttl_s": 0.01})
        time.sleep(0.03)
        status, body, _ = _req("POST", self.base + "/v1/maintenance/expire", {})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["data"]["expired"], 0)

    def test_ttl_api(self) -> None:
        import time
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "ttl", "ttl_s": 0.01})
        task_id = body["data"]["task_id"]
        time.sleep(0.03)
        _req("POST", self.base + "/v1/agents", {"agent_id": "ttl", "capabilities": ["ttl"]})
        _, claim, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "ttl", "capability": "ttl"})
        self.assertIsNone(claim["data"])
        _, task, _ = _req("GET", self.base + f"/v1/tasks/{task_id}")
        self.assertEqual(task["data"]["status"], "expired")

    def test_requeue_api(self) -> None:
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "rq"})
        task_id = body["data"]["task_id"]
        _req("POST", self.base + f"/v1/tasks/{task_id}/cancel", {})
        status, body, _ = _req("POST", self.base + f"/v1/tasks/{task_id}/requeue", {})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "pending")
        self.assertEqual(_req("POST", self.base + f"/v1/tasks/{task_id}/requeue", {})[0], 409)

    def test_cancel_api(self) -> None:
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "c"})
        task_id = body["data"]["task_id"]
        status, body, _ = _req("POST", self.base + f"/v1/tasks/{task_id}/cancel", {})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "cancelled")
        self.assertEqual(_req("POST", self.base + "/v1/tasks/nope/cancel", {})[0], 404)

    def test_get_task(self) -> None:
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "g"})
        task_id = body["data"]["task_id"]
        status, payload, _ = _req("GET", self.base + f"/v1/tasks/{task_id}")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["task_id"], task_id)
        self.assertEqual(_req("GET", self.base + "/v1/tasks/nope")[0], 404)

    def test_rate_env_and_batch_complete(self) -> None:
        import os
        os.environ["SWARMLAB_RATE_RPS"] = "bad"
        try:
            self.assertEqual(_req("GET", self.base + "/health")[0], 200)
        finally:
            os.environ.pop("SWARMLAB_RATE_RPS", None)
        _req("POST", self.base + "/v1/agents", {"agent_id": "z", "capabilities": ["x"]})
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "x"})
        task_id = body["data"]["task_id"]
        _, body, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "z", "capability": "x"})
        fence = body["data"]["lease_epoch"]
        status, body, _ = _req("POST", self.base + "/v1/batch", {"ops": [
            {"op": "renew", "task_id": task_id, "agent_id": "z", "fence": fence},
            {"op": "complete", "task_id": task_id, "agent_id": "z", "fence": fence},
        ]})
        self.assertEqual(status, 200)
        self.assertTrue(all(r.get("ok") for r in body["data"]))

    def test_auth_and_heartbeat(self) -> None:
        import os
        # legacy token mode с отдельным сервером
        os.environ["SWARMLAB_TOKEN"] = "legacy"
        try:
            other = build_server(SwarmStore(":memory:"), "127.0.0.1", 0, "legacy")
            base = f"http://127.0.0.1:{other.server_address[1]}"
            thread = threading.Thread(target=other.serve_forever, daemon=True)
            thread.start()
            try:
                self.assertEqual(_req("GET", base + "/v1/stats")[0], 401)
                self.assertEqual(_req("GET", base + "/v1/stats", None, "legacy")[0], 200)
            finally:
                other.shutdown(); other.server_close(); thread.join(timeout=5)
        finally:
            os.environ.pop("SWARMLAB_TOKEN", None)
        _req("POST", self.base + "/v1/agents", {"agent_id": "h", "capabilities": ["x"]})
        self.assertEqual(_req("POST", self.base + "/v1/heartbeat", {"agent_id": "h"})[0], 200)

    def test_batch_ops(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "b", "capabilities": ["x"]})
        _req("POST", self.base + "/v1/tasks", {"capability": "x"})
        status, body, _ = _req("POST", self.base + "/v1/batch", {"ops": [
            {"op": "submit", "capability": "x"},
            {"op": "claim", "agent_id": "b", "capability": "x"},
            {"op": "events"},
            {"op": "stats"},
            {"op": "bad"},
            1,
        ]})
        self.assertEqual(status, 200)
        self.assertEqual(len(body["data"]), 6)
        self.assertEqual(_req("GET", self.base + "/v1/tasks?limit=bad")[0], 400)

    def test_post_errors(self) -> None:
        self.assertEqual(_req("POST", self.base + "/v1/agents", {"agent_id": "x", "capabilities": "bad"})[0], 400)
        self.assertEqual(_req("POST", self.base + "/v1/heartbeat", {})[0], 400)
        self.assertEqual(_req("POST", self.base + "/v1/batch", {"ops": "bad"})[0], 400)
        self.assertEqual(_req("POST", self.base + "/nope", {})[0], 404)
        req = urllib.request.Request(self.base + "/v1/tasks", data=b"[]", method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
        req = urllib.request.Request(self.base + "/v1/tasks", data=b"x" * (1 << 20 + 10), method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
        except (urllib.error.URLError, ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            pass

    def test_renew_and_stream(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "r", "capabilities": ["x"]})
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "x"})
        task_id = body["data"]["task_id"]
        _, body, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "r", "capability": "x"})
        fence = body["data"]["lease_epoch"]
        status, renewed, _ = _req("POST", self.base + f"/v1/tasks/{task_id}/renew", {"agent_id": "r", "fence": fence})
        self.assertEqual(status, 200)
        self.assertIn("lease_until", renewed["data"])
        status, _, _ = _req("GET", self.base + "/v1/tasks?status=claimed")
        self.assertEqual(status, 200)
        status, _, _ = _req("POST", self.base + "/v1/batch", {"ops": [{"op": "nope"}]})
        self.assertEqual(status, 200)
        req = urllib.request.Request(self.base + "/v1/stream?after=0&limit=1&timeout_s=0.2", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)

    def test_get_routes_and_errors(self) -> None:
        status, _, headers = _req("GET", self.base + "/v1/stats")
        self.assertEqual(status, 200)
        self.assertTrue(headers.get("X-Request-Id"))
        for path in ("/v1/agents", "/v1/tasks", "/v1/events", "/metrics"):
            self.assertEqual(_req("GET", self.base + path)[0], 200)
        self.assertEqual(_req("GET", self.base + "/nope")[0], 404)
        req = urllib.request.Request(self.base + "/v1/tasks", data=b"{bad", method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
        self.assertEqual(_req("POST", self.base + "/v1/agents", {"agent_id": ""})[0], 400)


class ExtraMcpTests(unittest.TestCase):
    def test_batch_tools_and_prompts(self) -> None:
        store = SwarmStore(":memory:")
        mcp = McpDispatcher(store)
        try:
            mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "swarm_register", "arguments": {"agent_id": "m", "capabilities": ["x"]}}})
            batch = mcp.handle({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "swarm_batch", "arguments": {"ops": [
                    {"op": "submit", "capability": "x"},
                    {"op": "claim", "agent_id": "m", "capability": "x"},
                    {"op": "events", "after": 0},
                    {"op": "stats"},
                ]}},
            })
            self.assertIn("content", batch["result"])
            prompt = mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "prompts/get", "params": {"name": "swarm_planner", "arguments": {"goal": "g"}}})
            self.assertIn("messages", prompt["result"])
            bad = mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "prompts/get", "params": {"name": "nope"}})
            self.assertIn("error", bad)
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
