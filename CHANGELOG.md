# Changelog — swarm-lab

## [11.18.0] — 2026-11-19

Coordination roles.

### Добавлено
- `POST /v1/roles/claim|renew|release`, `GET /v1/roles` — lease-based roles/election.
- 197 тестов, 100% coverage.

## [11.17.0] — 2026-11-19

Shared artifacts.

### Добавлено
- `POST/GET/DELETE /v1/artifacts` — общая память агентов, версии, каналы.
- 194 теста, 100% coverage.

## [11.16.0] — 2026-11-19

Channel membership.

### Добавлено
- `POST /v1/channels/{c}/join|leave`, `GET /v1/channels/{c}/members`.
- Auto-join при отправке в канал; роли member.
- 191 тест, 100% coverage.

## [11.15.0] — 2026-11-19

Message SSE.

### Добавлено
- `GET /v1/messages/stream` — SSE для inbox/каналов, keepalive, disconnect-safe.
- 188 тестов, 100% coverage.

## [11.14.0] — 2026-11-19

Agent messaging.

### Добавлено
- `POST/GET /v1/messages`, channels, `POST /v1/messages/{id}/read`.
- Per-agent token → agent identity; inbox/channel polling.
- 184 теста, 100% coverage.

## [11.13.0] — 2026-11-19

Agent self-onboarding.

### Добавлено
- Public `POST /v1/agents/register` с join code; выпуск per-agent токенов.
- Per-agent tokens в SQLite/PG, revoke при deregister; dynamic auth.
- 181 тест, 100% coverage.

## [11.12.0] — 2026-11-19

PG migration safety.

### Исправлено
- Параллельный старт реплик мог давать deadlock на DDL; добавлен advisory lock.
- 177 тестов, 100% coverage.

## [11.11.0] — 2026-11-19

English publication + agent discovery.

### Добавлено
- English dashboard/README.
- `/llms.txt`, `/agents.json`, `/.well-known/ai-plugin.json`, `/robots.txt`, `/sitemap.xml`.
- 177 тестов, 100% coverage.

## [11.10.0] — 2026-11-18

Docker DB env fix (actual).

### Исправлено
- CMD теперь читает `SWARMLAB_DB` и `$PORT`; Render/PaaS используют PostgreSQL.
- 176 тестов, 100% coverage.

## [11.9.0] — 2026-11-18

Container DB env fix.

### Исправлено
- Docker CMD игнорировал `SWARMLAB_DB`; Render/PaaS не переключались на Postgres.
- 176 тестов, 100% coverage.

## [11.8.0] — 2026-11-18

Simple deploy path.

### Добавлено
- `START_HERE.md`: Render-деплой без инженерных знаний.
- Контейнер слушает `$PORT` (совместимость с Render/PaaS).
- 176 тестов, 100% coverage.

## [11.7.0] — 2026-11-18

Clickable dashboard + handoff docs.

### Добавлено
- `GET /` и `/dashboard`: HTML-панель со ссылками на API/GitHub/Cloud/KMS/пентест.
- `PRODUCTION.md`, `PENTEST.md`.
- 176 тестов, 100% coverage.

## [11.6.0] — 2026-11-18

Root discovery endpoint.

### Добавлено
- `GET /` — JSON с версией и ссылками на endpoints (раньше был 404).
- 175 тестов, 100% coverage.

## [11.5.0] — 2026-11-18

Vault/ESO external secrets.

### Добавлено
- live kind: HashiCorp Vault (dev) + External Secrets Operator; ExternalSecret → secret для auth.
- CI 12 jobs: + kind-vault; все зелёные.
- 174 теста, 100% coverage.

## [11.4.0] — 2026-11-18

Live backup/S3 drill.

### Добавлено
- kind CI: local-path PVC, backup CronJob, restore verification (SQLite).
- kind CI: moto S3, Helm `backup.s3`, maintenance image Job, проверка объекта.
- 11 CI jobs green; 174 теста, 100% coverage.

## [11.3.0] — 2026-11-18

Live PG/HPA.

### Исправлено
- Runtime-образ не содержал `psycopg`/`cryptography`: PostgreSQL и RS256 в контейнере не работали. Добавлены зависимости.

### Добавлено
- CI `kind-pg`: live PostgreSQL, HPA (metrics-server), 2 реплики, smoke.
- 174 теста, 9 CI jobs green.

