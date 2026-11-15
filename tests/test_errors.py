from __future__ import annotations

import unittest

from swarmlab.mcp import McpDispatcher
from swarmlab.store import SwarmStore


class ErrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SwarmStore(":memory:")
        self.mcp = McpDispatcher(self.store)

    def tearDown(self) -> None:
        self.store.close()

    def test_mcp_errors_and_batch(self) -> None:
        unknown = self.mcp.handle({"jsonrpc": "2.0", "id": 1, "method": "nope"})
        self.assertIn("error", unknown)
        bad_tool = self.mcp.handle({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        })
        self.assertTrue(bad_tool["result"]["isError"])
        batch = self.mcp.handle({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "swarm_batch", "arguments": {"ops": [{"op": "stats"}, {"op": "nope"}]}},
        })
        self.assertIn("content", batch["result"])
        bad_resource = self.mcp.handle({
            "jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "nope"},
        })
        self.assertIn("error", bad_resource)


if __name__ == "__main__":
    unittest.main()
