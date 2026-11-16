from __future__ import annotations

import threading
import unittest
import urllib.request

from swarmlab.api import build_server
from swarmlab.mcp import McpDispatcher
from swarmlab.store import SwarmStore


class McpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SwarmStore(":memory:")
        self.mcp = McpDispatcher(self.store)

    def tearDown(self) -> None:
        self.store.close()

    def _rpc(self, method: str, params=None):
        return self.mcp.handle({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})

    def _call(self, name: str, args: dict):
        response = self._rpc("tools/call", {"name": name, "arguments": args})
        return response["result"]

    def test_tools_flow(self) -> None:
        init = self._rpc("initialize")
        self.assertEqual(init["result"]["serverInfo"]["name"], "swarm-lab")
        names = {t["name"] for t in self._rpc("tools/list")["result"]["tools"]}
        for expected in ("swarm_register", "swarm_submit", "swarm_claim", "swarm_complete"):
            self.assertIn(expected, names)
        registered = self._call("swarm_register", {"agent_id": "a1", "capabilities": ["search"]})
        self.assertFalse(registered["isError"])
        submitted = self._call("swarm_submit", {"capability": "search", "payload": {"q": "x"}})
        task_id = self._text(submitted)["task_id"]
        claim = self._text(self._call("swarm_claim", {"agent_id": "a1", "capability": "search"}))
        done = self._text(self._call("swarm_complete", {
            "task_id": task_id, "agent_id": "a1", "fence": claim["lease_epoch"], "result": {"ok": 1},
        }))
        self.assertEqual(done["status"], "completed")

    @staticmethod
    def _text(response: dict):
        import json
        return json.loads(response["content"][0]["text"])

    def test_max_attempts_tool(self) -> None:
        self._call("swarm_register", {"agent_id": "ma", "capabilities": ["ma"]})
        submitted = self._text(self._call("swarm_submit", {"capability": "ma", "max_attempts": 1}))
        claim = self._text(self._call("swarm_claim", {"agent_id": "ma", "capability": "ma"}))
        self.assertEqual(claim["attempts"], 1)
        got = self._text(self._call("swarm_get_task", {"task_id": submitted["task_id"]}))
        self.assertEqual(got["max_attempts"], 1)

    def test_dependency_tool(self) -> None:
        self._call("swarm_register", {"agent_id": "dep", "capabilities": ["dep"]})
        first = self._text(self._call("swarm_submit", {"capability": "dep"}))
        second = self._text(self._call("swarm_submit", {"capability": "dep", "depends_on": first["task_id"]}))
        claim = self._text(self._call("swarm_claim", {"agent_id": "dep", "capability": "dep"}))
        self.assertEqual(claim["task_id"], first["task_id"])
        self._call("swarm_complete", {"task_id": first["task_id"], "agent_id": "dep", "fence": claim["lease_epoch"]})
        next_claim = self._text(self._call("swarm_claim", {"agent_id": "dep", "capability": "dep"}))
        self.assertEqual(next_claim["task_id"], second["task_id"])

    def test_expire_tool(self) -> None:
        out = self._text(self._call("swarm_expire", {}))
        self.assertIn("expired", out)

    def test_deregister_tool(self) -> None:
        self._call("swarm_register", {"agent_id": "d", "capabilities": ["x"]})
        self.assertTrue(self._text(self._call("swarm_deregister", {"agent_id": "d"}))["deleted"])

    def test_requeue_tool(self) -> None:
        submitted = self._text(self._call("swarm_submit", {"capability": "rq"}))
        self._call("swarm_cancel", {"task_id": submitted["task_id"]})
        self.assertEqual(self._text(self._call("swarm_requeue", {"task_id": submitted["task_id"]}))["status"], "pending")

    def test_cancel_tool(self) -> None:
        submitted = self._text(self._call("swarm_submit", {"capability": "c"}))
        cancelled = self._text(self._call("swarm_cancel", {"task_id": submitted["task_id"]}))
        self.assertEqual(cancelled["status"], "cancelled")

    def test_get_agent_tool(self) -> None:
        self._call("swarm_register", {"agent_id": "ag", "capabilities": ["x"]})
        self.assertEqual(self._text(self._call("swarm_get_agent", {"agent_id": "ag"}))["agent_id"], "ag")
        self.assertTrue(self._call("swarm_get_agent", {"agent_id": "nope"})["isError"])

    def test_get_task_tool(self) -> None:
        submitted = self._text(self._call("swarm_submit", {"capability": "g"}))
        got = self._text(self._call("swarm_get_task", {"task_id": submitted["task_id"]}))
        self.assertEqual(got["task_id"], submitted["task_id"])
        missing = self._call("swarm_get_task", {"task_id": "nope"})
        self.assertTrue(missing["isError"])

    def test_renew_complete(self) -> None:
        self._call("swarm_register", {"agent_id": "m", "capabilities": ["x"]})
        submitted = self._text(self._call("swarm_submit", {"capability": "x"}))
        claim = self._text(self._call("swarm_claim", {"agent_id": "m", "capability": "x"}))
        renewed = self._text(self._call("swarm_renew", {"task_id": submitted["task_id"], "agent_id": "m", "fence": claim["lease_epoch"]}))
        self.assertIn("lease_until", renewed)
        done = self._text(self._call("swarm_complete", {"task_id": submitted["task_id"], "agent_id": "m", "fence": claim["lease_epoch"]}))
        self.assertEqual(done["status"], "completed")

    def test_resources_prompts_and_http(self) -> None:
        resources = self._rpc("resources/list")["result"]["resources"]
        self.assertIn("swarm://stats", {r["uri"] for r in resources})
        read = self._rpc("resources/read", {"uri": "swarm://stats"})
        self.assertIn("contents", read["result"])
        prompts = self._rpc("prompts/list")["result"]["prompts"]
        self.assertIn("swarm_worker", {p["name"] for p in prompts})
        prompt = self._rpc("prompts/get", {"name": "swarm_worker", "arguments": {"capability": "search"}})
        self.assertIn("messages", prompt["result"])

        server = build_server(self.store, "127.0.0.1", 0)
        port = int(server.server_address[1])
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/mcp",
                data=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=3) as resp:
                self.assertEqual(resp.status, 200)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()



