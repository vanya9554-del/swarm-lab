# Changelog — swarm-lab

## [5.9.0] — 2026-11-15

CI fix + SSE failure path.

### Исправлено
- CI: `URLError` (broken pipe) в large-body тесте на Linux.
- SSE listener failure; 103 теста.

## [5.8.0] — 2026-11-15

MCP runtime exception path.

### Добавлено
- tool runtime error test; 102 теста.

## [5.7.0] — 2026-11-15

Coverage 96%.

### Добавлено
- API backpressure, PG unavailable; coverage 96,0%, 102 теста.

## [5.6.0] — 2026-11-15

Manifest validator.

### Добавлено
- `scripts/validate_manifests.py` + test; 100 тестов.

## [5.5.0] — 2026-11-15

Stream/PG decode coverage.

### Добавлено
- SSE empty stream, PG invalid payload/result, guards; coverage 95,7%, 99 тестов.

## [5.4.0] — 2026-11-15

Harness isolation.

### Исправлено
- Night harness запускает только smoke-тесты (39), не конкурирует с полным suite; 96 тестов.

## [5.3.0] — 2026-11-15

MCP failure paths.

### Добавлено
- unknown tool, tool error, stdio parse error; 96 тестов.

## [5.2.0] — 2026-11-15

Configurable lease.

### Добавлено
- `SWARMLAB_LEASE_S` для claim (API/MCP/batch); 96 тестов.

## [5.1.0] — 2026-11-15

PG affinity/priority.

### Добавлено
- affinity/priority claim test; 95 тестов.

## [5.0.0] — 2026-11-15

Milestone 5.0: API contract.

### Добавлено
- ROUTES ↔ OpenAPI contract tests; 94 теста.

## [4.9.0] — 2026-11-15

Auth/rate edge coverage.

### Добавлено
- invalid `SWARMLAB_TOKENS`, DELETE 429; coverage 95,4%, 92 теста.

## [4.8.0] — 2026-11-15

README/current docs.

### Добавлено
- README синхронизирован с 4.x: TTL/deps/attempts/OpenAPI/gzip; 90 тестов.

## [4.7.0] — 2026-11-15

Coverage 95%.

### Добавлено
- invalid payload decode test; coverage 95,0%, 88 тестов.

## [4.6.0] — 2026-11-15

Configurable body limit.

### Добавлено
- `SWARMLAB_MAX_BODY`; body-limit test; 87 тестов.

## [4.5.0] — 2026-11-15

PG guards/backpressure.

### Добавлено
- PG backpressure + requeue/cancel guards; 86 тестов.

## [4.4.0] — 2026-11-15

DELETE auth coverage.

### Добавлено
- DELETE 401/404; 84 теста, coverage 94,6%.

## [4.3.0] — 2026-11-15

Schema migration coverage.

### Добавлено
- SQLite old-schema migration test; coverage 94,5%, 82 теста.

## [4.2.0] — 2026-11-15

Store guard coverage.

### Добавлено
- renew/complete/requeue guards; coverage 94,1%, 81 тест.

## [4.1.0] — 2026-11-15

Query coverage.

### Добавлено
- API filters + PG queries; 80 тестов.

## [4.0.0] — 2026-11-15

Milestone 4.0: OpenAPI discovery.

### Добавлено
- `GET /v1/openapi` (OpenAPI 3.1); 78 тестов.

## [3.9.0] — 2026-11-15

Health observability.

### Добавлено
- `/health`: version + uptime; 77 тестов.

## [3.8.0] — 2026-11-15

Bench re-validation.

### Добавлено
- HTTP 300/300, 586.7 tasks/s, p50 9.2 ms; attempts API/MCP tests; 76 тестов.

## [3.7.0] — 2026-11-15

Dead-letter attempts.

### Добавлено
- `max_attempts` на submit; lease expiry → failed после лимита; requeue сбрасывает attempts; SQLite/PG/API/MCP; 74 теста.

## [3.6.0] — 2026-11-15

Coverage 94%.

### Добавлено
- batch cancel/requeue/expire, empty body; 72 теста, coverage 94,0%.

## [3.5.0] — 2026-11-15

PG claim guards.

### Добавлено
- cancel/renew/complete guard tests; coverage 93,6%, 71 тест.

## [3.4.0] — 2026-11-15

PG edge paths.

### Добавлено
- expire/tasks/renew errors; coverage 93,4%, 70 тестов.

## [3.3.0] — 2026-11-15

PG edges/coverage.

### Добавлено
- PG heartbeat/complete/renew/requeue errors; coverage 93,1%, 69 тестов.

## [3.2.0] — 2026-11-15

Task dependencies.

