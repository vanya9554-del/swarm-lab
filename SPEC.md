# SPEC — swarm-lab v6

## Объекты

- **Agent**: `agent_id`, `capabilities[]`, `endpoint`, `status`, `last_seen_at`, `meta`.
  Discovery — `GET /v1/agents?capability=&limit=`, TTL `SWARMLAB_AGENT_TTL`.
- **Task**: `task_id`, `capability`, `payload`, `priority`, `status`, `claimed_by`,
  `lease_until`, `lease_epoch`, `result`, `affinity_agent_id`, `dedup_key`,
  `expires_at`, `depends_on`, `attempts`, `max_attempts`, timestamps.
- **Event**: append-only `seq`, `type`, `payload`, `created_at`.

## Инварианты

1. Claim атомарный; один pending task — один worker.
2. `lease_epoch` инкрементится при claim; stale worker получает `STALE_LEASE`.
3. `dedup_key` уникален в рамках capability.
4. Backpressure: pending limit (`SWARMLAB_MAX_PENDING`) → 409/429.
5. Event stream — SSE (`/v1/stream`), `after=seq`, keepalive, PG LISTEN/NOTIFY.
6. **TTL**: `ttl_s` → `expires_at`; pending истекает при claim/expire.
7. **Dependencies**: `depends_on` — claim только после `completed` зависимости.
8. **Retry**: `attempts`/`max_attempts`; lease-expiry после лимита → `failed`.
9. **Lifecycle**: cancel/requeue; requeue только cancelled/failed.
10. **Auth**: bearer tokens + scopes; rate-limit (`Retry-After`), body limit.

## API

- Discovery: `GET /health`, `/ready`, `/metrics`, `/v1/version`, `/v1/capabilities`, `/v1/openapi`.
- Agents: `POST /v1/agents`, `GET /v1/agents`, `GET /v1/agents/{id}`,
  `DELETE /v1/agents/{id}`, `POST /v1/heartbeat`.
- Tasks: `POST /v1/tasks`, `GET /v1/tasks?status=&capability=&limit=`,
  `GET /v1/tasks/{id}`, `POST /v1/tasks/claim`,
  `POST /v1/tasks/{id}/complete|renew|cancel|requeue`.
- Events: `GET /v1/events`, `GET /v1/stream`.
- Batch: `POST /v1/batch` (register/submit/claim/complete/renew/cancel/requeue/deregister/expire/stats).
- Maintenance: `POST /v1/maintenance/expire`.
- MCP: `POST /mcp`, stdio `python -m swarmlab mcp`.

## Хранилища

- SQLite WAL (default) — один writer, RLock, миграции alter.
- PostgreSQL — multi-replica `FOR UPDATE SKIP LOCKED`, reconnect, `pg_notify`.

## Не цели

- UI, dashboard, human onboarding.
- Exactly-once side effects (только fencing/идемпотентность протокола).
- Распределённый брокер вне PG (Redis/NATS) — backlog.
