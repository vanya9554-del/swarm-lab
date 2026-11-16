"""S10: chaos — 3 реплики, 6 воркеров, 500 задач, exactly-once."""
from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
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


class ChaosTests(unittest.TestCase):
    TASKS = 500

    @classmethod
    def setUpClass(cls) -> None:
        if not PG:
            raise unittest.SkipTest("psycopg/pgserver not installed")
        cls.tmp = tempfile.TemporaryDirectory(prefix="swarmlab-chaos-", ignore_cleanup_errors=True)
        cls.work = Path(cls.tmp.name)
        pgdata = _init(cls.work)
        import pgserver
        cls.srv = pgserver.get_server(str(pgdata), cleanup_mode=None)
        uri = cls.srv.get_uri()
        with psycopg.connect(uri.rsplit("/", 1)[0] + "/postgres", connect_timeout=15) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("DROP DATABASE IF EXISTS swarmchaos")
                cur.execute("CREATE DATABASE swarmchaos WITH ENCODING 'UTF8' TEMPLATE template0")
        cls.dsn = uri.rsplit("/", 1)[0] + "/swarmchaos"

    @classmethod
    def tearDownClass(cls) -> None:
        if not PG:
            return
        try:
            cls.srv.cleanup()
        except Exception:  # noqa: BLE001, S110
            pass
        cls.tmp.cleanup()

    def test_http_two_replicas(self) -> None:
        import threading

        from swarmlab.api import build_server
        from swarmlab.client import SwarmClient
        from swarmlab.pg import PgSwarmStore

        stores = [PgSwarmStore(self.dsn) for _ in range(2)]
        servers = [build_server(st, "127.0.0.1", 0) for st in stores]
        threads = [threading.Thread(target=srv.serve_forever, daemon=True) for srv in servers]
        for t in threads:
            t.start()
        clients = [SwarmClient(f"http://127.0.0.1:{srv.server_address[1]}") for srv in servers]
        try:
            for i, c in enumerate(clients):
                c.register(f"h{i}", ["httpchaos"])
            baseline = clients[0].stats()["tasks"].get("completed", 0)
            for i in range(100):
                clients[0].submit("httpchaos", {"n": i})
            seen: list[str] = []
            errors: list[BaseException] = []
            lock = threading.Lock()
            barrier = threading.Barrier(2)

            def worker(idx: int) -> None:
                try:
                    barrier.wait(timeout=5)
                    while True:
                        task = clients[idx].claim(f"h{idx}", "httpchaos")
                        if not task:
                            return
                        clients[idx].complete(task["task_id"], f"h{idx}", {}, task["lease_epoch"])
                        with lock:
                            seen.append(task["task_id"])
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            workers = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
            for t in workers:
                t.start()
            for t in workers:
                t.join(timeout=30)
            self.assertFalse(errors, errors)
            self.assertEqual(len(seen), 100)
            self.assertEqual(len(set(seen)), 100)
            self.assertEqual(clients[0].stats()["tasks"].get("completed"), baseline + 100)
        finally:
            for c in clients:
                c.close()
            for srv in servers:
                srv.shutdown()
                srv.server_close()
            for st in stores:
                st.close()

    def test_chaos_exactly_once(self) -> None:
        from swarmlab.pg import PgSwarmStore
        stores = [PgSwarmStore(self.dsn) for _ in range(3)]
        try:
            for i, store in enumerate(stores):
                store.register(f"w{i}", ["chaos"])
            for i in range(self.TASKS):
                stores[0].submit("chaos", {"n": i}, priority=i % 7)
            seen: list[str] = []
            errors: list[BaseException] = []
            lock = threading.Lock()
            barrier = threading.Barrier(6)

            def worker(store, agent):
                try:
                    barrier.wait(timeout=10)
                    while True:
                        task = store.claim(agent, "chaos", lease_s=30)
                        if not task:
                            return
                        store.complete(task["task_id"], agent, {"ok": 1}, fence=task["lease_epoch"])
                        with lock:
                            seen.append(task["task_id"])
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [
                threading.Thread(target=worker, args=(stores[i % 3], f"w{i % 3}"))
                for i in range(6)
            ]
            started = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=60)
            elapsed = time.perf_counter() - started
            self.assertFalse(errors, errors)
            self.assertEqual(len(seen), self.TASKS)
            self.assertEqual(len(set(seen)), self.TASKS)
            self.assertLess(elapsed, 60)
            stats = stores[0].stats()
            self.assertEqual(stats["tasks"].get("completed"), self.TASKS)
        finally:
            for s in stores:
                s.close()


if __name__ == "__main__":
    unittest.main()
