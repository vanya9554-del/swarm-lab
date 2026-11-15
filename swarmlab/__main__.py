# -*- coding: utf-8 -*-
"""swarm-lab CLI (bootstrap)."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .store import SwarmStore


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="swarmlab")
    ap.add_argument("--version", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    demo = sub.add_parser("demo", help="локальный smoke")
    demo.add_argument("--db", default=":memory:")
    args = ap.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.cmd == "demo":
        store = SwarmStore(args.db)
        try:
            store.register("a1", ["search"])
            t = store.submit("search", {"q": "x"})
            claimed = store.claim("a1", "search")
            done = store.complete(t["task_id"], "a1", {"ok": 1}, fence=claimed["lease_epoch"])
            print(json.dumps({"task": done, "stats": store.stats()}, ensure_ascii=False, indent=2))
        finally:
            store.close()
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
