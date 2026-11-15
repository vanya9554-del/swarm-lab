# PLAN — swarm-lab (24h autonomous build)

## Фазы

- **S0 bootstrap** — каркас, store, тесты, README/SPEC. ✅
- **S1 engine** — task market, discovery, lease/fencing, event log; SQLite. 
- **S2 API** — stdlib HTTP, batch, SSE, idempotency; CLI `python -m swarmlab`. ✅ базовый
- **S3 MCP** — tools/resources/prompts для агентов. ✅
- **S4 PostgreSQL** — multi-replica claim (`FOR UPDATE SKIP LOCKED`), migrations. ✅
- **S5 load/chaos** — 2+ replicas, stale workers, latency/throughput отчёт. ✅
- **S6 hardening** — security, rate-limit, observability, Docker/CI. ✅
- **S7 release 1.0** — SBOM/checksums/README/ACCEPTANCE. ✅
- **S8 SSE NOTIFY** — PG LISTEN/NOTIFY вместо polling. ✅
- **S9 backpressure/auth** — pending limit, per-token rate key. ✅
- **S10 chaos/load** — 3 реплики/6 воркеров/100 задач. ✅
- **S11 deploy** — compose + K8s manifests. ✅

## Definition of done

- `python -m unittest` зелёный.
- API/MCP/CLI работают.
- 2-replica soak без дублей.
- Бенчмарк p50/p95 и throughput.
- Docker/CI/README/ACCEPTANCE.
- Внешние блокеры (GitHub push, K8s) — в `../NIGHT_SHIFT.md`.
