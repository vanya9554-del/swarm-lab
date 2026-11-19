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
            "/": {"get": {"summary": "Dashboard / service discovery"}},
            "/dashboard": {"get": {"summary": "Dashboard"}},
            "/llms.txt": {"get": {"summary": "LLM/agent index"}},
            "/robots.txt": {"get": {"summary": "Robots"}},
            "/sitemap.xml": {"get": {"summary": "Sitemap"}},
            "/agents.json": {"get": {"summary": "Agent discovery manifest"}},
            "/.well-known/ai-plugin.json": {"get": {"summary": "AI plugin manifest"}},
            "/health": {"get": {"summary": "Liveness"}},
            "/ready": {"get": {"summary": "Readiness + stats"}},
            "/metrics": {"get": {"summary": "Prometheus metrics"}},
            "/v1/version": {"get": {"summary": "Version"}},
            "/v1/capabilities": {"get": {"summary": "Feature discovery"}},
            "/v1/openapi": {"get": {"summary": "This document"}},
            "/v1/agents/register": {"post": {"summary": "Self-register agent (join code)"}},
            "/v1/agents": {
                "get": {"summary": "Discover agents"},
                "post": {"summary": "Register agent"},
            },
            "/v1/agents/{agent_id}": {
                "get": {"summary": "Get agent profile"},
                "delete": {"summary": "Deregister agent"},
            },
            "/v1/heartbeat": {"post": {"summary": "Agent heartbeat"}},
            "/v1/tasks": {
                "get": {"summary": "List tasks"},
                "post": {"summary": "Submit task"},
            },
            "/v1/tasks/{task_id}": {"get": {"summary": "Get task"}},
            "/v1/tasks/{task_id}/events": {"get": {"summary": "Task event history"}},
            "/v1/tasks/claim": {"post": {"summary": "Claim task"}},
            "/v1/tasks/{task_id}/complete": {"post": {"summary": "Complete task"}},
            "/v1/tasks/{task_id}/renew": {"post": {"summary": "Renew lease"}},
            "/v1/tasks/{task_id}/cancel": {"post": {"summary": "Cancel task"}},
            "/v1/tasks/{task_id}/requeue": {"post": {"summary": "Requeue cancelled/failed"}},
            "/v1/messages/stream": {"get": {"summary": "SSE message stream"}},
            "/v1/messages": {
                "get": {"summary": "Inbox/channel messages"},
                "post": {"summary": "Send message"},
            },
            "/v1/messages/{message_id}/read": {"post": {"summary": "Mark message read"}},
            "/v1/plugins": {"get": {"summary": "List plugins"}, "post": {"summary": "Propose plugin"}},
            "/v1/plugins/{name}/{version}": {"get": {"summary": "Get plugin"}},
            "/v1/plugins/{name}/{version}/approve": {"post": {"summary": "Approve plugin"}},
            "/v1/plugins/{name}/{version}/reject": {"post": {"summary": "Reject plugin"}},
            "/v1/reputation": {"get": {"summary": "Leaderboard"}},
            "/v1/reputation/{agent_id}": {"get": {"summary": "Agent reputation"}},
            "/v1/reputation/feedback": {"post": {"summary": "Give feedback"}},
            "/v1/roles": {"get": {"summary": "List roles"}},
            "/v1/roles/claim": {"post": {"summary": "Claim role lease"}},
            "/v1/roles/renew": {"post": {"summary": "Renew role lease"}},
            "/v1/roles/release": {"post": {"summary": "Release role"}},
            "/v1/artifacts": {"get": {"summary": "List artifacts"}, "post": {"summary": "Put artifact"}},
            "/v1/artifacts/{name}": {"get": {"summary": "Get artifact"}, "delete": {"summary": "Delete artifact"}},
            "/v1/channels": {"get": {"summary": "List channels"}},
            "/v1/channels/{channel}/join": {"post": {"summary": "Join channel"}},
            "/v1/channels/{channel}/leave": {"post": {"summary": "Leave channel"}},
            "/v1/channels/{channel}/roles": {"post": {"summary": "Assign channel role"}},
            "/v1/channels/{channel}/members": {"get": {"summary": "Channel members"}},
            "/v1/events": {"get": {"summary": "Event log"}},
            "/v1/stream": {"get": {"summary": "SSE stream"}},
            "/v1/batch": {"post": {"summary": "Batch RPC"}},
            "/v1/audit": {"get": {"summary": "Audit log"}},
            "/v1/stats": {"get": {"summary": "Store stats"}},
            "/v1/maintenance/expire": {"post": {"summary": "Expire TTL tasks"}},
            "/v1/maintenance/vacuum": {"post": {"summary": "WAL checkpoint"}},
            "/v1/maintenance/prune": {"post": {"summary": "Prune old rows"}},
            "/mcp": {"post": {"summary": "MCP JSON-RPC"}},
        },
    }
