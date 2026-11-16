# ACCEPTANCE — swarm-lab 10.0

Дата: 2026-11-16. Версия: **10.0.0**.

## Функциональность

| Требование | Статус | Доказательство |
|---|---|---|
| Task market (priority/affinity/dedup/lease/fencing) | ✅ | tests, README |
| TTL/dependencies/attempts/dead-letter | ✅ | tests |
| Cancel/requeue/task events | ✅ | API/MCP, tests |
| Agents register/discover/heartbeat/profile | ✅ | API/MCP, tests |
| SQLite + PostgreSQL | ✅ | tests, chaos |
| HTTP batch/SSE/gzip/HEAD | ✅ | tests |
| MCP stdio/HTTP | ✅ | tests |
| Python SDK | ✅ | `swarmlab.client` |
| OpenAPI/capabilities | ✅ | `/v1/openapi`, tests |
| Maintenance (vacuum/prune/expire) | ✅ | API/MCP, tests |

## Качество

| Критерий | Статус | Значение |
|---|---|---|
| unit/integration tests | ✅ | **163/163 OK** |
| coverage | ✅ | **100,0%** |
| ruff | ✅ | 0 |
| CI (test/docker/trivy/helm/kubeconform) | ✅ | green |
| CI Python 3.12 | ✅ | green |
| fuzz/property | ✅ | `tests/test_fuzz.py` |
| PG chaos 500 | ✅ | 3 реплики/6 воркеров, exactly-once |
| HTTP PG chaos 100 | ✅ | 2 API-реплики, exactly-once |
| load: engine/HTTP/soak | ✅ | BENCH/HTTP_BENCH |

## Инфраструктура

| Требование | Статус | Доказательство |
|---|---|---|
| Dockerfile + compose | ✅ | CI docker build |
| Trivy scan образа | ✅ | CI |
| Helm chart | ✅ | `deploy/helm/swarmlab`, CI lint/template/kubeconform |
| TLS ingress | ✅ | chart ingress/tls |
| HPA/PDB/NetworkPolicy | ✅ | chart |
| Backup/restore | ✅ | scripts + test + CronJob |
| Migrations/rolling upgrade | ✅ | schema v10, RUNBOOK |
| ArgoCD staging/prod | ✅ | `deploy/argocd` |
| GHCR push по тегу | ✅ | release workflow |
| Live K8s deploy | ⏳ | нет кластера (внешний блокер) |

## Security

| Требование | Статус | Доказательство |
|---|---|---|
| Bearer/scopes | ✅ | tests |
| JWT HS256/RS256, iss/aud/exp/nbf | ✅ | tests |
| Rate limit/body limit/headers | ✅ | tests |
| Secrets via K8s/ESO | ✅ | Helm values/existingSecret |
| Пентест-чеклист | ✅ | SECURITY.md |
| Trivy | ✅ | CI |
| Внешний аудит/пентест | ⏳ | внешний исполнитель |
| KMS/S3 | ⏳ | нет доступа |

## Observability

| Требование | Статус | Доказательство |
|---|---|---|
| /metrics counters+histogram | ✅ | tests |
| /health /ready /ready check | ✅ | tests |
| JSON logs | ✅ | tests |
| Prometheus alerts | ✅ | prometheus-rules.yaml |
| Grafana dashboard | ✅ | grafana-dashboard.json |
| SLO/error budget | ✅ | SLO.md |

## Документация

README, SPEC, PLAN, PROGRESS, QUALITY, FINAL_REPORT, BENCH, HTTP_BENCH, CHAOS,
DEPLOY, RUNBOOK, SECURITY, SLO, RELEASE_NOTES — ✅.

## Внешние блокеры

1. Live K8s-кластер/облако.
2. Внешний аудит/пентест.
3. KMS/S3 для секретов/бэкапов.
4. OIDC discovery/JWKS rotation (gateway; RS256 с PEM поддержан).
5. Docker локально (сборка/скан в CI).

## Итог

Внутренняя часть проекта завершена: **10.0.0**, 163 теста, 100% coverage,
production-инфраструктура готова статически/CI и требует live-валидации.
