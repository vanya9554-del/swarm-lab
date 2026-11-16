"""SQLite restore: integrity-check backup, then atomic replace."""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import tempfile
from pathlib import Path


def restore(backup: str | Path, db: str | Path) -> Path:
    backup = Path(backup)
    db = Path(db)
    if not backup.exists():
        raise FileNotFoundError(backup)
    check = sqlite3.connect(backup)
    try:
        result = check.execute("PRAGMA quick_check").fetchone()
    finally:
        check.close()
    if not result or result[0] != "ok":
        raise RuntimeError(f"backup integrity check failed: {result}")
    db.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=db.name, suffix=".tmp", dir=str(db.parent))
    os.close(fd)
    try:
        shutil.copy2(backup, tmp)
        for suffix in ("-wal", "-shm"):
            side = Path(str(db) + suffix)
            if side.exists():
                side.unlink()
        os.replace(tmp, db)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return db


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backup", required=True)
    ap.add_argument("--db", default="data/swarm.db")
    args = ap.parse_args(argv)
    print(restore(args.backup, args.db))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
