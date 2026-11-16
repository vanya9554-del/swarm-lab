# CHAOS — swarm-lab

## Сценарий

3 PostgreSQL-реплики, 6 воркеров, 100 задач, priority 0..6; воркеры клеймят и завершают
задачи с fence. Проверяется: нет дублей completion, нет потерь, все 100 завершены.

```bash
python -m unittest tests.test_chaos -v
```

## Результат

- Задач: 100; воркеров: 6; реплик: 3.
- Завершено ровно 100, уникальных 100, pending=0.
- Тест в `tests/test_chaos.py`.

## Ограничения

- Нет искусственного обрыва соединения/сетевого partition; reconnect — backlog.
- PG-кластер embedded; live K8s — внешний блокер.

## 2026-11-16

- `test_chaos_exactly_once`, `test_parallel_exactly_once_and_stale`, `test_reconnect_under_load`, `test_sqlite_concurrent_store` — **4/4 OK**.

## 2026-11-16 PG chaos 500

- 3 реплики, 6 воркеров, **500/500**, exactly-once, 7.2s.
