"""swarm-lab benchmark: tasks/sec и latency claim+complete.

SQLite:
    python scripts/bench.py --backend sqlite --tasks 200 --workers 8

PostgreSQL (нужен DSN):
    python scripts/bench.py --backend postgres --dsn postgresql://... --tasks 200 --workers 8
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return round(values[min(len(values) - 1, max(0, round((len(values) - 1) * q)))], 3)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=("sqlite", "postgres"), default="sqlite")
    ap.add_argument("--dsn", default="")
    ap.add_argument("--tasks", type=int, default=200)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--output", default="benchmarks/results.json")
    args = ap.parse_args(argv)
    from swarmlab.pg import PgSwarmStore
    from swarmlab.store import SwarmStore

    if args.backend == "postgres":
        if not args.dsn:
            print("--dsn is required for postgres", file=sys.stderr)
            return 2
        store = PgSwarmStore(args.dsn)
        worker_stores = [PgSwarmStore(args.dsn) for _ in range(max(1, args.workers))]
    else:
        store = SwarmStore(":memory:")
        worker_stores = [store for _ in range(max(1, args.workers))]
    agents = [f"bench-{i}" for i in range(max(1, args.workers))]
    for i, agent in enumerate(agents):
        worker_stores[i].register(agent, ["bench"])
    started = time.perf_counter()
    for i in range(max(1, args.tasks)):
        store.submit("bench", {"n": i}, priority=i % 3)
    barrier = threading.Barrier(len(agents))
    latencies: list[float] = []
    errors: list[BaseException] = []
    lock = threading.Lock()

    def worker(agent: str, worker_store) -> None:
        try:
            barrier.wait(timeout=10)
            while True:
                t0 = time.perf_counter()
                task = worker_store.claim(agent, "bench", lease_s=30)
                if not task:
                    return
                worker_store.complete(task["task_id"], agent, {"ok": 1}, fence=task["lease_epoch"])
                with lock:
                    latencies.append((time.perf_counter() - t0) * 1000.0)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(agent, worker_stores[i])) for i, agent in enumerate(agents)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    elapsed = max(1e-9, time.perf_counter() - started)
    result = {
        "backend": args.backend,
        "tasks": args.tasks,
        "workers": args.workers,
        "completed": len(latencies),
        "seconds": round(elapsed, 3),
        "tasks_per_sec": round(len(latencies) / elapsed, 1),
        "latency_ms": {
            "p50": pct(latencies, 0.50),
            "p95": pct(latencies, 0.95),
            "mean": round(statistics.mean(latencies), 3) if latencies else 0.0,
        },
        "errors": [str(e) for e in errors],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    store.close()
    for s in set(worker_stores):
        if s is not store:
            s.close()
    return 0 if len(latencies) == args.tasks and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
