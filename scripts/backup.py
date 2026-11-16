"""SQLite backup: VACUUM INTO + integrity check."""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def backup(db: str | Path, out: str | Path) -> Path:
    db = Path(db)
    out = Path(out)
    if not db.exists():
        raise FileNotFoundError(db)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    src = sqlite3.connect(db)
    try:
        src.execute("VACUUM INTO ?", (str(out),))
    finally:
        src.close()
    check = sqlite3.connect(out)
    try:
        result = check.execute("PRAGMA quick_check").fetchone()
    finally:
        check.close()
    if not result or result[0] != "ok":
        raise RuntimeError(f"backup integrity check failed: {result}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="data/swarm.db")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    path = backup(args.db, args.out)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
