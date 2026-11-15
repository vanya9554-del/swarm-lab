"""HTTP benchmark: concurrent claim/complete через API.

    python scripts/http_bench.py --url http://127.0.0.1:8788 --tasks 200 --workers 8
"""
from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
import urllib.error
import urllib.request


def _call(method: str, url: str, body: dict | None = None, timeout: float = 5.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read() or b"{}")
            return r.status, payload, (time.perf_counter() - t0) * 1000.0
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), (time.perf_counter() - t0) * 1000.0


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return round(values[min(len(values) - 1, max(0, round((len(values) - 1) * q)))], 3)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8788")
    ap.add_argument("--tasks", type=int, default=200)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--output", default="benchmarks/http_results.json")
    args = ap.parse_args(argv)
    base = args.url.rstrip("/")
    suffix = str(int(time.time() * 1000))
    capability = f"http-{suffix}"
    agents = [f"http-{suffix}-{i}" for i in range(max(1, args.workers))]
    for agent in agents:
        _call("POST", base + "/v1/agents", {"agent_id": agent, "capabilities": [capability]})
    for i in range(max(1, args.tasks)):
        _call("POST", base + "/v1/tasks", {"capability": capability, "payload": {"n": i}})
    latencies: list[float] = []
    errors: list[str] = []
    lock = threading.Lock()
    barrier = threading.Barrier(len(agents))

    def worker(agent: str) -> None:
        barrier.wait(timeout=10)
        while True:
            status, body, claim_ms = _call("POST", base + "/v1/tasks/claim", {"agent_id": agent, "capability": capability})
            task = (body.get("data") or {}) if status == 200 else {}
            if not task or not task.get("task_id"):
                return
            status, body, complete_ms = _call("POST", base + f"/v1/tasks/{task['task_id']}/complete", {
                "agent_id": agent, "fence": task.get("lease_epoch"), "result": {"ok": 1},
            })
            if status != 200:
                with lock:
                    errors.append(f"{status}:{body}")
                return
            with lock:
                latencies.append(claim_ms + complete_ms)

    started = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(a,)) for a in agents]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    elapsed = max(1e-9, time.perf_counter() - started)
    result = {
        "tasks": args.tasks,
        "workers": args.workers,
        "completed": len(latencies),
        "seconds": round(elapsed, 3),
        "tasks_per_sec": round(len(latencies) / elapsed, 1),
        "latency_ms": {"p50": pct(latencies, 0.5), "p95": pct(latencies, 0.95), "mean": round(statistics.mean(latencies), 3) if latencies else 0},
        "errors": errors[:10],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    from pathlib import Path
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if len(latencies) == args.tasks and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
