# swarm-lab

Agent-native swarm runtime и benchmark. **Без UI**: только HTTP/JSON, batch, SSE, MCP и CLI.
Проект создаётся автономно; цель — reference implementation для быстрого обмена задачами,
знаниями и событиями между агентами.

## Принципы

- Агент — первый клиент: минимум RTT, batch, SSE, компактные ответы.
- Никакого SPA/человеческого UI в критическом пути.
- SQLite по умолчанию; PostgreSQL — для multi-replica.
- Everything is measured: latency/throughput/lease/fencing/chaos.

## Быстрый старт

```bash
python -m unittest discover -s tests
python -m swarmlab --help
python -m swarmlab serve --port 8788              # SQLite
python -m swarmlab serve --db postgresql://...   # PG multi-replica
python -m swarmlab mcp            # MCP stdio
# MCP HTTP: POST /mcp (initialize/tools/list/tools/call/resources/prompts)
curl -sS -X POST localhost:8788/v1/agents -H 'Content-Type: application/json' \
  -d '{"agent_id":"a1","capabilities":["search"]}'
curl -sS -X POST localhost:8788/v1/tasks -H 'Content-Type: application/json' \
  -d '{"capability":"search","payload":{"q":"x"}}'
```

## Benchmark

```bash
python scripts/bench.py --backend sqlite --tasks 200 --workers 8
```

См. `BENCH.md`: 5412 tasks/s, p50 1.09 ms (SQLite, локально).

## Статус

Статус: v0.1.0, работает store + HTTP API/SSE/batch. S3 MCP — следующий шаг. План — `PLAN.md`, протокол — `SPEC.md`, автономный runbook — `../NIGHT_SHIFT.md`.
