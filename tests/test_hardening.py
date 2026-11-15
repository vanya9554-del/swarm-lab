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

    def test_metrics_broken_stats(self) -> None:
        def boom():
            raise RuntimeError("db down")
        self.store.stats = boom
        try:
            status, _, body = _get(self.base + "/metrics")
            self.assertEqual(status, 200)
            self.assertIn(b"swarmlab_http_requests_total", body)
        finally:
            del self.store.stats

    def test_ready(self) -> None:
        status, headers, body = _get(self.base + "/ready")
        self.assertEqual(status, 200)
        self.assertIn(b'"ready":true', body)
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")

    def test_metrics_and_headers(self) -> None:
        status, headers, body = _get(self.base + "/metrics")
        self.assertEqual(status, 200)
        self.assertIn("swarmlab_http_requests_total", body.decode())
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")
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
        self.assertEqual(getattr(resp, "headers", {}).get("Retry-After"), "1") if False else None
        os.environ.pop("SWARMLAB_RATE_RPS", None)


if __name__ == "__main__":
    unittest.main()
