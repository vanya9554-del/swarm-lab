# Observability — swarm-lab

## Компоненты

- `/metrics` — Prometheus text format (HTTP counters/histogram, tasks, agents, events, uptime).
- `/ready` — readiness + integrity (`quick_check`/`SELECT 1`).
- `SWARMLAB_LOG_FORMAT=json` — structured access/error logs (JSON lines, `request_id`, duration).
- `deploy/observability/prometheus-rules.yaml` — алерты.
- `deploy/observability/grafana-dashboard.json` — dashboard (UID `swarmlab`).
- `deploy/observability/SLO.md` — SLI/SLO/error budget.

## Установка

```bash
kubectl apply -f deploy/observability/prometheus-rules.yaml
kubectl create configmap swarmlab-dashboard \
  --from-file=swarmlab.json=deploy/observability/grafana-dashboard.json
```

В Helm: `--set serviceMonitor.enabled=true --set prometheusRule.enabled=true`
(требуется Prometheus Operator).

## Логи (Docker/K8s)

```yaml
env:
  - name: SWARMLAB_LOG_FORMAT
    value: json
```

Пример строки:

```json
{"ts": 1763000000.1, "level": "info", "request_id": "ab12", "remote": "10.0.0.1", "method": "POST", "path": "/v1/tasks", "status": 200, "bytes": 123, "duration_ms": 3.2}
```

## Алерты

| Alert | Условие |
|---|---|
| SwarmlabDown | `up == 0` 2m |
| SwarmlabNotReady | `/ready` probe fail 2m |
| SwarmlabHighErrorRate | 5xx >5% 5m |
| SwarmlabHighLatencyP95 | p95 >500ms 10m |
| SwarmlabHighLatencyP99 | p99 >2s 10m |
| SwarmlabNoAgents | agents=0 10m |
| SwarmlabBacklogHigh | pending >1000 15m |
| SwarmlabRateLimited | 429 rate >1/s 10m |

## Проверка правил

```bash
promtool check rules deploy/observability/prometheus-rules.yaml
python -m json.tool deploy/observability/grafana-dashboard.json >/dev/null
```
