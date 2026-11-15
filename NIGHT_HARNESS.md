# NIGHT_HARNESS — непрерывный фоновый процесс

`scripts/night_harness.py` работает **независимо от model-turn'ов**:
- каждые 5с: health/ensure server, submit→claim→complete цикл;
- каждую 1с: tick; JSONL `data/night_harness.jsonl`;
- каждые 15мин: `unittest` (без остановки цикла);
- до `2026-11-16T12:00:00+03:00`.

Запуск:

```powershell
python scripts/night_harness.py --until 2026-11-16T12:00:00+03:00
```

Это machine-level непрерывность (soak/health/tests). Модельные рассуждения всё равно
дискретны: между ходами есть пауза; если процесс/сессия/ПК умрёт — harness тоже.
