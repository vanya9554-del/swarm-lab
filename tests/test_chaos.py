# -*- coding: utf-8 -*-
"""S10: chaos — 3 реплики, 6 воркеров, 100 задач, exactly-once."""
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
        text=True, capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-500:])
    return pgdata


class ChaosTests(unittest.TestCase):
    TASKS = 100

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
                t.join(timeout=30)
            elapsed = time.perf_counter() - started
            self.assertFalse(errors, errors)
            self.assertEqual(len(seen), self.TASKS)
            self.assertEqual(len(set(seen)), self.TASKS)
            self.assertLess(elapsed, 30)
            stats = stores[0].stats()
            self.assertEqual(stats["tasks"].get("completed"), self.TASKS)
        finally:
            for s in stores:
                s.close()


if __name__ == "__main__":
    unittest.main()
