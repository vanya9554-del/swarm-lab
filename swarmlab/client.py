"""Minimal stdlib HTTP client for swarm-lab agents."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from typing import Any, Self


class SwarmClientError(RuntimeError):
    def __init__(self, status: int, payload: Any) -> None:
        super().__init__(f"HTTP {status}: {payload}")
        self.status = status
        self.payload = payload


class SwarmClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8788", token: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as exc:
            raise SwarmClientError(exc.code, exc.read().decode("utf-8", "replace")) from exc
        if not payload.get("ok"):
            raise SwarmClientError(200, payload)
        return payload.get("data")

    def register(self, agent_id: str, capabilities: list[str], endpoint: str | None = None) -> dict[str, Any]:
        return self._request("POST", "/v1/agents", {"agent_id": agent_id, "capabilities": capabilities, "endpoint": endpoint})

    def discover(self, capability: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"capability": capability, "limit": limit})
        return self._request("GET", f"/v1/agents?{query}")

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/agents/{urllib.parse.quote(agent_id)}")

    def heartbeat(self, agent_id: str, status: str = "idle") -> dict[str, Any]:
        return self._request("POST", "/v1/heartbeat", {"agent_id": agent_id, "status": status})

    def submit(self, capability: str, payload: Any = None, **options: Any) -> dict[str, Any]:
        body = {"capability": capability, "payload": payload}
        body.update({k: v for k, v in options.items() if v is not None})
        return self._request("POST", "/v1/tasks", body)

    def claim(self, agent_id: str, capability: str | None = None, lease_s: float | None = None) -> dict[str, Any] | None:
        return self._request("POST", "/v1/tasks/claim", {"agent_id": agent_id, "capability": capability, "lease_s": lease_s})

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request("GET", f"/v1/tasks/{urllib.parse.quote(task_id)}")

    def complete(self, task_id: str, agent_id: str, result: Any = None, fence: int | None = None) -> dict[str, Any]:
        return self._request("POST", f"/v1/tasks/{urllib.parse.quote(task_id)}/complete",
                             {"agent_id": agent_id, "result": result, "fence": fence})

    def renew(self, task_id: str, agent_id: str, lease_s: float = 60, fence: int | None = None) -> dict[str, Any]:
        return self._request("POST", f"/v1/tasks/{urllib.parse.quote(task_id)}/renew",
                             {"agent_id": agent_id, "lease_s": lease_s, "fence": fence})

    def cancel(self, task_id: str, agent_id: str | None = None) -> dict[str, Any]:
        return self._request("POST", f"/v1/tasks/{urllib.parse.quote(task_id)}/cancel", {"agent_id": agent_id})

    def requeue(self, task_id: str) -> dict[str, Any]:
        return self._request("POST", f"/v1/tasks/{urllib.parse.quote(task_id)}/requeue", {})

    def task_events(self, task_id: str, limit: int = 50) -> list[dict[str, Any]]:
        return self._request("GET", f"/v1/tasks/{urllib.parse.quote(task_id)}/events?limit={limit}")

    def stats(self) -> dict[str, Any]:
        return self._request("GET", "/v1/stats")

    def events(self, after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        return self._request("GET", f"/v1/events?after={after}&limit={limit}")

    def stream(self, after: int = 0, limit: int = 50, timeout_s: float = 5) -> Iterator[dict[str, Any]]:
        req = urllib.request.Request(
            f"{self.base_url}/v1/stream?after={after}&limit={limit}&timeout_s={timeout_s}",
            method="GET",
        )
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        with urllib.request.urlopen(req, timeout=timeout_s + 2) as resp:
            for raw in resp:
                line = raw.decode("utf-8").rstrip("\n")
                if line.startswith("data: "):
                    yield json.loads(line[6:])

    def close(self) -> None:
        # Stateless stdlib client; kept for context-manager symmetry.
        return None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
