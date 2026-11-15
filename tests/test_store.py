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
