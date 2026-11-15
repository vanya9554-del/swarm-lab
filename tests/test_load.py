"""S5: load/chaos — exactly-once и stale workers."""
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


class LoadTests(unittest.TestCase):
    TASKS = 50

    @classmethod
    def setUpClass(cls) -> None:
        if not PG:
            raise unittest.SkipTest("psycopg/pgserver not installed")
        cls.tmp = tempfile.TemporaryDirectory(prefix="swarmlab-load-", ignore_cleanup_errors=True)
        cls.work = Path(cls.tmp.name)
        pgdata = _init(cls.work)
        import pgserver
        cls.srv = pgserver.get_server(str(pgdata), cleanup_mode=None)
        uri = cls.srv.get_uri()
        with psycopg.connect(uri.rsplit("/", 1)[0] + "/postgres", connect_timeout=15) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("DROP DATABASE IF EXISTS swarmload")
                cur.execute("CREATE DATABASE swarmload WITH ENCODING 'UTF8' TEMPLATE template0")
        cls.dsn = uri.rsplit("/", 1)[0] + "/swarmload"

    @classmethod
    def tearDownClass(cls) -> None:
        if not PG:
            return
        try:
            cls.srv.cleanup()
        except Exception:  # noqa: BLE001, S110
            pass
        cls.tmp.cleanup()

    def test_parallel_exactly_once_and_stale(self) -> None:
        from swarmlab.pg import PgSwarmStore
        stores = [PgSwarmStore(self.dsn) for _ in range(2)]
        try:
            for i, store in enumerate(stores):
                store.register(f"w{i}", ["load"])
            for i in range(self.TASKS):
                stores[0].submit("load", {"n": i}, priority=i % 4)
            seen: list[str] = []
            lock = threading.Lock()
            barrier = threading.Barrier(2)

            def worker(store, agent):
                barrier.wait(timeout=5)
                while True:
                    task = store.claim(agent, "load", lease_s=30)
                    if not task:
                        return
                    store.complete(task["task_id"], agent, {"ok": 1}, fence=task["lease_epoch"])
                    with lock:
                        seen.append(task["task_id"])

            threads = [threading.Thread(target=worker, args=(stores[i], f"w{i}")) for i in range(2)]
            t0 = time.perf_counter()
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=20)
            elapsed = time.perf_counter() - t0
            self.assertEqual(len(seen), self.TASKS)
            self.assertEqual(len(set(seen)), self.TASKS)
            self.assertLess(elapsed, 20)
            # stale: kлейм, истекаем lease, reclaim другим, старый fence отклонён
            stores[0].register("w2", ["chaos"])
            task = stores[0].submit("chaos", {})
            first = stores[0].claim("w0", "chaos", lease_s=1)
            stores[0].conn.execute("UPDATE tasks SET lease_until=0 WHERE task_id=%s", (task["task_id"],))
            stores[0].conn.commit()
            second = stores[0].claim("w2", "chaos", lease_s=10)
            with self.assertRaises(RuntimeError):
                stores[0].complete(task["task_id"], "w0", {}, fence=first["lease_epoch"])
            stores[0].complete(task["task_id"], "w2", {}, fence=second["lease_epoch"])
        finally:
            for s in stores:
                s.close()


if __name__ == "__main__":
    unittest.main()



class SqliteConcurrencyTests(unittest.TestCase):
    def test_sqlite_concurrent_store(self) -> None:
        from swarmlab.store import SwarmStore
        store = SwarmStore(":memory:")
        try:
            for i in range(8):
                store.register(f"c{i}", ["c"])
            for i in range(100):
                store.submit("c", {"n": i})
            errors: list[BaseException] = []
            seen: list[str] = []
            lock = threading.Lock()
            barrier = threading.Barrier(8)

            def worker(i: int) -> None:
                try:
                    barrier.wait(timeout=5)
                    while True:
                        task = store.claim(f"c{i}", "c")
                        if not task:
                            return
                        store.complete(task["task_id"], f"c{i}", {}, fence=task["lease_epoch"])
                        with lock:
                            seen.append(task["task_id"])
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=20)
            self.assertFalse(errors, errors)
            self.assertEqual(len(seen), 100)
            self.assertEqual(len(set(seen)), 100)
        finally:
            store.close()