### Добавлено
- `depends_on` на submit; claim только после completed зависимости; SQLite/PG/API/MCP; 68 тестов.

## [3.1.0] — 2026-11-15

Gzip responses.

### Добавлено
- Gzip для JSON-ответов ≥512 байт при `Accept-Encoding: gzip`; 65 тестов.

## [3.0.0] — 2026-11-15

Milestone 3.0: maintenance expiry.

### Добавлено
- `POST /v1/maintenance/expire`, MCP `swarm_expire`, batch `expire`.
- PG deregister test; 64 теста.

## [2.9.0] — 2026-11-15

Agent deregistration.

### Добавлено
- `DELETE /v1/agents/{agent_id}`, MCP `swarm_deregister`, batch deregister; 61 тест.

## [2.8.0] — 2026-11-15

Task TTL/expiry.

### Добавлено
- `ttl_s` на submit; pending → expired при claim; `expire()`; SQLite ALTER/PG column.
- 58 тестов.

## [2.7.0] — 2026-11-15

Requeue cancelled/failed tasks.

### Добавлено
- `POST /v1/tasks/{id}/requeue`, MCP `swarm_requeue`, batch requeue; 55 тестов.

## [2.6.0] — 2026-11-15

HTTP rate-limit headers.

### Добавлено
- `Retry-After: 1` и request-id на 429; 52 теста.

## [2.5.0] — 2026-11-15

Version/capabilities discovery.

### Добавлено
- `GET /v1/version`, `GET /v1/capabilities`; 52 теста.

## [2.4.0] — 2026-11-15

PG K8s HPA/cancel.

### Добавлено
- `deploy/k8s-postgres.yaml`: 2 replicas + HPA/PDB/Service, PG DSN.
- PG cancel test; 51 тест, coverage 93,1%.

## [2.3.0] — 2026-11-15

Task cancellation.

### Добавлено
- `POST /v1/tasks/{id}/cancel`, MCP `swarm_cancel`, batch `cancel`.
- Ownership guard, idempotent cancel; 50 тестов.

## [2.2.0] — 2026-11-15

Deploy/K8s + reconnect chaos.

### Добавлено
- PDB, NetworkPolicy, deploy README, `test_deploy`.
- `test_reconnect_under_load` (40 задач, connection close); 47 тестов.

## [2.1.0] — 2026-11-15

Coverage/edge paths.

### Добавлено
- Events import/wait edges, rate-limit POST, metrics-broken path; coverage 93,2%, 45 тестов.

## [2.0.0] — 2026-11-15

Milestone 2.0: task read API.

### Добавлено
- `GET /v1/tasks/{task_id}`; MCP `swarm_get_task`; 41 тест, coverage 92,4%.
- Batch renew, PG SSE, readiness — в 1.9.

## [1.9.0] — 2026-11-15

Batch renew, PG SSE/failure paths.

### Исправлено
- `/v1/batch` поддерживает `renew` (был unknown op).
- PG HTTP SSE test; coverage 92,4%, 39 тестов.

## [1.8.0] — 2026-11-15

Readiness/coverage.

### Добавлено
- `/ready` failure path, public probes, coverage **91,6%**, 36 тестов.
- Store/events/CLI branches.

## [1.7.0] — 2026-11-15

Readiness and probes.

### Добавлено
- `GET /ready` (DB readiness), public `/health`/`/ready`/`/metrics`.
- K8s probes → `/ready`; coverage 90,3%, 32 теста.

## [1.6.0] — 2026-11-15

Continuous harness + coverage 90%.

### Добавлено
- `scripts/night_harness.py`: health/soak каждые 5с, tests каждые 15мин, server watchdog.
- Coverage **90,4%**, 31 тест; MCP/CLI/API edge paths.
- Query/body validation errors.

## [1.5.0] — 2026-11-15

Concurrency fix.

### Исправлено
- SQLite `_one/_all` без lock → `InterfaceError` под 8 воркерами; все чтения под RLock.
- HTTP: 200/200, 726 tasks/s, p50 7.47 ms, p95 25.5 ms, 0 errors.
- Регрессия `SqliteConcurrencyTests`; 27 тестов.

## [1.4.0] — 2026-11-15

Transport/observability/coverage.

### Добавлено
- TCP_NODELAY, request_queue_size=128.
- Coverage **86%**, 26 тестов; MCP/stdio edge paths.
- Request-id и latency histogram; HTTP benchmark script.

## [1.3.0] — 2026-11-15

Observability/coverage.

### Добавлено
- `X-Request-Id`, latency histogram в `/metrics`.
- Coverage **80%**, 23 теста; API/MCP/PG edge paths.
- Reconnect/chaos подтверждены.

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
