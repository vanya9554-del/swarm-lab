"""PostgreSQL LISTEN/NOTIFY для SSE swarm-lab."""
from __future__ import annotations

from typing import Self

CHANNEL = "swarmlab_events"


def available() -> bool:
    try:
        import psycopg  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


class PgEventStream:
    def __init__(self, dsn: str, channel: str = CHANNEL, connect_timeout: int = 3) -> None:
        if not available():
            raise RuntimeError("psycopg is not installed")
        import psycopg

        self.channel = channel
        self.conn = psycopg.connect(dsn, autocommit=True, connect_timeout=connect_timeout)
        with self.conn.cursor() as cur:
            cur.execute(f'LISTEN "{self.channel}"')

    def wait(self, timeout: float = 0.2) -> int | None:
        try:
            for notify in self.conn.notifies(timeout=max(0.01, float(timeout))):
                payload = str(notify.payload)
                return int(payload) if payload.isdigit() else None
        except Exception:  # noqa: BLE001
            return None
        return None

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:  # noqa: BLE001, S110
            pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


__all__ = ["CHANNEL", "PgEventStream", "available"]
