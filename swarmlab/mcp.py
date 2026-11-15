"""MCP (JSON-RPC 2024-11-05) для swarm-lab: tools/resources/prompts."""
from __future__ import annotations

import json
import sys
from typing import Any, TextIO

from . import __version__
from .store import SwarmError, SwarmStore

PROTOCOL = "2024-11-05"


class McpError(Exception):
    def __init__(self, code: int, message: str) -> None:
        self.code = int(code)
        self.message = message
        super().__init__(message)


def _text(value: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}], "isError": False}


def _err(code: str, message: str) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps({"error": {"code": code, "message": message}})}],
        "isError": True,
    }


class McpDispatcher:
    def __init__(self, store: SwarmStore) -> None:
        self.store = store

    def handle(self, message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return self._rpc(None, error=(-32600, "invalid request"))
        rid = message.get("id")
        method = message.get("method")
        params = message.get("params") or {}
        if not isinstance(method, str):
            return None if "id" not in message else self._rpc(rid, error=(-32600, "no method"))
        try:
            result = self._dispatch(method, params)
        except McpError as exc:
            return None if "id" not in message else self._rpc(rid, error=(exc.code, exc.message))
        except SwarmError as exc:
            return None if "id" not in message else self._rpc(rid, error=(-32602, f"{exc.code}: {exc.message}"))
        except Exception as exc:  # noqa: BLE001
            return None if "id" not in message else self._rpc(rid, error=(-32603, str(exc)))
        if "id" not in message:
            return None
        return self._rpc(rid, result=result)

    @staticmethod
    def _rpc(rid: Any, *, result: Any = None, error: tuple[int, str] | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {"jsonrpc": "2.0", "id": rid}
        if error is not None:
            out["error"] = {"code": error[0], "message": error[1]}
        else:
            out["result"] = result
        return out

    def _dispatch(self, method: str, params: Any) -> Any:
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}, "resources": {"subscribe": False}, "prompts": {"listChanged": False}},
                "serverInfo": {"name": "swarm-lab", "version": __version__},
                "instructions": "Agent-native swarm: register, discover, submit/claim/complete, events, batch. No UI.",
            }
        if method in ("notifications/initialized", "initialized", "ping"):
            return {}
        if method == "tools/list":
            return {"tools": [{"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]} for t in TOOLS]}
        if method == "tools/call":
            if not isinstance(params, dict):
                raise McpError(-32602, "params must be object")
            name = params.get("name")
            args = params.get("arguments") or {}
            if not isinstance(args, dict):
                raise McpError(-32602, "arguments must be object")
            return self._call(name, args)
        if method == "resources/list":
            return {"resources": RESOURCES}
        if method == "resources/read":
            uri = params.get("uri") if isinstance(params, dict) else None
            if uri == "swarm://stats":
                payload: Any = self.store.stats()
            elif uri == "swarm://events":
                payload = self.store.events(0, 50)
            else:
                raise McpError(-32602, f"unknown resource {uri}")
            return {"contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(payload, ensure_ascii=False)}]}
        if method == "prompts/list":
            return {"prompts": PROMPTS}
        if method == "prompts/get":
            return self._prompt(params)
        raise McpError(-32601, f"method not found: {method}")

    def _call(self, name: Any, args: dict[str, Any]) -> dict[str, Any]:
        try:
            if name == "swarm_stats":
                return _text(self.store.stats())
            if name == "swarm_discover":
                return _text(self.store.discover(args.get("capability"), int(args.get("limit") or 20)))
            if name == "swarm_get_task":
                task = self.store.get(str(args.get("task_id") or ""))
                return _text(task) if task is not None else _err("NOT_FOUND", "task not found")
            if name == "swarm_events":
                return _text(self.store.events(int(args.get("after") or 0), int(args.get("limit") or 100)))
            if name == "swarm_register":
                caps = args.get("capabilities")
                if not isinstance(caps, list):
                    return _err("INVALID_ARGUMENTS", "capabilities must be array")
                return _text(self.store.register(str(args.get("agent_id") or ""), caps, args.get("endpoint")))
            if name == "swarm_submit":
                return _text(self.store.submit(
                    str(args.get("capability") or ""), args.get("payload"),
                    priority=int(args.get("priority") or 0),
                    dedup_key=args.get("dedup_key"),
                    affinity_agent_id=args.get("affinity_agent_id"),
                    ttl_s=float(args["ttl_s"]) if args.get("ttl_s") is not None else None,
                    depends_on=args.get("depends_on"),
                ))
            if name == "swarm_claim":
                return _text(self.store.claim(
                    str(args.get("agent_id") or ""), args.get("capability"), float(args.get("lease_s") or 60)
                ))
            if name == "swarm_complete":
                fence = int(args["fence"]) if args.get("fence") is not None else None
                return _text(self.store.complete(
                    str(args.get("task_id") or ""), str(args.get("agent_id") or ""),
                    args.get("result"), success=bool(args.get("success", True)), fence=fence,
                ))
            if name == "swarm_expire":
                return _text(self.store.expire())
            if name == "swarm_deregister":
                return _text(self.store.deregister(str(args.get("agent_id") or "")))
            if name == "swarm_requeue":
                return _text(self.store.requeue(str(args.get("task_id") or "")))
            if name == "swarm_cancel":
                return _text(self.store.cancel(str(args.get("task_id") or ""), args.get("agent_id")))
            if name == "swarm_renew":
                fence = int(args["fence"]) if args.get("fence") is not None else None
                return _text(self.store.renew(
                    str(args.get("task_id") or ""), str(args.get("agent_id") or ""),
                    float(args.get("lease_s") or 60), fence,
                ))
            if name == "swarm_batch":
                ops = args.get("ops")
                if not isinstance(ops, list):
                    return _err("INVALID_ARGUMENTS", "ops must be array")
                results = []
                for op in ops[:100]:
                    try:
                        results.append({"ok": True, "data": self._call_op(op)})
                    except (SwarmError, McpError) as exc:
                        results.append({"ok": False, "code": getattr(exc, "code", "ERROR"), "message": str(exc)})
                return _text(results)
            return _err("UNKNOWN_TOOL", f"unknown tool {name}")
        except McpError as exc:
            return _err("INVALID_ARGUMENTS", exc.message)
        except SwarmError as exc:
            return _err(exc.code, exc.message)
        except (ValueError, TypeError) as exc:
            return _err("INVALID_ARGUMENTS", str(exc))

    def _call_op(self, op: Any) -> Any:
        if not isinstance(op, dict):
            raise McpError(-32602, "op must be object")
        name = str(op.get("op") or "")
        mapping = {
            "stats": "swarm_stats", "discover": "swarm_discover", "events": "swarm_events",
            "submit": "swarm_submit", "claim": "swarm_claim", "complete": "swarm_complete",
            "renew": "swarm_renew", "cancel": "swarm_cancel", "register": "swarm_register",
        }
        tool = mapping.get(name)
        if not tool:
            raise McpError(-32602, f"unknown op {name}")
        args = {k: v for k, v in op.items() if k != "op"}
        return json.loads(self._call(tool, args)["content"][0]["text"])

    def _prompt(self, params: Any) -> dict[str, Any]:
        if not isinstance(params, dict):
            raise McpError(-32602, "params must be object")
        name = params.get("name")
        args = params.get("arguments") or {}
        if name == "swarm_worker":
            text = f"Claim tasks for capability={args.get('capability','default')}, complete with fence."
        elif name == "swarm_planner":
            text = f"Split goal into swarm tasks with priority/dedup: {args.get('goal','')}"
        else:
            raise McpError(-32602, f"unknown prompt {name}")
        return {"description": "swarm prompt", "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}


TOOLS: tuple[dict[str, Any], ...] = (
    {"name": "swarm_stats", "description": "Swarm stats", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "swarm_discover", "description": "Discover agents", "inputSchema": {"type": "object", "properties": {"capability": {"type": "string"}, "limit": {"type": "integer"}}, "additionalProperties": False}},
    {"name": "swarm_get_task", "description": "Get task by id", "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"], "additionalProperties": False}},
    {"name": "swarm_events", "description": "Events after seq", "inputSchema": {"type": "object", "properties": {"after": {"type": "integer"}, "limit": {"type": "integer"}}, "additionalProperties": False}},
    {"name": "swarm_register", "description": "Register agent", "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "capabilities": {"type": "array", "items": {"type": "string"}}, "endpoint": {"type": "string"}}, "required": ["agent_id", "capabilities"], "additionalProperties": False}},
    {"name": "swarm_submit", "description": "Submit task", "inputSchema": {"type": "object", "properties": {"capability": {"type": "string"}, "payload": {}, "priority": {"type": "integer"}, "dedup_key": {"type": "string"}, "affinity_agent_id": {"type": "string"}}, "required": ["capability"], "additionalProperties": False}},
    {"name": "swarm_claim", "description": "Claim task", "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string"}, "capability": {"type": "string"}, "lease_s": {"type": "number"}}, "required": ["agent_id"], "additionalProperties": False}},
    {"name": "swarm_complete", "description": "Complete task", "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "agent_id": {"type": "string"}, "result": {}, "success": {"type": "boolean"}, "fence": {"type": "integer"}}, "required": ["task_id", "agent_id"], "additionalProperties": False}},
    {"name": "swarm_expire", "description": "Expire pending TTL tasks", "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "swarm_deregister", "description": "Deregister agent", "inputSchema": {"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"], "additionalProperties": False}},
    {"name": "swarm_requeue", "description": "Requeue cancelled/failed task", "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}}, "required": ["task_id"], "additionalProperties": False}},
    {"name": "swarm_cancel", "description": "Cancel task", "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "agent_id": {"type": "string"}}, "required": ["task_id"], "additionalProperties": False}},
    {"name": "swarm_renew", "description": "Renew lease", "inputSchema": {"type": "object", "properties": {"task_id": {"type": "string"}, "agent_id": {"type": "string"}, "lease_s": {"type": "number"}, "fence": {"type": "integer"}}, "required": ["task_id", "agent_id"], "additionalProperties": False}},
    {"name": "swarm_batch", "description": "Batch ops", "inputSchema": {"type": "object", "properties": {"ops": {"type": "array", "items": {"type": "object"}}}, "required": ["ops"], "additionalProperties": False}},
)

RESOURCES: tuple[dict[str, Any], ...] = (
    {"uri": "swarm://stats", "name": "Swarm stats", "description": "stats", "mimeType": "application/json"},
    {"uri": "swarm://events", "name": "Swarm events", "description": "last events", "mimeType": "application/json"},
)

PROMPTS: tuple[dict[str, Any], ...] = (
    {"name": "swarm_worker", "description": "Claim/complete loop with fence", "arguments": [{"name": "capability", "required": True}]},
    {"name": "swarm_planner", "description": "Plan tasks with priority/dedup", "arguments": [{"name": "goal", "required": True}]},
)


def main_stdio(store: SwarmStore, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    dispatcher = McpDispatcher(store)
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            response: Any = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            response = dispatcher.handle(message)
        if response is not None:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()
