# Changelog — swarm-lab

## [1.2.0] — 2026-11-15

Post-1.1 quality.

### Добавлено
- Token scopes/RBAC (`SWARMLAB_TOKENS`, 401/403), PG reconnect/retry.
- Quality gate: ruff 0, coverage 76%, 20 тестов, CI coverage step.
- `QUALITY.md`, CLI/error tests.

## [1.1.0] — 2026-11-15

Post-1.0 hardening.

### Добавлено
- PG LISTEN/NOTIFY SSE (без 50мс polling на PG).
- Backpressure `SWARMLAB_MAX_PENDING` → 429; rate limit по токену.
- Chaos: 3 replica/6 workers/100 tasks exactly-once.
- Compose (SQLite + PG profile), K8s manifests, DEPLOY.md.
- 15 тестов.

## [1.0.0] — 2026-11-15

Первый стабильный релиз.

### Добавлено
- SQLite engine: agents/discovery, task market, priority, affinity, dedup, lease/fence, events/stats.
- HTTP API: JSON, batch (1 RTT), SSE, bearer token, rate-limit, security headers, `/metrics`.
- MCP: tools/resources/prompts, stdio + HTTP `/mcp`.
- PostgreSQL: multi-replica atomic claim `FOR UPDATE SKIP LOCKED`, fencing, dedup.
- Benchmark/load/chaos: 5412 tasks/s (SQLite), PG 2-replica exactly-once.
- Docker, GitHub Actions CI, pyproject, MIT, SECURITY, ACCEPTANCE.

### Ограничения
- Нет UI by design; bearer auth без scopes; SSE polling.
