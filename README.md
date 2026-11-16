# swarm-lab

Agent-native swarm runtime и benchmark. **Без UI**: только HTTP/JSON, batch, SSE, MCP и CLI.
Reference implementation для быстрого обмена задачами, знаниями и событиями между агентами.

## Принципы

- Агент — первый клиент: минимум RTT, batch, SSE, gzip, компактные ответы.
- Никакого SPA/человеческого UI в критическом пути.
- SQLite по умолчанию; PostgreSQL — для multi-replica.
- Everything is measured: latency/throughput/lease/fencing/chaos.

## Возможности

- **Task market**: priority, affinity, dedup, lease/fencing (`lease_epoch`), backpressure.
- **TTL/expiry**: `ttl_s`, `expire`, maintenance endpoint.
- **Dependencies**: `depends_on` — claim только после completed.
- **Retry**: `attempts`/`max_attempts` → dead-letter `failed`; `requeue`.
- **Lifecycle**: cancel, requeue, get task by id.
- **PostgreSQL**: `FOR UPDATE SKIP LOCKED`, reconnect, `LISTEN/NOTIFY` SSE, multi-replica.
- **MCP 2024-11-05**: tools/resources/prompts over stdio и HTTP `/mcp`.
- **Observability**: Prometheus `/metrics`, `/health` (version/uptime), `/ready`, request-id, latency histogram.
- **Discovery**: `/v1/capabilities`, `/v1/version`, OpenAPI 3.1 `/v1/openapi`.
- **Hardening**: bearer tokens/scopes, rate limit + `Retry-After`, body limit, security headers.
- **Transport**: HTTP/1.1, keep-alive, `TCP_NODELAY`, gzip, `request_queue_size=128`.
- **Deploy**: Docker, compose (SQLite + PG profile), K8s (SQLite/PDB/NetworkPolicy, PG/HPA).

## Быстрый старт

```bash
python -m unittest discover -s tests
python -m swarmlab --help
python -m swarmlab serve --port 8788              # SQLite
python -m swarmlab serve --db postgresql://...   # PG multi-replica
python -m swarmlab mcp            # MCP stdio
# MCP HTTP: POST /mcp (initialize/tools/list/tools/call/resources/prompts)
curl -sS -X POST localhost:8788/v1/agents -H 'Content-Type: application/json' \
  -d '{"agent_id":"a1","capabilities":["search"]}'
curl -sS -X POST localhost:8788/v1/tasks -H 'Content-Type: application/json' \
  -d '{"capability":"search","payload":{"q":"x"},"ttl_s":60,"max_attempts":3}'
```

## Benchmark

```bash
python scripts/bench.py --backend sqlite --tasks 200 --workers 8
python scripts/http_bench.py --tasks 300 --workers 8
```

- SQLite engine: **5412 tasks/s**, p50 **1.09 ms** (`BENCH.md`).
- HTTP: **300/300**, **586,7 tasks/s**, p50 **9,2 ms**, p95 **31,5 ms**, 0 errors (`HTTP_BENCH.md`).

## Docker

```bash
docker build -t swarm-lab .
docker run -p 8788:8788 -e SWARMLAB_TOKEN=secret swarm-lab
```

## Статус

**v10.3.0** — 172 теста, coverage **95,0%**, ruff 0; релиз-артефакты в `release/v4.7.0/`.
План — `PLAN.md`, протокол — `SPEC.md`, качество — `QUALITY.md`,
автономный runbook — `../NIGHT_SHIFT.md`.

## Python client

```python
from swarmlab.client import SwarmClient

with SwarmClient("http://127.0.0.1:8788", token="...") as c:
    c.register("agent-1", ["echo"])
    task = c.submit("echo", {"msg": "hi"})
    claimed = c.claim("agent-1", "echo")
    c.complete(claimed["task_id"], "agent-1", {"ok": True}, claimed["lease_epoch"])
```
