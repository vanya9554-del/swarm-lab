# PROGRESS — swarm-lab

## Сделано

- **S0 bootstrap**: README/SPEC/PLAN, `.gitignore`, git repo (`main`), 3 store tests.
- **S1 engine**: SQLite WAL store, agents/discovery, task market, priority, affinity, dedup,
  claim/lease, `lease_epoch`, fence, stale → `STALE_LEASE`, idempotent complete, events/stats.
- **S2 API**: stdlib HTTP (`/v1/agents`, `/v1/heartbeat`, `/v1/tasks`, `/v1/tasks/claim`,
  `/v1/tasks/{id}/complete|renew`, `/v1/events`, `/v1/stream`, `/v1/batch`, `/v1/stats`),
  SSE, batch, bearer token, CLI `serve`; 5 tests.
- **S3 MCP**: tools/resources/prompts, HTTP `/mcp`, stdio `python -m swarmlab mcp`; 7 tests total.
- **S4 PostgreSQL**: `swarmlab/pg.py`, `open_store(dsn)`, multi-replica claim, tests 9 total.
- **S5 load/chaos**: `scripts/bench.py`, `BENCH.md`, 50-task PG multi-replica/stale test; **10 tests**; SQLite 5412 tasks/s, p50 1.09ms/p95 2.92ms.
- **S6 hardening**: bearer token, rate-limit, body limit, security headers, `/metrics`, Dockerfile, CI, pyproject, MIT, SECURITY; **12 tests**.
- **S7 release 1.0**: ACCEPTANCE, CHANGELOG, RELEASE_NOTES, SBOM/checksums; v1.0.0.
- **S8**: PG `pg_notify` + `PgEventStream`; SSE ждёт NOTIFY на PG.
- **S9**: pending backpressure (`SWARMLAB_MAX_PENDING` → 429), rate-limit per token; **14 tests**.

## В работе

- S10 chaos/reconnect; S11 compose/K8s; S12 release 1.1.
- S4 PostgreSQL multi-replica (optional deps).
- S5 load/chaos benchmark.

## Осталось

- S3–S7; Docker/CI; release 1.0; SBOM/checksum.
- GitHub remote/push — нет auth; внешний блокер.

## Допущения

- stdlib-only; SQLite default; PG — optional.
- Нет UI by design.
- Token auth — простой bearer; scopes/rate-limit — backlog.

## Проверки

```powershell
Set-Location swarm-lab
python -m unittest discover -s tests -v
python -m swarmlab demo
python -m swarmlab serve --port 8788
```

## Дефекты/фиксы

- Store fence проверяется до claimed_by → stale worker получает `STALE_LEASE` (не FORBIDDEN).
- Heartbeat выделен в `SwarmStore.heartbeat` (не upsert через discover).
