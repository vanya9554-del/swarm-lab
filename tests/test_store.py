from __future__ import annotations

import unittest

from swarmlab.store import SwarmError, SwarmStore


class StoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = SwarmStore(":memory:")
        self.store.register("a1", ["search", "write"])
        self.store.register("a2", ["search"])

    def tearDown(self) -> None:
        self.store.close()

    def test_discovery_and_dedup(self) -> None:
        agents = self.store.discover("search")
        self.assertEqual({a["agent_id"] for a in agents}, {"a1", "a2"})
        first = self.store.submit("search", {"q": 1}, dedup_key="k")
        second = self.store.submit("search", {"q": 2}, dedup_key="k")
        self.assertEqual(first["task_id"], second["task_id"])
        self.assertTrue(second.get("duplicate"))

    def test_claim_fence_and_stale(self) -> None:
        task = self.store.submit("search", {"q": 1})
        claimed = self.store.claim("a1", "search")
        self.assertEqual(claimed["task_id"], task["task_id"])
        fence = claimed["lease_epoch"]
        # имитируем истёкший lease и reclaim
        self.store.conn.execute("UPDATE tasks SET lease_until=0 WHERE task_id=?", (task["task_id"],))
        again = self.store.claim("a2", "search")
        self.assertGreater(again["lease_epoch"], fence)
        with self.assertRaises(SwarmError) as caught:
            self.store.complete(task["task_id"], "a1", {}, fence=fence)
        self.assertEqual(caught.exception.code, "STALE_LEASE")
        done = self.store.complete(task["task_id"], "a2", {"ok": 1}, fence=again["lease_epoch"])
        self.assertEqual(done["status"], "completed")
        idem = self.store.complete(task["task_id"], "a2", {"ok": 2}, fence=again["lease_epoch"])
        self.assertTrue(idem.get("idempotent"))

    def test_task_events(self) -> None:
        t = self.store.submit("x", {})
        self.store.claim("a1", "x")
        events = self.store.task_events(t["task_id"])
        self.assertTrue(any(e["type"] == "task.claimed" for e in events))
        self.assertEqual(self.store.task_events("nope"), [])
        self.store.conn.execute(
            "INSERT INTO events(type, payload, created_at) VALUES ('bad', '{\"task_id\":\"x\"', 0)"
        )
        self.store.conn.commit()
        self.assertEqual(self.store.task_events("x"), [])

    def test_prune(self) -> None:
        t = self.store.submit("x", {})
        self.store.claim("a1", "x")
        self.store.complete(t["task_id"], "a1", {}, fence=self.store.get(t["task_id"])["lease_epoch"])
        self.store.conn.execute("UPDATE tasks SET completed_at=0 WHERE task_id=?", (t["task_id"],))
        self.store.conn.execute("INSERT INTO events(type, payload, created_at) VALUES ('old', '{}', 0)")
        self.store.conn.execute("INSERT INTO audit(created_at, action, detail) VALUES (0, 'old', '{}')")
        self.store.conn.commit()
        out = self.store.prune(60)
        self.assertGreaterEqual(out["tasks"], 1)
        self.assertGreaterEqual(out["events"], 1)
        self.assertGreaterEqual(out["audits"], 1)

    def test_vacuum(self) -> None:
        self.assertTrue(self.store.vacuum()["ok"])

    def test_audit(self) -> None:
        self.store.audit("login", "actor", "/x", {"ok": 1}, "127.0.0.1")
        rows = self.store.audits()
        self.assertEqual(rows[0]["action"], "login")
        self.assertEqual(rows[0]["detail"], {"ok": 1})

    def test_audit_filter(self) -> None:
        self.store.audit("a", "actor1")
        self.store.audit("b", "actor2")
        self.assertEqual(len(self.store.audits(action="a")), 1)
        self.assertEqual(self.store.audits(actor="actor2")[0]["action"], "b")

    def test_audit_invalid_detail(self) -> None:
        self.store.conn.execute("INSERT INTO audit(created_at, action, detail) VALUES (0, 'x', 'bad')")
        self.assertEqual(self.store.audits()[0]["detail"], "bad")

    def test_schema_version(self) -> None:
        self.assertEqual(self.store.schema_version(), 11)

    def test_check(self) -> None:
        self.assertEqual(self.store.check()["quick_check"], "ok")

    def test_get_agent(self) -> None:
        self.assertEqual(self.store.get_agent("a1")["agent_id"], "a1")
        self.assertIsNone(self.store.get_agent("nope"))

    def test_deregister(self) -> None:
        self.assertTrue(self.store.deregister("a1")["deleted"])
        self.assertNotIn("a1", {a["agent_id"] for a in self.store.discover("search")})
        self.assertFalse(self.store.deregister("nope")["deleted"])

    def test_invalid_result(self) -> None:
        import time
        self.store.conn.execute(
            "INSERT INTO tasks(task_id, capability, payload, priority, status, lease_epoch, result, created_at) "
            "VALUES ('badr', 'x', '{}', 0, 'completed', 1, 'not-json', ?)",
            (time.time(),),
        )
        self.store.conn.commit()
        self.assertEqual(self.store.get("badr")["result"], "not-json")

    def test_renew_stale(self) -> None:
        t = self.store.submit("x", {})
        self.store.claim("a1", "x")
        with self.assertRaises(SwarmError):
            self.store.renew(t["task_id"], "a1", fence=999)
        with self.assertRaises(SwarmError):
            self.store.renew("missing", "a1")

    def test_stale_event_decode(self) -> None:
        import time
        t = self.store.submit("x", {})
        self.store.claim("a1", "x")
        with self.assertRaises(SwarmError):
            self.store.complete(t["task_id"], "a1", {}, fence=999)
        self.store.conn.execute(
            "INSERT INTO events(seq, type, payload, created_at) VALUES (999999, 'bad', 'not-json', ?)",
            (time.time(),),
        )
        self.store.conn.commit()
        self.assertTrue(any(e["type"] == "bad" for e in self.store.events(999998, 5)))

    def test_invalid_payload(self) -> None:
        import time
        self.store.conn.execute(
            "INSERT INTO tasks(task_id, capability, payload, priority, status, lease_epoch, created_at) "
            "VALUES ('bad', 'x', 'not-json', 0, 'pending', 1, ?)",
            (time.time(),),
        )
        self.store.conn.commit()
        self.assertEqual(self.store.get("bad")["payload"], "not-json")

    def test_agent_ttl(self) -> None:
        import os
        self.store.register("ttl-agent", ["search"])
        self.store.conn.execute("UPDATE agents SET last_seen_at=0 WHERE agent_id='ttl-agent'")
        self.store.conn.commit()
        os.environ["SWARMLAB_AGENT_TTL"] = "1"
        try:
            self.assertNotIn("ttl-agent", {a["agent_id"] for a in self.store.discover("search")})
        finally:
            os.environ.pop("SWARMLAB_AGENT_TTL", None)

    def test_invalid_max_pending(self) -> None:
        import os
        os.environ["SWARMLAB_MAX_PENDING"] = "bad"
        try:
            self.store.submit("x", {})
        finally:
            os.environ.pop("SWARMLAB_MAX_PENDING", None)

    def test_backpressure(self) -> None:
        import os

        from swarmlab.store import SwarmStore
        os.environ["SWARMLAB_MAX_PENDING"] = "1"
        try:
            s = SwarmStore(":memory:")
            try:
                s.submit("x", {})
                with self.assertRaises(SwarmError):
                    s.submit("x", {})
            finally:
                s.close()
        finally:
            os.environ.pop("SWARMLAB_MAX_PENDING", None)

    def test_migration(self) -> None:
        import sqlite3
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "old.db"
            conn = sqlite3.connect(path)
            conn.execute(
                "CREATE TABLE tasks (task_id TEXT PRIMARY KEY, capability TEXT NOT NULL, payload TEXT NOT NULL, "
                "priority INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, dedup_key TEXT, claimed_by TEXT, "
                "lease_until REAL, lease_epoch INTEGER NOT NULL DEFAULT 1, result TEXT, affinity_agent_id TEXT, "
                "created_at REAL NOT NULL)"
            )
            conn.commit(); conn.close()
            store = SwarmStore(str(path))
            try:
                store.register("a1", ["x"])
                t = store.submit("x", {})
                self.assertEqual(store.get(t["task_id"])["attempts"], 0)
            finally:
                store.close()

    def test_claim_exception(self) -> None:
        from unittest.mock import patch
        self.store.submit("x", {})
        with patch.object(self.store, "_one", side_effect=RuntimeError("boom")), self.assertRaises(RuntimeError):
            self.store.claim("a1", "x")

    def test_claim_rollback(self) -> None:
        self.store.submit("x", {})
        real = self.store.conn

        class Flaky:
            def __init__(self, conn):
                self._conn = conn
            def execute(self, sql, *args, **kwargs):
                if str(sql).startswith("BEGIN"):
                    raise RuntimeError("db locked")
                return self._conn.execute(sql, *args, **kwargs)
            def __getattr__(self, name):
                return getattr(self._conn, name)

        self.store.conn = Flaky(real)
        try:
            with self.assertRaises(RuntimeError):
                self.store.claim("a1", "x")
        finally:
            self.store.conn = real

    def test_guards(self) -> None:
        t = self.store.submit("x", {})
        claimed = self.store.claim("a1", "x")
        with self.assertRaises(SwarmError):
            self.store.renew(t["task_id"], "a2")
        with self.assertRaises(SwarmError):
            self.store.complete(t["task_id"], "a2", {})
        with self.assertRaises(SwarmError):
            self.store.complete(t["task_id"], "a1", {}, fence=999)
        with self.assertRaises(SwarmError):
            self.store.requeue("missing")
        self.store.complete(t["task_id"], "a1", {}, fence=claimed["lease_epoch"])

    def test_attempts(self) -> None:
        import time
        t = self.store.submit("x", {}, max_attempts=1)
        first = self.store.claim("a1", "x", lease_s=1.0)
        self.assertEqual(first["attempts"], 1)
        time.sleep(1.1)
        self.assertIsNone(self.store.claim("a1", "x"))
        self.assertEqual(self.store.get(t["task_id"])["status"], "failed")
        self.store.requeue(t["task_id"])
        self.assertEqual(self.store.claim("a1", "x")["attempts"], 1)

    def test_dependencies(self) -> None:
        first = self.store.submit("x", {})
        second = self.store.submit("x", {}, depends_on=first["task_id"])
        self.assertEqual(self.store.claim("a1", "x")["task_id"], first["task_id"])
        self.assertIsNone(self.store.claim("a1", "x"))
        self.store.complete(first["task_id"], "a1", {}, fence=self.store.get(first["task_id"])["lease_epoch"])
        self.assertEqual(self.store.claim("a1", "x")["task_id"], second["task_id"])

    def test_ttl(self) -> None:
        import time
        t = self.store.submit("x", {}, ttl_s=0.01)
        time.sleep(1.1)
        self.assertIsNone(self.store.claim("a1", "x"))
        self.assertEqual(self.store.get(t["task_id"])["status"], "expired")
        self.assertEqual(self.store.expire()["expired"], 0)

    def test_requeue(self) -> None:
        t = self.store.submit("x", {})
        self.store.cancel(t["task_id"])
        self.assertEqual(self.store.requeue(t["task_id"])["status"], "pending")
        with self.assertRaises(SwarmError):
            self.store.requeue(t["task_id"])

    def test_cancel(self) -> None:
        t = self.store.submit("x", {})
        self.assertEqual(self.store.cancel(t["task_id"])["status"], "cancelled")
        self.assertTrue(self.store.cancel(t["task_id"]).get("idempotent"))
        claimed = self.store.submit("x", {})
        self.store.claim("a1", "x")
        self.assertEqual(self.store.cancel(claimed["task_id"], "a1")["status"], "cancelled")
        other = self.store.submit("x", {})
        self.store.claim("a1", "x")
        with self.assertRaises(SwarmError):
            self.store.cancel(other["task_id"], "a2")

    def test_affinity_priority_and_events(self) -> None:
        low = self.store.submit("search", {"n": 1}, priority=1)
        high = self.store.submit("search", {"n": 2}, priority=9)
        claimed = self.store.claim("a1", "search")
        self.assertEqual(claimed["task_id"], high["task_id"])
        self.store.complete(high["task_id"], "a1", {}, fence=claimed["lease_epoch"])
        low_claim = self.store.claim("a1", "search")
        self.assertEqual(low_claim["task_id"], low["task_id"])
        self.store.complete(low["task_id"], "a1", {}, fence=low_claim["lease_epoch"])
        other = self.store.submit("search", {"n": 3}, affinity_agent_id="a2")
        self.assertIsNone(self.store.claim("a1", "search"))
        got = self.store.claim("a2", "search")
        self.assertEqual(got["task_id"], other["task_id"])
        self.assertGreaterEqual(len(self.store.events(0, 20)), 4)
        self.assertIn("tasks", self.store.stats())


if __name__ == "__main__":
    unittest.main()