## [11.2.0] — 2026-11-18

TLS ingress + S3 maintenance.

### Добавлено
- Live kind TLS: ingress-nginx + cert-manager + HTTPS smoke.
- `Dockerfile.maintenance` (boto3), Helm `backup.s3` CronJob.
- Release workflow собирает/подписывает maintenance-образ.
- 174 теста, CI green.

## [11.1.0] — 2026-11-16

Supply chain + DAST.

### Добавлено
- OWASP ZAP baseline DAST в CI (0 FAIL, отчёт artifact).
- Multi-arch образ (amd64/arm64), provenance, **cosign keyless** подпись.
- SBOM (Syft SPDX) в release workflow.
- 174 теста, 100% coverage.

## [11.0.0] — 2026-11-16

Milestone 11.0: production closures.

### Добавлено
- Live Kubernetes (kind) в CI: Helm install, server-side dry-run, smoke, rolling upgrade.
- OIDC JWKS discovery (`SWARMLAB_JWT_JWKS_URL`), cache/kid rotation.
- S3-compatible backup (`scripts/backup_s3.py`) + CI moto S3.
- Bandit SAST в CI; fix maxBody integer rendering.
- 174 теста, 100% coverage, CI green (7 jobs).

## [10.8.0] — 2026-11-16

OIDC JWKS discovery.

### Добавлено
- `SWARMLAB_JWT_JWKS_URL`: кэш 5 мин, выбор по `kid`, RS256.
- Helm `auth.jwtJwksUrl`; 174 теста, 100% coverage.

## [10.7.0] — 2026-11-16

Live kind cluster validation.

### Добавлено
- CI job `kind`: реальный Kubernetes, Helm install, server-side dry-run, smoke, rolling upgrade.
- Fix: `SWARMLAB_MAX_BODY` рендерится как integer (не float scientific).
- 173 теста, CI green.

## [10.6.0] — 2026-11-16

Audit metrics.

### Добавлено
- `stats.audit`, `swarmlab_audit_entries`; 173 теста, 100% coverage.

## [10.5.0] — 2026-11-16

Dependency audit.

### Добавлено
- CI job `pip-audit` для Python-зависимостей; 172 теста.

## [10.4.0] — 2026-11-16

NetworkPolicy hardening.

### Добавлено
- default-deny ingress (same-namespace only); `allowAllIngress` для отладки.
- 172 теста, CI green.

## [10.3.0] — 2026-11-16

Audit filters.

### Добавлено
- `GET /v1/audit?action=&actor=`; MCP args; 172 теста, 100% coverage.

## [10.2.0] — 2026-11-16

Audit retention.

### Добавлено
- `prune` удаляет старые audit-записи; 170 тестов, 100% coverage.

## [10.1.0] — 2026-11-16

Audit log.

### Добавлено
- `audit` table (SQLite/PG): auth denied/forbidden, mutations; `/v1/audit`, MCP `swarm_audit`.
- Schema v11; 170 тестов, 100% coverage.

## [10.0.0] — 2026-11-16

Milestone 10.0: production-ready.

### Добавлено
- Schema v10, acceptance checklist, final production infra.
- 163 теста, 100% coverage, CI/CD/GHCR/ArgoCD/observability/security.

## [9.9.0] — 2026-11-16

HTTP multi-replica chaos.

### Добавлено
- 2 API-реплики на общем PG: 100/100 exactly-once; 163 теста.

## [9.8.0] — 2026-11-16

Python client SDK.

### Добавлено
- `swarmlab.client.SwarmClient`: agents/tasks/events/stream, errors, context manager.
- 162 теста, 100% coverage.

## [9.7.0] — 2026-11-16

PG chaos 500.

### Добавлено
- 3 replicas/6 workers/500 tasks exactly-once; 158 тестов.

## [9.6.0] — 2026-11-16

OIDC RS256 JWT.

### Добавлено
- RS256 verification via `SWARMLAB_JWT_PUBLIC_KEY`; optional `cryptography` (`[oidc]`).
- Helm `jwtPublicKey`; 158 тестов, 100% coverage.

## [9.5.0] — 2026-11-16

Schema versioning/migrations.

### Добавлено
- `schema_version` (SQLite/PG), PG additive migrations; rolling upgrade docs.
- 157 тестов, 100% coverage.

