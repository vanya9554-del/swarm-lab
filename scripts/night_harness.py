"""Continuous night harness: держит server тёплым и гоняет soak каждую секунду.

Работает независимо от model-turn'ов; пишет JSONL, перезапускает server при падении,
периодически запускает unittest (без остановки цикла). До 16.11.2026 12:00.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8788"
PYTHON = sys.executable
LOG = ROOT / "data" / "night_harness.jsonl"
SERVER_LOG = ROOT / "data" / "night_server.log"


def now_utc() -> str:
    return dt.datetime.now(dt.UTC).isoformat()


def call(method: str, path: str, body: dict | None = None, timeout: float = 5.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}"), (time.perf_counter() - t0) * 1000
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), (time.perf_counter() - t0) * 1000
    except Exception as exc:  # noqa: BLE001
        return 0, {"exc": repr(exc)}, (time.perf_counter() - t0) * 1000


def log(record: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": now_utc(), **record}, ensure_ascii=False) + "\n")


def ensure_server() -> bool:
    status, _, _ = call("GET", "/health", timeout=2)
    if status == 200:
        return True
    log({"event": "server_restart"})
    SERVER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SERVER_LOG.open("a", encoding="utf-8") as out:
        subprocess.Popen(
            [PYTHON, "-m", "swarmlab", "serve", "--db", "data/swarm.db", "--port", "8788"],
            cwd=str(ROOT), stdout=out, stderr=out, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    for _ in range(20):
        time.sleep(0.5)
        if call("GET", "/health", timeout=1)[0] == 200:
            log({"event": "server_started"})
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", default="2026-11-16T12:00:00+03:00")
    ap.add_argument("--tick", type=float, default=1.0)
    args = ap.parse_args(argv)
    until = dt.datetime.fromisoformat(args.until)
    agents = [f"night-{i}" for i in range(4)]
    for agent in agents:
        call("POST", "/v1/agents", {"agent_id": agent, "capabilities": ["night"]})
    log({"event": "start", "until": until.isoformat(), "pid": os.getpid()})
    last_health = 0.0
    last_task = 0.0
    last_test = 0.0
    tasks = 0
    errors = 0
    while dt.datetime.now(until.tzinfo) < until:
        started = time.time()
        try:
            if started - last_health >= 5:
                ok = ensure_server()
                last_health = started
                if not ok:
                    errors += 1
                    log({"event": "server_down", "errors": errors})
            if started - last_task >= 5:
                last_task = started
                cap = f"night-{int(started)}"
                for agent in agents:
                    call("POST", "/v1/agents", {"agent_id": agent, "capabilities": [cap]})
                status, body, submit_ms = call("POST", "/v1/tasks", {"capability": cap, "payload": {"t": started}})
                if status == 200:
                    task_id = body["data"]["task_id"]
                    status, body, claim_ms = call("POST", "/v1/tasks/claim", {"agent_id": agents[tasks % len(agents)], "capability": cap})
                    if status == 200 and body.get("data"):
                        task = body["data"]
                        status2, _, complete_ms = call("POST", f"/v1/tasks/{task_id}/complete", {
                            "agent_id": agents[tasks % len(agents)], "fence": task.get("lease_epoch"), "result": {"ok": 1},
                        })
                        if status2 == 200:
                            tasks += 1
                            if tasks <= 3 or tasks % 12 == 0:
                                log({"event": "tick", "tasks": tasks, "latency_ms": round(submit_ms + claim_ms + complete_ms, 3), "errors": errors})
                        else:
                            errors += 1
                            log({"event": "complete_error", "status": status2})
            if started - last_test >= 900:
                last_test = started
                proc = subprocess.run(
                    [PYTHON, "-m", "unittest", "discover", "-s", "tests", "-q"],
                    check=False, cwd=str(ROOT), capture_output=True, text=True, timeout=300,
                )
                log({"event": "tests", "returncode": proc.returncode, "tail": (proc.stderr or proc.stdout)[-500:]})
        except Exception as exc:  # noqa: BLE001
            errors += 1
            log({"event": "loop_error", "error": repr(exc), "errors": errors})
        elapsed = time.time() - started
        time.sleep(max(0.05, args.tick - elapsed))
    log({"event": "stop", "tasks": tasks, "errors": errors})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
