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
- **S10 chaos**: 3 реплики, 6 воркеров, 100 задач, exactly-once; `CHAOS.md`.
- **S11 deploy**: `docker-compose.yml`, `deploy/k8s.yaml`, `DEPLOY.md`; **15 tests**.
- **S13**: `SWARMLAB_TOKENS` scopes read/write (403/401), PG reconnect/retry; **17 tests**.
- **S14**: coverage 76%, ruff 0, CI quality, 20 tests.
- **S15**: release 1.2.0.
- **S16**: request-id/latency, coverage 80%, 23 tests, release 1.3.0.
- **S17**: transport tuning, coverage 86%, 26 tests, release 1.4.0.
- **S18**: SQLite read-lock fix; HTTP 200/200 726 tasks/s; 27 tests; release 1.5.0.
- **S19**: night harness, coverage 90,4%, 31 tests; release 1.6.0.
- **S20**: `/ready`, public probes, coverage 90,3%, 32 tests; release 1.7.0.
- **S21**: readiness failure, 36 tests, coverage 91,6%; release 1.8.0.
- **S22**: batch renew, PG SSE, coverage 92,4%, 39 tests; release 1.9.0.
- **S23**: GET task by id, MCP get_task, 41 tests; release 2.0.0.
- **S24**: edges/rate/metrics, 45 tests, coverage 93,2%; release 2.1.0.
- **S25**: PDB/NetworkPolicy, reconnect load, 47 tests; release 2.2.0.
- **S26**: task cancel, 50 tests; release 2.3.0.
- **S27**: PG K8s HPA/PDB, PG cancel, 51 тест; release 2.4.0.
- **S28**: version/capabilities, 52 теста; release 2.5.0.
- **S29**: Retry-After/rate headers; release 2.6.0.
- **S30**: requeue cancelled/failed, 55 тестов; release 2.7.0.
- **S31**: task TTL/expiry, 58 тестов; release 2.8.0.
- **S32**: agent deregistration, 61 тест; release 2.9.0.
- **S33**: maintenance expire, 64 теста; release 3.0.0.
- **S34**: gzip compression, 65 тестов; release 3.1.0.
- **S35**: task dependencies, 68 тестов; release 3.2.0.
- **S36**: PG edge coverage, 69 тестов; release 3.3.0.
- **S37**: PG edge paths, coverage 93,4%, 70 тестов; release 3.4.0.
- **S38**: PG claim guards, coverage 93,6%, 71 тест; release 3.5.0.
- **S39**: batch maintenance, coverage 94,0%, 72 теста; release 3.6.0.
- **S40**: dead-letter attempts, 74 теста; release 3.7.0.
- **S41**: HTTP bench 300/300, 76 тестов; release 3.8.0.
- **S42**: health version/uptime, 77 тестов; release 3.9.0.
- **S43**: OpenAPI 3.1, 78 тестов; release 4.0.0.
- **S44**: query coverage, 80 тестов; release 4.1.0.
- **S45**: store guards, coverage 94,1%, 81 тест; release 4.2.0.
- **S46**: schema migration, coverage 94,5%, 82 теста; release 4.3.0.
- **S47**: DELETE auth coverage, 84 теста; release 4.4.0.
- **S48**: PG guards/backpressure, 86 тестов; release 4.5.0.
- **S49**: SWARMLAB_MAX_BODY, 87 тестов; release 4.6.0.
- **S12 release 1.1**: PG NOTIFY/backpressure/chaos/deploy, tag v1.1.0; GitHub push.

## В работе

- Post-5.10: live K8s, external audit, chaos.
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

- **Night harness**: `scripts/night_harness.py` запущен detached; JSONL `data/night_harness.jsonl`; health/soak каждые 5с, тесты каждые 15мин.

- **S96**: GitHub Release v6.9.0 + assets (checksums, sbom, notes).

- **S97**: security headers, milestone 7.0.0.

- **S98**: engine 3354.6 tasks/s; release 7.1.0.

- **S99**: HEAD support, 141 тест; release 7.2.0.

- **S100**: 10×500 soak, 5000/5000, 0 errors; milestone 8.0.0.

- **S101**: data retention prune, 145 тестов; release 8.1.0.

- **S102**: final report refresh (v8.1, 145 тестов, 5000 soak).

- **S103**: CI green; harness 7956 tasks, 0 errors.

- **S105**: task event history, 149 тестов; release 8.2.0.

- **S106**: post-change 5000/5000 soak; release 8.3.0.

- **S107**: final verification; 149 тестов, 100%, CI green, harness 8676 tasks/0 errors.

- **S110**: pre-return final check; 149 тестов, 100%, CI green.

- **S111**: shift complete; 149 тестов, 100%, CI green, server/harness stable.

- **S112**: Helm chart + Docker/Helm CI, milestone 9.0.0.

- **S113**: observability (histogram, JSON logs, alerts, Grafana, SLO); release 9.1.0.

- **S114**: JWT security + Helm wiring; release 9.2.0.

- **S115**: backup/restore, GHCR CD, ArgoCD, kubeconform, fuzz; release 9.3.0.

- **S116**: Trivy/kubeconform/GHCR/ArgoCD/RUNBOOK/backup; release 9.4.0.

- **S117**: schema version/migrations, rolling upgrade; release 9.5.0.

- **S118**: RS256 JWT/OIDC, 158 тестов; release 9.6.0.

- **S119**: PG chaos 500/500; release 9.7.0.

- **S120**: Python client SDK, 162 теста; release 9.8.0.

- **S121**: HTTP PG multi-replica chaos 100/100; release 9.9.0.

- **S122**: milestone 10.0, acceptance checklist; release 10.0.0.

- **S123**: audit log, schema v11, 170 тестов; release 10.1.0.

- **S124**: audit retention prune; release 10.2.0.

- **S125**: audit filters; release 10.3.0.

- **S126**: default-deny NetworkPolicy; release 10.4.0.

- **S127**: pip-audit CI; release 10.5.0.

- **S128**: audit metrics; release 10.6.0.

- **S129**: live kind validation in CI, maxBody fix; release 10.7.0.

- **S130**: OIDC JWKS discovery, 174 теста; release 10.8.0.

- **S131**: live kind, OIDC JWKS, S3 backup, bandit; milestone 11.0.0.

- **S132**: DAST ZAP, cosign, multi-arch, SBOM; release 11.1.0.

- **S133**: live TLS kind, maintenance image/Helm S3; release 11.2.0.

- **S134**: runtime psycopg/crypto fix, live PG/HPA kind; release 11.3.0.

- **S135**: live backup/restore + S3 CronJob; release 11.4.0.
