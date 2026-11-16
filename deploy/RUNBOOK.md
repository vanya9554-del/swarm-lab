# RUNBOOK — swarm-lab production

## Deploy (Helm)

```bash
helm upgrade --install swarmlab deploy/helm/swarmlab \
  -f deploy/helm/swarmlab/ci/postgres-values.yaml \
  --set image.tag=v9.4.0 \
  --set auth.token="$SWARMLAB_TOKEN"
```

ArgoCD: `deploy/argocd/staging.yaml` (auto sync main), `prod.yaml` (manual sync, pinned tag).

## Image

- `ghcr.io/vanya9554-del/swarm-lab:vX.Y.Z` (release workflow on tag).
- Pull secret, если пакет приватный.

## Проверка

```bash
kubectl -n swarmlab rollout status deploy/swarmlab
kubectl -n swarmlab port-forward svc/swarmlab 8788:80
curl -fsS localhost:8788/ready
curl -fsS localhost:8788/metrics | head
```

## Rollback

```bash
helm history swarmlab -n swarmlab
helm rollback swarmlab <REVISION> -n swarmlab
```

ArgoCD prod: `argocd app rollback swarmlab-prod <id>`; staging — revert main.

## Scale

- SQLite: **1 replica**, RWO PVC. Не масштабировать.
- PG: `replicaCount`/HPA; HPA требует PG.
- Agent workers масштабируются отдельно (клиенты claim).

## Backup/restore

- SQLite: CronJob `swarmlab-backup` (Helm) или `python scripts/backup.py`.
- Restore: остановить deployment → `python scripts/restore.py` → запустить; проверка `/ready` и `/v1/stats`.
- PG: `pg_dump`/`psql`; restore в новую БД, переключить Secret DSN.
- Drill: раз в квартал восстановить в staging и прогнать smoke.

## Incident: 5xx/latency

1. `/ready` и `check.quick_check`.
2. `kubectl logs -l app.kubernetes.io/name=swarmlab --since=10m` (JSON).
3. `kubectl top pod`; HPA.
4. SQLite lock/диск; PG connections/locks.
5. Rollback если после деплоя.

## Incident: нет агентов/backlog

- `swarmlab_agents`, `swarmlab_tasks{status="pending"}`.
- Проверить discovery TTL (`SWARMLAB_AGENT_TTL`), rate limit, workers.
- Временный scale workers/PG app replicas.

## Security

- Секреты: Secret/ESO, не values.
- JWT: HS256 secret/issuer/audience; OIDC на gateway.
- Rate limit на ingress + app.
- Trivy scan в CI; пентест-чеклист в `SECURITY.md`.

## SLO

См. `deploy/observability/SLO.md`; alerts `deploy/observability/prometheus-rules.yaml`.

## Блокеры

Live K8s, внешний аудит/пентест, KMS/S3 — см. `NIGHT_SHIFT.md`.

## Schema migrations / rolling upgrade

- Schema version: **9** (`PRAGMA user_version`, `schema_meta`).
- SQLite: `ALTER TABLE` идемпотентны при старте; **остановить** перед restore.
- PostgreSQL: `ADD COLUMN IF NOT EXISTS` + `INSERT ... ON CONFLICT` на старте; безопасно для rolling upgrade.
- Rolling: обновлять поды по одному; readiness `/ready`; не откатывать схему назад старой версией.
- Перед апгрейдом: backup (SQLite/PG dump); проверить `/ready`.
- Откат приложения: helm rollback; схема остаётся совместимой (аддитивные колонки).