## [9.4.0] — 2026-11-16

Production infra hardening.

### Добавлено
- Trivy image scan, kubeconform rendered manifests, GHCR release workflow.
- ArgoCD staging/prod, RUNBOOK, backup/restore scripts + test.
- 155 тестов, 100% coverage.

## [9.3.0] — 2026-11-16

Backup/restore + CD.

### Добавлено
- `scripts/backup.py`/`restore.py` с integrity check и restore test.
- `release.yml`: Docker build/push GHCR по git tag.
- ArgoCD staging/prod applications; kubeconform в CI.
- Fuzz/property test; 155 тестов, 100% coverage.

## [9.2.0] — 2026-11-16

JWT security.

### Добавлено
- HS256 JWT auth, `iss`/`aud`/`exp`/`nbf`, scopes; Helm wiring.
- SECURITY.md/пентест-чеклист; 152 теста, 100% coverage.

## [9.1.0] — 2026-11-16

Observability.

### Добавлено
- HTTP latency histogram в `/metrics`; JSON access logs (`SWARMLAB_LOG_FORMAT=json`).
- PrometheusRule, Grafana dashboard, SLO/error budget; Helm `prometheusRule`.
- 151 тест, 100% coverage.

## [9.0.0] — 2026-11-16

Milestone 9.0: production deployment.

### Добавлено
- Helm chart (`deploy/helm/swarmlab`): SQLite/PG, ingress/TLS, HPA, PDB, NetworkPolicy, ServiceMonitor, backup CronJob.
- CI jobs: `docker build` + `helm lint/template` (SQLite/PG).
- Deploy README, validator checks Helm/CI; 149 тестов, 100% coverage.

## [8.3.0] — 2026-11-16

Post-change soak.

### Добавлено
- 10×500/8 = 5000/5000, 0 errors; 149 тестов.

## [8.2.0] — 2026-11-16

Task event history.

### Добавлено
- `GET /v1/tasks/{id}/events`, MCP `swarm_task_events`; 149 тестов.

## [8.1.0] — 2026-11-16

Data retention prune.

### Добавлено
- `POST /v1/maintenance/prune`, MCP `swarm_prune`; 145 тестов.

## [8.0.0] — 2026-11-16

Milestone 8.0: soak stability.

### Добавлено
- 10×500/8 = **5000/5000**, 0 errors; 141 тест, 100% coverage.

## [7.2.0] — 2026-11-16

HEAD support.

### Добавлено
- `HEAD` для GET endpoints (без body), stream-заголовки; 141 тест.

## [7.1.0] — 2026-11-16

Engine benchmark.

### Добавлено
- SQLite 1000/8: 3354.6 tasks/s, p50 1.987 ms; 140 тестов.

## [7.0.0] — 2026-11-16

Milestone 7.0: security headers.

### Добавлено
- X-Frame-Options, Permissions-Policy, CSP (default-src none); 140 тестов.

## [6.9.0] — 2026-11-16

WAL checkpoint/vacuum.

### Добавлено
- `POST /v1/maintenance/vacuum`, MCP `swarm_vacuum`; 140 тестов.

## [6.8.0] — 2026-11-16

Readiness integrity.

### Добавлено
- `/ready` включает `quick_check` (SQLite) / `SELECT 1` (PG); 136 тестов.

## [6.7.0] — 2026-11-16

SQLite tuning.

### Добавлено
- busy_timeout 5s, cache 20MB, temp_store MEMORY; 500/500, 499.7 tasks/s.

## [6.6.0] — 2026-11-16

Final report.

### Добавлено
- `FINAL_REPORT.md`: итоги, метрики, блокеры, рекомендации.

## [6.5.0] — 2026-11-16

SPEC v6.

### Добавлено
- SPEC синхронизирован: TTL/deps/attempts/lifecycle/API/MCP/PG; 134 теста.

## [6.4.0] — 2026-11-16

TCP keepalive.

### Добавлено
- `SO_KEEPALIVE` на server socket; 134 теста, 100% coverage.

## [6.3.0] — 2026-11-16

Graceful SIGTERM.

### Добавлено
- SIGTERM → server.shutdown для K8s/Docker; 133 теста.

## [6.2.0] — 2026-11-16

Chaos validation.

### Добавлено
- 4/4 chaos/load (3 replicas, reconnect, exactly-once); 132 теста.

