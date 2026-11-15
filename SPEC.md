# SPEC — swarm-lab v0.1

## Объекты

- **Agent**: `agent_id`, `capabilities[]`, `endpoint`, `status`, `last_seen`.
- **Task**: `task_id`, `capability`, `payload`, `priority`, `status`, `claimed_by`,
  `lease_until`, `lease_epoch`, `fence`, `result`, timestamps.
- **Event**: append-only `seq`, `type`, `payload`, `created_at`.

## Инварианты

1. Claim атомарный; один pending task — один worker.
2. `lease_epoch` инкрементится при claim; stale worker получает `STALE_LEASE`.
3. `dedup_key` уникален в рамках capability.
4. Backpressure: pending limit → 429.
5. Event stream — SSE; после reconnect `after=seq`.

## API (целевой)

`POST /v1/agents`, `GET /v1/agents`, `POST /v1/heartbeat`,
`POST /v1/tasks`, `POST /v1/tasks/claim`, `POST /v1/tasks/{id}/complete`,
`POST /v1/tasks/{id}/renew`, `GET /v1/tasks`, `GET /v1/events`,
`GET /v1/stream`, `POST /v1/batch`, `GET /v1/stats`.

## Не цели

- UI, dashboard, human onboarding.
- Exactly-once side effects (только fencing/идемпотентность протокола).
- Распределённый брокер вне PG (Redis/NATS) — backlog.
