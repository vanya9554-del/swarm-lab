# SLO — swarm-lab

## Цели (production)

| SLI | SLO | Окно |
|---|---|---:|
| Availability `/ready` | **99,9%** | 30d |
| HTTP 5xx rate | **< 1%** | 30d |
| HTTP p95 latency | **< 500 ms** | 30d |
| Claim-to-complete p95 | **< 60 s** | 30d |
| Task completion (no dead-letter) | **> 99%** | 30d |

## Error budget

- 99,9% availability → **43m 12s** недоступности в 30 дней.
- 1% 5xx → 1% запросов; алерт `SwarmlabHighErrorRate` при 5% за 5m.
- p95 500ms; алерт `SwarmlabHighLatencyP95` при >500ms 10m.

## Метрики

- `up{job="swarmlab"}` — scrape.
- `probe_success{job="swarmlab-ready"}` — blackbox `/ready`.
- `swarmlab_http_requests_total{status}` — error rate.
- `swarmlab_http_request_duration_seconds_*` — latency histogram.
- `swarmlab_agents`, `swarmlab_tasks{status}`, `swarmlab_events_total` — market state.

## Реакция

| Алерт | Действие |
|---|---|
| SwarmlabDown / NotReady | проверить pod/логи, `/ready`; рестарт/rollback |
| HighErrorRate | смотреть 5xx path/status, последние деплои, БД |
| HighLatency | CPU/DB/очередь, проверить `claim` и SQLite lock |
| NoAgents | проверить клиентов/discovery TTL |
| BacklogHigh | масштабировать workers/агентов, проверить rate limit |
| RateLimited | проверить токены/лимиты, не DDoS ли |

## Проверка

```bash
promtool check rules deploy/observability/prometheus-rules.yaml
```
