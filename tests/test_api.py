# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from swarmlab.api import build_server
from swarmlab.store import SwarmStore


def _call(method: str, url: str, body: dict | None = None, timeout: float = 5.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), json.loads(resp.read() or b"{}"), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        return int(exc.code), json.loads(exc.read() or b"{}"), dict(exc.headers)


class ApiTests(unittest.TestCase):
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

    def test_task_flow(self) -> None:
        status, body, _ = _call("POST", self.base + "/v1/agents", {"agent_id": "a1", "capabilities": ["search"]})
        self.assertEqual(status, 200, body)
        status, body, _ = _call("POST", self.base + "/v1/tasks", {"capability": "search", "payload": {"q": "x"}})
        self.assertEqual(status, 200, body)
        task_id = body["data"]["task_id"]
        status, body, _ = _call("POST", self.base + "/v1/tasks/claim", {"agent_id": "a1", "capability": "search"})
        self.assertEqual(status, 200, body)
        claim = body["data"]
        status, body, _ = _call(
            "POST", self.base + f"/v1/tasks/{task_id}/complete",
            {"agent_id": "a1", "fence": claim["lease_epoch"], "result": {"ok": 1}},
        )
        self.assertEqual(status, 200, body)
        self.assertEqual(body["data"]["status"], "completed")

    def test_batch_and_sse(self) -> None:
        _call("POST", self.base + "/v1/agents", {"agent_id": "a1", "capabilities": ["search"]})
        _call("POST", self.base + "/v1/tasks", {"capability": "search"})
        status, body, _ = _call(
            "POST", self.base + "/v1/batch",
            {"ops": [{"op": "claim", "agent_id": "a1", "capability": "search"}, {"op": "stats"}]},
        )
        self.assertEqual(status, 200, body)
        self.assertTrue(body["data"][0]["ok"])
        self.assertIn("events", body["data"][1]["data"])
        req = urllib.request.Request(self.base + "/v1/stream?after=0&limit=1&timeout_s=1", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            line = resp.readline().decode().strip()
        self.assertTrue(line.startswith("id:") or line.startswith("data:"))


if __name__ == "__main__":
    unittest.main()
