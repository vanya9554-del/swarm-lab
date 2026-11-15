# -*- coding: utf-8 -*-
"""Prometheus-совместимые метрики swarm-lab."""
from __future__ import annotations

import threading
import time
from collections import defaultdict

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


class SwarmMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[tuple[str, str, int], int] = defaultdict(int)
        self._started = time.time()
        self._total = 0

    def observe(self, method: str, path: str, status: int) -> None:
        with self._lock:
            self._counters[(str(method).upper(), str(path), int(status))] += 1
            self._total += 1

    def render(self, store) -> str:
        lines = [
            "# HELP swarmlab_http_requests_total HTTP requests by method/path/status",
            "# TYPE swarmlab_http_requests_total counter",
        ]
        with self._lock:
            counters = dict(self._counters)
            total = self._total
        for (method, path, status), value in sorted(counters.items()):
            lines.append(
                f'swarmlab_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {value}'
            )
        lines += [
            "# HELP swarmlab_http_requests_total_all Total requests (process lifetime)",
            "# TYPE swarmlab_http_requests_total_all counter",
            f"swarmlab_http_requests_total_all {total}",
        ]
        try:
            stats = store.stats()
            lines.append("# HELP swarmlab_agents Agents")
            lines.append("# TYPE swarmlab_agents gauge")
            lines.append(f"swarmlab_agents {stats.get('agents', 0)}")
            for status, value in sorted((stats.get("tasks") or {}).items()):
                lines.append(f'swarmlab_tasks{{status="{status}"}} {value}')
            lines.append("# HELP swarmlab_events_total Events")
            lines.append("# TYPE swarmlab_events_total counter")
            lines.append(f"swarmlab_events_total {(stats.get('events') or {}).get('total', 0)}")
        except Exception:  # noqa: BLE001, S110
            pass
        lines.append(f"# HELP swarmlab_uptime_seconds Uptime")
        lines.append("# TYPE swarmlab_uptime_seconds gauge")
        lines.append(f"swarmlab_uptime_seconds {time.time() - self._started:.1f}")
        lines.append("")
        return "\n".join(lines)
