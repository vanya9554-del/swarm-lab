from __future__ import annotations

import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BackupTests(unittest.TestCase):
    def test_backup_restore_roundtrip(self) -> None:
        from swarmlab.store import SwarmStore

        backup_mod = _load("backup")
        restore_mod = _load("restore")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "swarm.db"
            store = SwarmStore(str(db))
            try:
                store.register("a1", ["x"])
                task = store.submit("x", {"v": 1})
            finally:
                store.close()
            out = backup_mod.backup(db, Path(tmp) / "backup.db")
            self.assertTrue(out.exists())
            restored = Path(tmp) / "restored.db"
            restore_mod.restore(out, restored)
            check = sqlite3.connect(restored)
            try:
                self.assertEqual(check.execute("PRAGMA quick_check").fetchone()[0], "ok")
                count = check.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            finally:
                check.close()
            self.assertEqual(count, 1)
            store = SwarmStore(str(restored))
            try:
                self.assertEqual(store.get(task["task_id"])["payload"], {"v": 1})
            finally:
                store.close()

    def test_restore_rejects_bad_file(self) -> None:
        restore_mod = _load("restore")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.db"
            bad.write_bytes(b"not a database")
            with self.assertRaises((RuntimeError, sqlite3.DatabaseError)):
                restore_mod.restore(bad, Path(tmp) / "out.db")


if __name__ == "__main__":
    unittest.main()
