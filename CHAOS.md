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
