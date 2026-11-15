"""swarm-lab — agent-native swarm runtime."""
from __future__ import annotations

__version__ = "5.13.0"

from .store import SwarmError, SwarmStore


def open_store(target: str = ":memory:"):
    """SQLite path или postgresql:// DSN."""
    if str(target).startswith(("postgresql://", "postgres://")):
        from .pg import PgSwarmStore
        return PgSwarmStore(str(target))
    return SwarmStore(str(target))


__all__ = ["SwarmError", "SwarmStore", "__version__", "open_store"]
