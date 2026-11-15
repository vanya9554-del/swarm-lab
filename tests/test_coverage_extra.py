from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from swarmlab.api import build_server
from swarmlab.mcp import McpDispatcher
from swarmlab.store import SwarmError, SwarmStore


def _req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
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
