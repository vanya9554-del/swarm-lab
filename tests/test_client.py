from __future__ import annotations

import threading
import unittest

from swarmlab.api import build_server
from swarmlab.client import SwarmClient, SwarmClientError
from swarmlab.store import SwarmStore


class ClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SwarmStore(":memory:")
        self.server = build_server(self.store, "127.0.0.1", 0)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.client = SwarmClient(self.base)

    def tearDown(self) -> None:
        self.client.close()
        self.server.shutdown()

    def test_agent_flow(self) -> None:
        with self.client as client:
            self.assertEqual(client.register("a1", ["x"])["agent_id"], "a1")
            self.assertTrue(client.discover("x"))
            self.assertEqual(client.get_agent("a1")["agent_id"], "a1")
            self.assertEqual(client.heartbeat("a1")["agent_id"], "a1")
            task = client.submit("x", {"v": 1}, priority=5)
            claimed = client.claim("a1", "x", lease_s=10)
            self.assertEqual(claimed["task_id"], task["task_id"])
            renewed = client.renew(claimed["task_id"], "a1", 10, claimed["lease_epoch"])
            self.assertIn("lease_until", renewed)
            done = client.complete(claimed["task_id"], "a1", {"r": 1}, claimed["lease_epoch"])
            self.assertEqual(done["status"], "completed")
            self.assertEqual(client.get_task(task["task_id"])["result"], {"r": 1})
            self.assertTrue(client.task_events(task["task_id"]))
            self.assertTrue(client.events())
            self.assertIn("tasks", client.stats())

    def test_mutations_and_errors(self) -> None:
        self.client.register("a1", ["x"])
        task = self.client.submit("x", {})
        with self.assertRaises(SwarmClientError) as bad:
            self.client.complete(task["task_id"], "a1", {}, 999)
        self.assertEqual(bad.exception.status, 409)
        self.assertEqual(self.client.cancel(task["task_id"])["status"], "cancelled")
        task2 = self.client.submit("x", {})
        self.client.claim("a1", "x")
        self.client.cancel(task2["task_id"])
        self.assertEqual(self.client.requeue(task2["task_id"])["status"], "pending")
        with self.assertRaises(SwarmClientError) as missing:
            self.client.get_task("nope")
        self.assertEqual(missing.exception.status, 404)

    def test_token_and_false_payload(self) -> None:
        from unittest.mock import MagicMock, patch
        authed = SwarmClient(self.base, token="token")
        self.assertIn("tasks", authed.stats())
        gen = authed.stream(timeout_s=0.1, limit=1)
        next(gen, None)
        gen.close()
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.read.return_value = b'{"ok": false, "error": {"code": "X"}}'
        with patch("swarmlab.client.urllib.request.urlopen", return_value=resp):
            with self.assertRaises(SwarmClientError):
                authed._request("GET", "/v1/stats")

    def test_stream(self) -> None:
        self.client.register("a1", ["x"])
        self.client.submit("x", {})
        events = self.client.stream(timeout_s=0.1, limit=1)
        first = next(events)
        self.assertIn("seq", first)
        events.close()
