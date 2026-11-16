from __future__ import annotations

import os
import threading
import unittest
import urllib.error
import urllib.request

from swarmlab.api import build_server
from swarmlab.store import SwarmStore


def _post(url: str, body: bytes):
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def _get(url: str):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


class HardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SwarmStore(":memory:")
        self.server = build_server(self.store, "127.0.0.1", 0)
        self.port = int(self.server.server_address[1])
        self.base = f"http://127.0.0.1:{self.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.store.close()
        os.environ.pop("SWARMLAB_RATE_RPS", None)

    def test_tcp_nodelay_error(self) -> None:
        import socket
        from unittest.mock import patch

        from swarmlab.api import build_server
        from swarmlab.store import SwarmStore
        original = socket.socket.setsockopt

        def flaky(sock, level, opt, value):
            if level == socket.IPPROTO_TCP and opt == socket.TCP_NODELAY:
                raise OSError("no tcp nodelay")
            return original(sock, level, opt, value)

        with patch.object(socket.socket, "setsockopt", flaky):
            other = build_server(SwarmStore(":memory:"), "127.0.0.1", 0)
        other.server_close()

    def test_gzip(self) -> None:
        import gzip
        # создаём достаточно большой ответ
        for i in range(20):
            _req = urllib.request.Request(self.base + "/v1/tasks", data=b'{"capability":"gz"}', method="POST")
            _req.add_header("Content-Type", "application/json")
            urllib.request.urlopen(_req, timeout=3).read()
        req = urllib.request.Request(self.base + "/v1/tasks")
        req.add_header("Accept-Encoding", "gzip")
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.headers.get("Content-Encoding"), "gzip")
            data = gzip.decompress(resp.read())
            self.assertIn(b"ok", data)

    def test_metrics_broken_stats(self) -> None:
        def boom():
            raise RuntimeError("db down")
        self.store.stats = boom
        try:
            status, _, body = _get(self.base + "/metrics")
            self.assertEqual(status, 200)
            self.assertIn(b"swarmlab_http_requests_total", body)
            self.assertIn(b"swarmlab_http_request_duration_seconds_bucket", body)
        finally:
            del self.store.stats

    def test_head(self) -> None:
        import http.client
        from urllib.parse import urlparse
        parsed = urlparse(self.base)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
        conn.request("HEAD", "/v1/stream?after=0&limit=1&timeout_s=0.2")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.read(), b"")
        conn.request("HEAD", "/health")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.read(), b"")
        conn.close()

    def test_health_info(self) -> None:
        status, _, body = _get(self.base + "/health")
        self.assertEqual(status, 200)
        self.assertIn(b'"version"', body)
        self.assertIn(b'"uptime_s"', body)

    def test_metrics_statuses(self) -> None:
        t = self.store.submit("x", {})
        self.store.cancel(t["task_id"])
        status, _, body = _get(self.base + "/metrics")
        self.assertEqual(status, 200)
        self.assertIn(b'swarmlab_tasks{status="cancelled"}', body)

    def test_ready(self) -> None:
        status, headers, body = _get(self.base + "/ready")
        self.assertEqual(status, 200)
        self.assertIn(b'"ready":true', body)
        self.assertIn(b'"quick_check":"ok"', body)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertIn("default-src", headers.get("Content-Security-Policy", ""))

    def test_metrics_and_headers(self) -> None:
        status, headers, body = _get(self.base + "/metrics")
        self.assertEqual(status, 200)
        self.assertIn("swarmlab_http_requests_total", body.decode())
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertIn("default-src", headers.get("Content-Security-Policy", ""))
        self.assertIn("swarmlab_http_requests_total_all", body.decode())

    def test_rate_limit_post(self) -> None:
        os.environ["SWARMLAB_RATE_RPS"] = "1"
        try:
            req = urllib.request.Request(self.base + "/v1/tasks", data=b"{}", method="POST")
            req.add_header("Content-Type", "application/json")
            statuses = []
            retry_after = None
            for _ in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        statuses.append(resp.status)
                except urllib.error.HTTPError as exc:
                    statuses.append(exc.code)
                    retry_after = exc.headers.get("Retry-After")
            self.assertIn(429, statuses)
            self.assertEqual(retry_after, "1")
        finally:
            os.environ.pop("SWARMLAB_RATE_RPS", None)

    def test_backpressure(self) -> None:
        os.environ["SWARMLAB_MAX_PENDING"] = "1"
        try:
            body = b'{"capability":"bp"}'
            status1, _, _ = _post(self.base + "/v1/tasks", body)
            status2, _, _ = _post(self.base + "/v1/tasks", body)
            self.assertIn(status1, (200, 400))
            self.assertEqual(status2, 429)
        finally:
            os.environ.pop("SWARMLAB_MAX_PENDING", None)

    def test_rate_limit(self) -> None:
        os.environ["SWARMLAB_RATE_RPS"] = "2"
        statuses = [_get(self.base + "/health")[0] for _ in range(5)]
        self.assertIn(429, statuses)
        os.environ.pop("SWARMLAB_RATE_RPS", None)


if __name__ == "__main__":
    unittest.main()
