# deploy — swarm-lab

## Варианты

| Режим | Где | Масштаб |
|---|---|---|
| Compose SQLite | `docker-compose.yml` | 1 реплика, локально |
| Compose + PG | `docker-compose.yml --profile pg` | 1 app + PG |
| K8s raw SQLite | `deploy/k8s.yaml` | 1 реплика, PVC |
| K8s raw PG | `deploy/k8s-postgres.yaml` | 2+ реплики, HPA |
| **Helm** | `deploy/helm/swarmlab` | все режимы |

## Helm quick start (SQLite)

```bash
helm install swarmlab deploy/helm/swarmlab \
  --set auth.token="$SWARMLAB_TOKEN" \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=swarm.example.com
```

## Helm + PostgreSQL + HPA

```bash
kubectl create secret generic swarmlab-pg \
  --from-literal=dsn='postgresql://swarm:pass@postgres:5432/swarm'
kubectl create secret generic swarmlab-auth --from-literal=token="$SWARMLAB_TOKEN"

helm install swarmlab deploy/helm/swarmlab \
  -f deploy/helm/swarmlab/ci/postgres-values.yaml
```

Значения:

- `persistence.*` — PVC для SQLite.
- `postgresql.enabled/existingSecret` — PG DSN (обязателен при enabled).
- `autoscaling.enabled` — HPA (только с PG).
- `backup.enabled` — CronJob backup в отдельный PVC.
- `serviceMonitor.enabled` — Prometheus Operator ServiceMonitor.
- `networkPolicy.ingress` — список `from` для ingress-controller.
- `auth.existingSecret` — не создавать Secret с токеном внутри chart.

## Проверки

```bash
helm lint deploy/helm/swarmlab
helm template sqlite deploy/helm/swarmlab >/tmp/sqlite.yaml
helm template pg deploy/helm/swarmlab -f deploy/helm/swarmlab/ci/postgres-values.yaml >/tmp/pg.yaml
python scripts/validate_manifests.py
```

## Ограничения

- Live K8s не проверялся (внешний блокер).
- SQLite: только 1 реплика (RWO PVC).
- TLS/Ingress зависит от кластера и cert-manager.
- Backup SQLite: `VACUUM INTO` в отдельный PVC; восстановление — скопировать файл.
- Backup PG: `pg_dump` в PVC; восстановление — `psql`.

## Backup/restore (SQLite)

```bash
python scripts/backup.py --db data/swarm.db --out backups/swarm-$(date +%Y%m%d).db
python scripts/restore.py --backup backups/swarm-20261116.db --db data/swarm.db
```

Restore требует остановленный сервер (WAL sidecar-файлы удаляются). Для PG — `pg_dump`/`psql`.

## ArgoCD / GHCR

- `deploy/argocd/staging.yaml` — автосинк с `main`, namespace `swarmlab-staging`.
- `deploy/argocd/prod.yaml` — тег `vX.Y.Z`, ручной sync.
- `release.yml` собирает и пушит `ghcr.io/vanya9554-del/swarm-lab:<tag>` на git tag.

```bash
kubectl apply -f deploy/argocd/staging.yaml
kubectl apply -f deploy/argocd/prod.yaml
```

## NetworkPolicy

По умолчанию ingress разрешён только pod'ам того же namespace (`podSelector: {}`).
Для ingress-controller задайте `networkPolicy.ingress`:
```yaml
networkPolicy:
  ingress:
    - namespaceSelector: {matchLabels: {kubernetes.io/metadata.name: ingress-nginx}}
      podSelector: {matchLabels: {app.kubernetes.io/name: ingress-nginx}}
```
`allowAllIngress: true` — только для отладки.
