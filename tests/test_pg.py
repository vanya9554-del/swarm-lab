from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

try:
    import pgserver  # noqa: F401
    import psycopg
    PG = True
except Exception:  # noqa: BLE001
    PG = False


def _init(work: Path) -> Path:
    pgdata = work / "pgdata"
    if (pgdata / "PG_VERSION").exists():
        return pgdata
    import pgserver
    bin_dir = Path(pgserver.__file__).resolve().parent / "pginstall" / "bin"
    initdb = bin_dir / ("initdb.exe" if os.name == "nt" else "initdb")
    pgdata.mkdir(parents=True)
    proc = subprocess.run(
        [str(initdb), "-D", str(pgdata), "--auth=trust", "--auth-local=trust",
         "--encoding=SQL_ASCII", "--locale=C", "-U", "postgres"],
        check=False, text=True, capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-500:])
    return pgdata


class PgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not PG:
            raise unittest.SkipTest("psycopg/pgserver not installed")
        cls.tmp = tempfile.TemporaryDirectory(prefix="swarmlab-pg-", ignore_cleanup_errors=True)
        cls.work = Path(cls.tmp.name)
        pgdata = _init(cls.work)
        import pgserver
        cls.srv = pgserver.get_server(str(pgdata), cleanup_mode=None)
        uri = cls.srv.get_uri()
        base = uri.rsplit("/", 1)[0] + "/postgres"
        with psycopg.connect(base, connect_timeout=15) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("DROP DATABASE IF EXISTS swarmlab")
                cur.execute("CREATE DATABASE swarmlab WITH ENCODING 'UTF8' TEMPLATE template0")
        cls.dsn = uri.rsplit("/", 1)[0] + "/swarmlab"

    @classmethod
    def tearDownClass(cls) -> None:
        if not PG:
            return
        try:
            cls.srv.cleanup()
        except Exception:  # noqa: BLE001, S110
            pass
        cls.tmp.cleanup()

    def test_multi_replica_claim(self) -> None:
        from swarmlab.pg import PgSwarmStore
        a = PgSwarmStore(self.dsn)
        b = PgSwarmStore(self.dsn)
        try:
            a.register("a1", ["x"])
            b.register("a2", ["x"])
            for i in range(20):
                a.submit("x", {"n": i})
            results: list[str] = []
            barrier = threading.Barrier(2)
            lock = threading.Lock()

            def worker(store, agent):
                barrier.wait(timeout=5)
                while True:
                    task = store.claim(agent, "x")
                    if not task:
                        return
                    store.complete(task["task_id"], agent, {"ok": 1}, fence=task["lease_epoch"])
                    with lock:
                        results.append(task["task_id"])

            threads = [
                threading.Thread(target=worker, args=(a, "a1")),
                threading.Thread(target=worker, args=(b, "a2")),
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=20)
            self.assertEqual(len(results), 20)
            self.assertEqual(len(set(results)), 20)
        finally:
            a.close()
            b.close()

    def test_edges(self) -> None:
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            with self.assertRaises(RuntimeError):
                s.heartbeat("missing")
            t = s.submit("edge", {"n": 1}, ttl_s=30, depends_on=None)
            s.cancel(t["task_id"])
            self.assertEqual(s.requeue(t["task_id"])["status"], "pending")
            with self.assertRaises(RuntimeError):
                s.requeue(t["task_id"])
            with self.assertRaises(RuntimeError):
                s.complete("missing", "x")
            with self.assertRaises(RuntimeError):
                s.renew(t["task_id"], "nobody")
            self.assertEqual(s.expire()["expired"], 0)
        finally:
            s.close()

    def test_attempts(self) -> None:
        import time
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            s.register("at", ["at"])
            t = s.submit("at", {}, max_attempts=1)
            first = s.claim("at", "at", lease_s=1.0)
            self.assertEqual(first["attempts"], 1)
            time.sleep(1.1)
            self.assertIsNone(s.claim("at", "at"))
            self.assertEqual(s.get(t["task_id"])["status"], "failed")
            s.requeue(t["task_id"])
            self.assertEqual(s.claim("at", "at")["attempts"], 1)
        finally:
            s.close()

    def test_claim_guards(self) -> None:
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            s.register("g1", ["g"])
            s.register("g2", ["g"])
            t = s.submit("g", {})
            first = s.claim("g1", "g")
            self.assertEqual(first["task_id"], t["task_id"])
            with self.assertRaises(RuntimeError):
                s.cancel(t["task_id"], "g2")
            with self.assertRaises(RuntimeError):
                s.renew(t["task_id"], "g1", fence=999)
            with self.assertRaises(RuntimeError):
                s.complete(t["task_id"], "g1", {}, fence=999)
        finally:
            s.close()

    def test_edge_paths(self) -> None:
        import time

        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            s.register("e1", ["e"])
            s.register("e2", ["e"])
            t = s.submit("e", {}, ttl_s=0.01, depends_on=None)
            time.sleep(1.1)
            self.assertGreaterEqual(s.expire()["expired"], 1)
            self.assertTrue(s.tasks())
            with self.assertRaises(RuntimeError):
                s.renew(t["task_id"], "e1", fence=999)
            with self.assertRaises(RuntimeError):
                s.requeue("missing")
            with self.assertRaises(RuntimeError):
                s.complete("missing", "e1")
            with self.assertRaises(RuntimeError):
                s.renew("missing", "e1")
        finally:
            s.close()

    def test_deregister(self) -> None:
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            s.register("gone", ["x"])
            self.assertTrue(s.deregister("gone")["deleted"])
            self.assertFalse(s.deregister("gone")["deleted"])
        finally:
            s.close()

    def test_ttl(self) -> None:
        import time

        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            s.register("ttl", ["ttl"])
            t = s.submit("ttl", {}, ttl_s=0.01)
            time.sleep(1.1)
            self.assertIsNone(s.claim("ttl", "ttl"))
            self.assertEqual(s.get(t["task_id"])["status"], "expired")
            self.assertEqual(s.expire()["expired"], 0)
        finally:
            s.close()

    def test_cancel(self) -> None:
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            s.register("c1", ["c"])
            t = s.submit("c", {})
            self.assertEqual(s.cancel(t["task_id"])["status"], "cancelled")
            self.assertTrue(s.cancel(t["task_id"]).get("idempotent"))
        finally:
            s.close()

    def test_more_methods(self) -> None:
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            s.register("m1", ["a"])
            s.register("m2", ["a"])
            self.assertEqual(s.heartbeat("m1")["agent_id"], "m1")
            self.assertEqual(len(s.discover("a")), 2)
            task = s.submit("a", {"n": 1}, priority=5)
            duplicate = s.submit("a", {}, dedup_key="pg-more")
            self.assertTrue(s.submit("a", {}, dedup_key="pg-more").get("duplicate"))
            claimed = s.claim("m1", "a")
            self.assertEqual(claimed["task_id"], task["task_id"])
            s.renew(task["task_id"], "m1", 30, claimed["lease_epoch"])
            self.assertIn("a", {r["capability"] for r in s.tasks("claimed")})
            self.assertGreaterEqual(len(s.events(0, 20)), 2)
            s.complete(task["task_id"], "m1", {}, fence=claimed["lease_epoch"])
            self.assertTrue(s.complete(task["task_id"], "m1", {}, fence=claimed["lease_epoch"]).get("idempotent"))
            self.assertIn("agents", s.stats())
            self.assertIsNotNone(duplicate)
        finally:
            s.close()

    def test_reconnect_after_connection_close(self) -> None:
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            s.conn.close()
            s.register("reconnect", ["x"])
            self.assertIn("agents", s.stats())
        finally:
            s.close()

    def test_pg_http_sse(self) -> None:
        import threading
        import urllib.request

        from swarmlab.api import build_server
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        server = build_server(s, "127.0.0.1", 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            s.register("sse", ["sse"])
            last = int(s.events(0, 100)[-1]["seq"])
            req = urllib.request.Request(
                f"http://127.0.0.1:{server.server_address[1]}/v1/stream?after={last}&limit=1&timeout_s=3",
                method="GET",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                s.submit("sse", {"ping": 1})
                line = resp.readline().decode().strip()
                if line.startswith("id:"):
                    line = resp.readline().decode().strip()
            self.assertTrue(line.startswith("data:"), line)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            s.close()

    def test_listen_notify(self) -> None:
        from swarmlab.events import PgEventStream
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        with PgEventStream(self.dsn) as listener:
            try:
                s.register("n1", ["notify"])
                task = s.submit("notify", {})
                payload = listener.wait(3.0)
                self.assertIsNotNone(payload)
                self.assertGreater(int(payload), 0)
                self.assertEqual(s.get(task["task_id"])["status"], "pending")
            finally:
                s.close()

    def test_dedup_and_fence(self) -> None:
        from swarmlab.pg import PgSwarmStore
        s = PgSwarmStore(self.dsn)
        try:
            s.register("a1", ["y"])
            first = s.submit("y", {}, dedup_key="k")
            second = s.submit("y", {}, dedup_key="k")
            self.assertEqual(first["task_id"], second["task_id"])
            claimed = s.claim("a1", "y")
            s.conn.execute("UPDATE tasks SET lease_until=0 WHERE task_id=%s", (first["task_id"],))
            s.conn.commit()
            other = s.claim("a1", "y")
            with self.assertRaises(RuntimeError):
                s.complete(first["task_id"], "a1", {}, fence=claimed["lease_epoch"])
            done = s.complete(first["task_id"], "a1", {}, fence=other["lease_epoch"])
            self.assertEqual(done["status"], "completed")
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()
