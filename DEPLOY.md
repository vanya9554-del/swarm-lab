# DEPLOY — swarm-lab

## Docker

```bash
docker build -t swarmlab:1.0.0 .
docker run --rm -p 8788:8788 -e SWARMLAB_TOKEN=secret -v swarm-data:/data swarmlab:1.0.0
```

## Compose

```bash
docker compose up -d --build          # SQLite
docker compose --profile pg up -d     # app-pg + postgres
```

## Kubernetes (без live-проверки)

```bash
kubectl apply -f deploy/k8s.yaml
```

- Образ заменить на опубликованный.
- Token — в Secret, не в git.
- SQLite → 1 реплика + PVC; PG → `--db postgresql://...`.
- Live K8s — внешний блокер; манифест не проверялся в кластере.

## Настройки

| Env | Значение |
|---|---|
| `SWARMLAB_TOKEN` | bearer token (пусто = без auth) |
| `SWARMLAB_RATE_RPS` | лимит запросов/сек на IP/token, 0=off |
| `SWARMLAB_MAX_PENDING` | backpressure на pending tasks, 0=off |
| `SWARMLAB_LOG` | `0` — выключить access log |
