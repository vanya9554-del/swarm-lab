# HTTP_BENCH — swarm-lab

## Результат (локально, 15.11.2026)

`scripts/http_bench.py --tasks 200 --workers 8`:

| Метрика | Значение |
|---|---:|
| Completed | **200/200** |
| tasks/sec | **726.4** |
| p50 | **7.473 ms** |
| p95 | **25.500 ms** |
| mean | 10.665 ms |
| Errors | **0** |

## Найденный дефект

Первые прогоны давали `409/404` и `RemoteDisconnected`:
`sqlite3.InterfaceError: bad parameter or other API misuse` — `_one/_all` читали
общий SQLite connection без `self.lock`, пока другой поток делал claim/commit.
Исправлено: все чтения под `RLock`; регрессия `SqliteConcurrencyTests` (8 воркеров/100 задач).
