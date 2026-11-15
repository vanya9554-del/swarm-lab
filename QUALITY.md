# QUALITY — swarm-lab

## Текущий срез

| Метрика | Значение |
|---|---|
| unittest | **88/88 OK** |
| coverage (source=swarmlab) | **95,0%** |
| ruff | **0 errors** |
| PG/chaos tests | 4 (embedded, skip без psycopg) |
| benchmark | 5412 tasks/s SQLite, p50 1.09 ms |

## Команды

```bash
python -m unittest discover -s tests -v
python -m coverage run --source=swarmlab -m unittest discover -s tests -q
python -m coverage report -m
python -m ruff check swarmlab tests scripts
```

## Остаток

- `__main__`/MCP error paths частично покрыты.
- PG reconnect/chaos — embedded; live K8s — внешний блокер.
- Coverage target 80% — следующий шаг.
