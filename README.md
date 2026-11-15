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
```

## Статус

Каркас v0.1.0. План — `PLAN.md`, протокол — `SPEC.md`, автономный runbook — `../NIGHT_SHIFT.md`.
