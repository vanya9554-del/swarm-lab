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
