# BENCH — swarm-lab

## Методика

`scripts/bench.py` создаёт N задач, W воркеров клеймят и завершают их; измеряется
claim+complete latency и суммарный throughput. SQLite — один процесс; PG — несколько
store-инстансов (multi-replica).

```bash
python scripts/bench.py --backend sqlite --tasks 200 --workers 8
python scripts/bench.py --backend postgres --dsn postgresql://... --tasks 200 --workers 8
```

## Результат (локально, 15.11.2026)

| Backend | Tasks | Workers | Completed | tasks/sec | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| SQLite | 200 | 8 | 200 | **5412.4** | **1.088 ms** | **2.917 ms** |

Условия: Python 3.12, Windows, WAL, один процесс; цифры зависят от железа.
PG-бенчмарк запускается на реальном DSN; embedded PG в тестах проверяет
multi-replica exactly-once отдельно (`tests/test_load.py`).
