"""swarm-lab CLI (bootstrap)."""
from __future__ import annotations

import argparse
import json

from . import __version__, open_store


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="swarmlab")
    ap.add_argument("--version", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    demo = sub.add_parser("demo", help="локальный smoke")
    demo.add_argument("--db", default=":memory:")
    serve = sub.add_parser("serve", help="HTTP API")
    serve.add_argument("--db", default="swarm.db", help="sqlite path or postgresql:// DSN")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8788)
    serve.add_argument("--token", default=None)
    mcp = sub.add_parser("mcp", help="MCP stdio server")
    mcp.add_argument("--db", default="swarm.db")
    args = ap.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.cmd == "mcp":
        from .mcp import main_stdio
        store = open_store(args.db)
        try:
            main_stdio(store)
        finally:
            store.close()
        return 0
    if args.cmd == "serve":
        from .api import build_server
        store = open_store(args.db)
        server = build_server(store, args.host, args.port, args.token)
        print(f"swarm-lab on http://{args.host}:{server.server_address[1]} db={args.db}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            store.close()
        return 0
    if args.cmd == "demo":
        store = open_store(args.db)
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