## [6.1.0] — 2026-11-16

2000-task soak.

### Добавлено
- HTTP 2000/2000, 529.7 tasks/s, p50 24.7 ms; 132 теста, 100% coverage.

## [6.0.0] — 2026-11-16

Milestone 6.0: K8s lifecycle hardening.

### Добавлено
- startupProbe, terminationGracePeriodSeconds; image 5.31.0; validator обновлён.

## [5.31.0] — 2026-11-16

Coverage 100%.

### Добавлено
- MCP value error, PG cancel missing; unreachable except удалён; **100% coverage**, 132 теста.

## [5.30.0] — 2026-11-16

Test suite 130.

### Добавлено
- MCP call-error/PG requeue tests; 130 тестов.

## [5.29.0] — 2026-11-16

Coverage 99.7%.

### Добавлено
- CLI runpy, metrics statuses, PG requeue; coverage 99,7%, 128 тестов.

## [5.28.0] — 2026-11-16

Dead code cleanup.

### Исправлено
- удалён dead POST `/v1/agents/{id}` branch; coverage 99,5%.

## [5.27.0] — 2026-11-16

Coverage 99%.

### Добавлено
- claim rollback/exception, PG notify failure; store 100%, total 99,1%, 125 тестов.

## [5.26.0] — 2026-11-16

Renew stale coverage.

### Добавлено
- renew stale/missing; coverage 98,7%, 122 теста.

## [5.25.0] — 2026-11-16

Connect retry failure.

### Добавлено
- PG connect attempts failure; coverage 98,6%, 121 тест.

## [5.24.0] — 2026-11-16

Coverage 98%.

### Добавлено
- store stale/event decode, PG env/complete edges; coverage 98,1%, 120 тестов.

## [5.23.0] — 2026-11-16

Invalid backpressure env.

### Добавлено
- `SWARMLAB_MAX_PENDING=bad` → 0; coverage 97,5%, 118 тестов.

## [5.22.0] — 2026-11-16

Soak validation.

### Добавлено
- 1000/1000 HTTP tasks, 529 tasks/s, p50 9.3 ms; 117 тестов.

## [5.21.0] — 2026-11-16

PG filter/TTL coverage.

### Добавлено
- PG capability filter + agent TTL; coverage 97,4%, 117 тестов.

## [5.20.0] — 2026-11-16

Task capability filter.

### Добавлено
- `GET /v1/tasks?capability=`; SQLite/PG; 116 тестов.

## [5.19.0] — 2026-11-16

MCP stdio/error coverage.

### Добавлено
- dispatch/stdio edge; coverage 97,3%, 115 тестов.

## [5.18.0] — 2026-11-16

PG agent profile.

### Добавлено
- PG `get_agent`/cancel/requeue guards; coverage 96,6%, 114 тестов.

## [5.17.0] — 2026-11-16

Agent profile API.

### Добавлено
- `GET /v1/agents/{id}`, MCP `swarm_get_agent`; 113 тестов.

## [5.16.0] — 2026-11-16

API error branches.

### Добавлено
- task renew ValueError, GET SwarmError; coverage 96,9%, 110 тестов.

## [5.15.0] — 2026-11-16

SSE disconnect coverage.

### Добавлено
- client disconnect path; coverage 96,6%, 109 тестов.

## [5.14.0] — 2026-11-16

Configurable SSE keepalive.

### Добавлено
- `SWARMLAB_STREAM_KEEPALIVE_S`; 108 тестов.

## [5.13.0] — 2026-11-16

SSE keepalive.

### Добавлено
- `: keepalive` каждую секунду простоя; coverage 96,5%, 107 тестов.

## [5.12.0] — 2026-11-16

Configurable agent TTL.

### Добавлено
- `SWARMLAB_AGENT_TTL` для discover (SQLite/PG); 106 тестов.

## [5.11.0] — 2026-11-16

SSE listener coverage.

### Добавлено
- PG SSE listener success/failure; TCP_NODELAY error path; coverage 96,4%, 105 тестов.

## [5.10.1] — 2026-11-16

CI green.

### Исправлено
- CI измеряет SQLite coverage (PG-тесты опциональны); порог 90; manifest validation.

## [5.10.0] — 2026-11-16

CI quality gates.

### Добавлено
- CI: `--fail-under=90` + manifest validation; 103 теста.

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