class McpStdioErrorTests(unittest.TestCase):
    def test_stdio_lines(self) -> None:
        import io
        from unittest.mock import patch

        from swarmlab.mcp import McpDispatcher, main_stdio
        from swarmlab.store import SwarmError, SwarmStore
        store = SwarmStore(":memory:")
        dispatcher = McpDispatcher(store)
        try:
            with patch.object(dispatcher, "_dispatch", side_effect=SwarmError("BAD_REQUEST", "sw")):
                response = dispatcher.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
            self.assertIn("error", response)
            with patch.object(dispatcher, "_dispatch", side_effect=RuntimeError("boom")):
                response = dispatcher.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
            self.assertIn("error", response)
            self.assertIsNone(dispatcher.handle({"jsonrpc": "2.0", "method": "tools/list"}))
            out = io.StringIO()
            main_stdio(store, stdin=io.StringIO("\nnot-json\n{\"id\":1,\"method\":\"ping\"}\n"), stdout=out)
            text = out.getvalue()
            self.assertIn("parse error", text)
            self.assertIn("result", text)
        finally:
            store.close()



class McpCallErrorTests(unittest.TestCase):
    def test_call_errors(self) -> None:
        from unittest.mock import patch

        from swarmlab.mcp import McpDispatcher, McpError
        from swarmlab.store import SwarmStore
        store = SwarmStore(":memory:")
        try:
            dispatcher = McpDispatcher(store)
            with patch.object(dispatcher, "_call", side_effect=McpError(-32602, "bad")):
                response = dispatcher.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "x"}})
            self.assertIn("error", response)
            with patch.object(dispatcher, "_call", side_effect=ValueError("bad")):
                response = dispatcher.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "x"}})
            self.assertIn("error", response)
        finally:
            store.close()
