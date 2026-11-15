"""OpenAPI 3.1 spec для agent-native discovery."""
from __future__ import annotations

from typing import Any

from . import __version__


def spec() -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {"title": "swarm-lab", "version": __version__, "description": "Agent-native swarm runtime"},
        "servers": [{"url": "/"}],
        "paths": {
            "/health": {"get": {"summary": "Liveness"}},
            "/ready": {"get": {"summary": "Readiness + stats"}},
            "/metrics": {"get": {"summary": "Prometheus metrics"}},
            "/v1/version": {"get": {"summary": "Version"}},
            "/v1/capabilities": {"get": {"summary": "Feature discovery"}},
            "/v1/openapi": {"get": {"summary": "This document"}},
            "/v1/agents": {
                "get": {"summary": "Discover agents"},
                "post": {"summary": "Register agent"},
            },
            "/v1/agents/{agent_id}": {"delete": {"summary": "Deregister agent"}},
            "/v1/heartbeat": {"post": {"summary": "Agent heartbeat"}},
            "/v1/tasks": {
                "get": {"summary": "List tasks"},
                "post": {"summary": "Submit task"},
            },
            "/v1/tasks/{task_id}": {"get": {"summary": "Get task"}},
            "/v1/tasks/claim": {"post": {"summary": "Claim task"}},
            "/v1/tasks/{task_id}/complete": {"post": {"summary": "Complete task"}},
            "/v1/tasks/{task_id}/renew": {"post": {"summary": "Renew lease"}},
            "/v1/tasks/{task_id}/cancel": {"post": {"summary": "Cancel task"}},
            "/v1/tasks/{task_id}/requeue": {"post": {"summary": "Requeue cancelled/failed"}},
            "/v1/events": {"get": {"summary": "Event log"}},
            "/v1/stream": {"get": {"summary": "SSE stream"}},
            "/v1/batch": {"post": {"summary": "Batch RPC"}},
            "/v1/stats": {"get": {"summary": "Store stats"}},
            "/v1/maintenance/expire": {"post": {"summary": "Expire TTL tasks"}},
            "/mcp": {"post": {"summary": "MCP JSON-RPC"}},
        },
    }
