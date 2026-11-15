# Changelog — swarm-lab

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
