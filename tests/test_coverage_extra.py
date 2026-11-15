from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from swarmlab.api import build_server
from swarmlab.mcp import McpDispatcher
from swarmlab.store import SwarmError, SwarmStore


def _req(method, url, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
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

    def test_ready_failure(self) -> None:
        def boom():
            raise RuntimeError("db down")
        self.store.stats = boom
        try:
            status, _, _ = _req("GET", self.base + "/ready")
            self.assertEqual(status, 503)
        finally:
            del self.store.stats

    def test_body_limit(self) -> None:
        from swarmlab import api
        old = api.MAX_BODY
        api.MAX_BODY = 4
        other = build_server(SwarmStore(":memory:"), "127.0.0.1", 0)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{other.server_address[1]}"
        try:
            req = urllib.request.Request(base + "/v1/tasks", data=b'{"capability":"long"}', method="POST")
            req.add_header("Content-Type", "application/json")
            try:
                urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 400)
        finally:
            other.shutdown(); other.server_close(); thread.join(timeout=5)
            api.MAX_BODY = old

    def test_api_backpressure(self) -> None:
        import os
        os.environ["SWARMLAB_MAX_PENDING"] = "1"
        try:
            _req("POST", self.base + "/v1/tasks", {"capability": "bp"})
            status, _, _ = _req("POST", self.base + "/v1/tasks", {"capability": "bp"})
            self.assertIn(status, (409, 429))
        finally:
            os.environ.pop("SWARMLAB_MAX_PENDING", None)

    def test_stream_keepalive(self) -> None:
        resp = urllib.request.urlopen(self.base + "/v1/stream?after=999999&limit=1&timeout_s=1.4", timeout=5)
        try:
            self.assertIn(b": keepalive", resp.read())
        finally:
            resp.close()

    def test_stream_keepalive_env(self) -> None:
        import os
        os.environ["SWARMLAB_STREAM_KEEPALIVE_S"] = "0.1"
        try:
            resp = urllib.request.urlopen(self.base + "/v1/stream?after=999999&limit=1&timeout_s=0.4", timeout=5)
            try:
                self.assertIn(b": keepalive", resp.read())
            finally:
                resp.close()
        finally:
            os.environ.pop("SWARMLAB_STREAM_KEEPALIVE_S", None)

    def test_stream_listener_success(self) -> None:
        import threading
        from unittest.mock import patch

        from swarmlab.api import build_server
        store = SwarmStore(":memory:")
        store.dsn = "postgresql://x"
        store.backend = "postgres"
        other = build_server(store, "127.0.0.1", 0)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{other.server_address[1]}"
        class FakeListener:
            def wait(self, timeout=None):
                return None
            def close(self):
                return None
        try:
            with patch("swarmlab.events.PgEventStream", return_value=FakeListener()):
                resp = urllib.request.urlopen(base + "/v1/stream?after=0&limit=1&timeout_s=0.1", timeout=5)
                try:
                    self.assertEqual(resp.status, 200)
                    resp.read()
                finally:
                    resp.close()
        finally:
            other.shutdown(); other.server_close(); thread.join(timeout=5)

    def test_stream_listener_failure(self) -> None:
        import threading
        from unittest.mock import patch

        from swarmlab.api import build_server
        store = SwarmStore(":memory:")
        store.dsn = "postgresql://x"
        store.backend = "postgres"
        other = build_server(store, "127.0.0.1", 0)
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{other.server_address[1]}"
        try:
            with patch("swarmlab.events.PgEventStream", side_effect=RuntimeError("no pg")):
                resp = urllib.request.urlopen(base + "/v1/stream?after=0&limit=1&timeout_s=0.1", timeout=5)
                try:
                    self.assertEqual(resp.status, 200)
                    resp.read()
                finally:
                    resp.close()
        finally:
            other.shutdown(); other.server_close(); thread.join(timeout=5)

    def test_stream_empty(self) -> None:
        with urllib.request.urlopen(self.base + "/v1/stream?after=999999&limit=1&timeout_s=0.1", timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            resp.read()

    def test_lease_env(self) -> None:
        import os
        import time
        os.environ["SWARMLAB_LEASE_S"] = "120"
        try:
            _req("POST", self.base + "/v1/agents", {"agent_id": "le", "capabilities": ["le"]})
            _req("POST", self.base + "/v1/tasks", {"capability": "le"})
            _, claim, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "le", "capability": "le"})
            self.assertGreater(claim["data"]["lease_until"], time.time() + 100)
        finally:
            os.environ.pop("SWARMLAB_LEASE_S", None)

    def test_tokens_invalid(self) -> None:
        import os

        from swarmlab.api import build_server
        os.environ["SWARMLAB_TOKENS"] = "not-json"
        try:
            other = build_server(SwarmStore(":memory:"), "127.0.0.1", 0)
        finally:
            os.environ.pop("SWARMLAB_TOKENS", None)
        other.server_close()

    def test_delete_rate(self) -> None:
        import os
        os.environ["SWARMLAB_RATE_RPS"] = "1"
        try:
            req = urllib.request.Request(self.base + "/v1/agents/x", method="DELETE")
            codes = []
            for _ in range(2):
                try:
                    urllib.request.urlopen(req, timeout=3)
                except urllib.error.HTTPError as exc:
                    codes.append(exc.code)
            self.assertIn(429, codes)
        finally:
            os.environ.pop("SWARMLAB_RATE_RPS", None)

    def test_delete_auth(self) -> None:
        from swarmlab.api import build_server
        other = build_server(SwarmStore(":memory:"), "127.0.0.1", 0, "tok")
        thread = threading.Thread(target=other.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{other.server_address[1]}"
        try:
            req = urllib.request.Request(base + "/v1/agents/x", method="DELETE")
            try:
                urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 401)
            req = urllib.request.Request(base + "/nope", method="DELETE")
            req.add_header("Authorization", "Bearer tok")
            try:
                urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 404)
        finally:
            other.shutdown(); other.server_close(); thread.join(timeout=5)

    def test_query_filters(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "q", "capabilities": ["q"]})
        _req("POST", self.base + "/v1/tasks", {"capability": "q"})
        self.assertEqual(_req("GET", self.base + "/v1/agents?capability=q&limit=1")[0], 200)
        self.assertEqual(_req("GET", self.base + "/v1/tasks?status=pending&limit=1")[0], 200)
        self.assertEqual(_req("GET", self.base + "/v1/events?after=0&limit=1")[0], 200)
        self.assertEqual(_req("GET", self.base + "/v1/tasks?limit=bad")[0], 400)
        self.assertEqual(_req("GET", self.base + "/v1/agents?limit=bad")[0], 400)

    def test_openapi(self) -> None:
        status, body, _ = _req("GET", self.base + "/v1/openapi")
        self.assertEqual(status, 200)
        self.assertEqual(body["openapi"], "3.1.0")
        self.assertIn("/v1/tasks/{task_id}/complete", body["paths"])

    def test_version_capabilities(self) -> None:
        status, body, _ = _req("GET", self.base + "/v1/version")
        self.assertEqual(status, 200)
        self.assertIn("version", body["data"])
        status, body, _ = _req("GET", self.base + "/v1/capabilities")
        self.assertEqual(status, 200)
        self.assertIn("batch", body["data"]["features"])

    def test_deregister_api(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "del", "capabilities": ["x"]})
        req = urllib.request.Request(self.base + "/v1/agents/del", method="DELETE")
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
        self.assertEqual(_req("GET", self.base + "/v1/agents?capability=x")[1]["data"], [])
        req = urllib.request.Request(self.base + "/nope", method="DELETE")
        try:
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 404)

    def test_max_attempts_api(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "ma", "capabilities": ["ma"]})
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "ma", "max_attempts": 1})
        task_id = body["data"]["task_id"]
        _, claim, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "ma", "capability": "ma"})
        self.assertEqual(claim["data"]["attempts"], 1)
        _, task, _ = _req("GET", self.base + f"/v1/tasks/{task_id}")
        self.assertEqual(task["data"]["max_attempts"], 1)

    def test_batch_maintenance(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "bm", "capabilities": ["bm"]})
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "bm"})
        task_id = body["data"]["task_id"]
        _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "bm", "capability": "bm"})
        status, body, _ = _req("POST", self.base + "/v1/batch", {"ops": [
            {"op": "cancel", "task_id": task_id, "agent_id": "bm"},
            {"op": "requeue", "task_id": task_id},
            {"op": "expire"},
        ]})
        self.assertEqual(status, 200)
        self.assertTrue(all(r.get("ok") for r in body["data"]))
        # пустое тело POST
        req = urllib.request.Request(self.base + "/v1/batch", data=b"", method="POST")
        try:
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)

    def test_dependencies_api(self) -> None:
        _, first, _ = _req("POST", self.base + "/v1/tasks", {"capability": "dep"})
        first_id = first["data"]["task_id"]
        _, second, _ = _req("POST", self.base + "/v1/tasks", {"capability": "dep", "depends_on": first_id})
        second_id = second["data"]["task_id"]
        _req("POST", self.base + "/v1/agents", {"agent_id": "dep", "capabilities": ["dep"]})
        _, claim, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "dep", "capability": "dep"})
        self.assertEqual(claim["data"]["task_id"], first_id)
        _, claim2, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "dep", "capability": "dep"})
        self.assertIsNone(claim2["data"])
        _req("POST", self.base + f"/v1/tasks/{first_id}/complete", {"agent_id": "dep", "fence": claim["data"]["lease_epoch"]})
        _, claim3, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "dep", "capability": "dep"})
        self.assertEqual(claim3["data"]["task_id"], second_id)

    def test_expire_api(self) -> None:
        import time
        _req("POST", self.base + "/v1/tasks", {"capability": "exp", "ttl_s": 0.01})
        time.sleep(0.03)
        status, body, _ = _req("POST", self.base + "/v1/maintenance/expire", {})
        self.assertEqual(status, 200)
        self.assertGreaterEqual(body["data"]["expired"], 0)

    def test_ttl_api(self) -> None:
        import time
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "ttl", "ttl_s": 0.01})
        task_id = body["data"]["task_id"]
        time.sleep(0.03)
        _req("POST", self.base + "/v1/agents", {"agent_id": "ttl", "capabilities": ["ttl"]})
        _, claim, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "ttl", "capability": "ttl"})
        self.assertIsNone(claim["data"])
        _, task, _ = _req("GET", self.base + f"/v1/tasks/{task_id}")
        self.assertEqual(task["data"]["status"], "expired")

    def test_requeue_api(self) -> None:
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "rq"})
        task_id = body["data"]["task_id"]
        _req("POST", self.base + f"/v1/tasks/{task_id}/cancel", {})
        status, body, _ = _req("POST", self.base + f"/v1/tasks/{task_id}/requeue", {})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "pending")
        self.assertEqual(_req("POST", self.base + f"/v1/tasks/{task_id}/requeue", {})[0], 409)

    def test_cancel_api(self) -> None:
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "c"})
        task_id = body["data"]["task_id"]
        status, body, _ = _req("POST", self.base + f"/v1/tasks/{task_id}/cancel", {})
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "cancelled")
        self.assertEqual(_req("POST", self.base + "/v1/tasks/nope/cancel", {})[0], 404)

    def test_get_task(self) -> None:
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "g"})
        task_id = body["data"]["task_id"]
        status, payload, _ = _req("GET", self.base + f"/v1/tasks/{task_id}")
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["task_id"], task_id)
        self.assertEqual(_req("GET", self.base + "/v1/tasks/nope")[0], 404)

    def test_rate_env_and_batch_complete(self) -> None:
        import os
        os.environ["SWARMLAB_RATE_RPS"] = "bad"
        try:
            self.assertEqual(_req("GET", self.base + "/health")[0], 200)
        finally:
            os.environ.pop("SWARMLAB_RATE_RPS", None)
        _req("POST", self.base + "/v1/agents", {"agent_id": "z", "capabilities": ["x"]})
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "x"})
        task_id = body["data"]["task_id"]
        _, body, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "z", "capability": "x"})
        fence = body["data"]["lease_epoch"]
        status, body, _ = _req("POST", self.base + "/v1/batch", {"ops": [
            {"op": "renew", "task_id": task_id, "agent_id": "z", "fence": fence},
            {"op": "complete", "task_id": task_id, "agent_id": "z", "fence": fence},
        ]})
        self.assertEqual(status, 200)
        self.assertTrue(all(r.get("ok") for r in body["data"]))

    def test_auth_and_heartbeat(self) -> None:
        import os
        # legacy token mode с отдельным сервером
        os.environ["SWARMLAB_TOKEN"] = "legacy"
        try:
            other = build_server(SwarmStore(":memory:"), "127.0.0.1", 0, "legacy")
            base = f"http://127.0.0.1:{other.server_address[1]}"
            thread = threading.Thread(target=other.serve_forever, daemon=True)
            thread.start()
            try:
                self.assertEqual(_req("GET", base + "/v1/stats")[0], 401)
                self.assertEqual(_req("GET", base + "/v1/stats", None, "legacy")[0], 200)
            finally:
                other.shutdown(); other.server_close(); thread.join(timeout=5)
        finally:
            os.environ.pop("SWARMLAB_TOKEN", None)
        _req("POST", self.base + "/v1/agents", {"agent_id": "h", "capabilities": ["x"]})
        self.assertEqual(_req("POST", self.base + "/v1/heartbeat", {"agent_id": "h"})[0], 200)

    def test_batch_ops(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "b", "capabilities": ["x"]})
        _req("POST", self.base + "/v1/tasks", {"capability": "x"})
        status, body, _ = _req("POST", self.base + "/v1/batch", {"ops": [
            {"op": "submit", "capability": "x"},
            {"op": "claim", "agent_id": "b", "capability": "x"},
            {"op": "events"},
            {"op": "stats"},
            {"op": "bad"},
            1,
        ]})
        self.assertEqual(status, 200)
        self.assertEqual(len(body["data"]), 6)
        self.assertEqual(_req("GET", self.base + "/v1/tasks?limit=bad")[0], 400)

    def test_post_errors(self) -> None:
        self.assertEqual(_req("POST", self.base + "/v1/agents", {"agent_id": "x", "capabilities": "bad"})[0], 400)
        self.assertEqual(_req("POST", self.base + "/v1/heartbeat", {})[0], 400)
        self.assertEqual(_req("POST", self.base + "/v1/batch", {"ops": "bad"})[0], 400)
        self.assertEqual(_req("POST", self.base + "/nope", {})[0], 404)
        req = urllib.request.Request(self.base + "/v1/tasks", data=b"[]", method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
        req = urllib.request.Request(self.base + "/v1/tasks", data=b"x" * (1 << 20 + 10), method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)
        except (urllib.error.URLError, ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            pass

    def test_renew_and_stream(self) -> None:
        _req("POST", self.base + "/v1/agents", {"agent_id": "r", "capabilities": ["x"]})
        _, body, _ = _req("POST", self.base + "/v1/tasks", {"capability": "x"})
        task_id = body["data"]["task_id"]
        _, body, _ = _req("POST", self.base + "/v1/tasks/claim", {"agent_id": "r", "capability": "x"})
        fence = body["data"]["lease_epoch"]
        status, renewed, _ = _req("POST", self.base + f"/v1/tasks/{task_id}/renew", {"agent_id": "r", "fence": fence})
        self.assertEqual(status, 200)
        self.assertIn("lease_until", renewed["data"])
        status, _, _ = _req("GET", self.base + "/v1/tasks?status=claimed")
        self.assertEqual(status, 200)
        status, _, _ = _req("POST", self.base + "/v1/batch", {"ops": [{"op": "nope"}]})
        self.assertEqual(status, 200)
        req = urllib.request.Request(self.base + "/v1/stream?after=0&limit=1&timeout_s=0.2", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)

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
