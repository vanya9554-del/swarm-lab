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

    def test_open_store_pg_branch(self) -> None:
        from unittest.mock import patch
        import swarmlab
        with patch("swarmlab.pg.PgSwarmStore") as fake:
            fake.return_value = object()
            result = swarmlab.open_store("postgresql://x")
            self.assertIsNotNone(result)
            fake.assert_called_once_with("postgresql://x")

    def test_events_failures(self) -> None:
        from unittest.mock import patch
        from swarmlab.events import PgEventStream
        with patch("swarmlab.events.available", return_value=False):
            with self.assertRaises(RuntimeError):
                PgEventStream("x")
        class BadConn:
            def notifies(self, timeout=None):
                raise RuntimeError("bad")
            def close(self):
                raise RuntimeError("bad")
        stream = PgEventStream.__new__(PgEventStream)
        stream.conn = BadConn()
        self.assertIsNone(stream.wait(0.1))
        stream.close()

    def test_error_branches(self) -> None:
        self.mcp.handle("bad")
        self.mcp.handle({"jsonrpc": "2.0", "id": 1})
        self.mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": "bad"})
        self.mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "swarm_register", "arguments": "bad"}})
        self.mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "swarm_register", "arguments": {"agent_id": "x", "capabilities": "bad"}}})
        self.mcp.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "swarm_batch", "arguments": {"ops": "bad"}}})
        self.mcp.handle({"jsonrpc": "2.0", "id": 6, "method": "prompts/get", "params": "bad"})
        self.mcp.handle({"jsonrpc": "2.0", "id": 7, "method": "resources/read", "params": "bad"})
        self.mcp.handle({"jsonrpc": "2.0", "id": 8, "method": "tools/call", "params": {"name": "swarm_batch", "arguments": {"ops": [1]}}})

    def test_stdio_and_more_tools(self) -> None:
        import io

        from swarmlab.mcp import main_stdio
        src = io.StringIO('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n')
        out = io.StringIO()
        main_stdio(self.store, stdin=src, stdout=out)
        self.assertIn('"result"', out.getvalue())
        self.mcp.handle({"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "swarm://events"}})
        self.mcp.handle({"jsonrpc": "2.0", "id": 3, "method": "prompts/get", "params": {"name": "swarm_planner", "arguments": {"goal": "x"}}})
        self.mcp.handle({"jsonrpc": "2.0", "id": 4, "method": "prompts/get", "params": {"name": "bad"}})
        self.mcp.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/list"})
        self.mcp.handle({"jsonrpc": "2.0", "id": 6, "method": "resources/list"})
        self.mcp.handle({"jsonrpc": "2.0", "id": 7, "method": "notifications/initialized"})
        self.mcp.handle({"jsonrpc": "2.0", "id": 8, "method": "ping"})
        self.mcp.handle({"jsonrpc": "2.0", "id": 9, "method": "tools/call", "params": {"name": "swarm_discover", "arguments": {}}})
        self.mcp.handle({"jsonrpc": "2.0", "id": 10, "method": "tools/call", "params": {"name": "swarm_events", "arguments": {}}})
        self.mcp.handle({"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "swarm_batch", "arguments": {"ops": [{"op": "register", "agent_id": "z", "capabilities": ["x"]}, {"op": "submit", "capability": "x"}, {"op": "claim", "agent_id": "z", "capability": "x"}, {"op": "renew", "task_id": "bad", "agent_id": "z"}, {"op": "complete", "task_id": "bad", "agent_id": "z"}]}}})
        self.mcp.handle({"jsonrpc": "2.0", "id": 12, "method": "resources/read", "params": {"uri": "swarm://events"}})

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
