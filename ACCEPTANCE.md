# ACCEPTANCE — swarm-lab 1.0

**Дата:** 15.11.2026 · **Версия:** 8.1.0 · **Проект:** agent-native swarm runtime (без UI).

## Матрикс

| Проверка | Результат |
|---|---|
| unittest | **145/145 OK** (store, API, MCP, PG, load, hardening) |
| SQLite engine | task market, priority, affinity, dedup, lease/fence |
| HTTP API | register/discover/submit/claim/complete/renew/events/stream/batch/stats |
| SSE | event stream, `after=seq`; PG LISTEN/NOTIFY |
| MCP | tools/resources/prompts, stdio + HTTP `/mcp` |
| PostgreSQL | 3 replica chaos 100 tasks; 2 replica atomic claim `FOR UPDATE SKIP LOCKED`, stale fence |
| Load | SQLite 200 tasks/8 workers: **5412 tasks/s**, p50 **1.088 ms**, p95 **2.917 ms** |
| Quality | coverage 100,0%, ruff 0; HTTP 200/200, 726 tasks/s |
| Observability | X-Request-Id, latency histogram |
| Hardening | scopes/RBAC, bearer token, rate limit per token, backpressure 429, body limit, headers, `/metrics` |
| Deploy | Dockerfile, compose (SQLite/PG), K8s manifests, CI |
| Release | SBOM/checksums в `release/v1.0.0/` |

## Команды

```bash
cd swarm-lab
python -m unittest discover -s tests -v
python scripts/bench.py --backend sqlite --tasks 200 --workers 8
python scripts/release.py
python -m swarmlab serve --port 8788
```

## Ограничения

- Нет UI by design.
- Auth — простой bearer; scopes/RBAC нет.
- SSE polling 50 мс; PG LISTEN/NOTIFY — backlog.
- Exactly-once side effects не гарантируется (только fencing/идемпотентность).
- K8s/live multi-replica/внешний аудит — вне проекта.
- GitHub remote/push требует `gh auth login`/PAT.
