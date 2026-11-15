# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.error
import urllib.request

from swarmlab.api import build_server
from swarmlab.store import SwarmStore


def _req(method, url, token=None, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


class AuthTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["SWARMLAB_TOKENS"] = json.dumps({"reader": ["read"], "writer": ["read", "write"]})
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
        os.environ.pop("SWARMLAB_TOKENS", None)

    def test_scopes(self) -> None:
        status, _ = _req("GET", self.base + "/health", "reader")
        self.assertEqual(status, 200)
        status, _ = _req("POST", self.base + "/v1/tasks", "reader", {"capability": "x"})
        self.assertEqual(status, 403)
        status, _ = _req("POST", self.base + "/v1/tasks", "writer", {"capability": "x"})
        self.assertEqual(status, 200)
        status, _ = _req("GET", self.base + "/health", "unknown")
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
