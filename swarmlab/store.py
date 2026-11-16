"""swarm-lab: agent-native task market (SQLite)."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;
PRAGMA cache_size=-20000;
PRAGMA temp_store=MEMORY;

CREATE TABLE IF NOT EXISTS agents (
    agent_id      TEXT PRIMARY KEY,
    capabilities  TEXT NOT NULL DEFAULT '[]',
    endpoint      TEXT,
    status        TEXT NOT NULL DEFAULT 'idle',
    last_seen_at  REAL NOT NULL DEFAULT 0,
    meta          TEXT
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id        TEXT PRIMARY KEY,
    capability     TEXT NOT NULL,
    payload        TEXT,
    priority       INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'pending',
    dedup_key      TEXT,
    affinity_agent_id TEXT,
    expires_at     REAL,
    depends_on     TEXT,
    attempts       INTEGER NOT NULL DEFAULT 0,
    max_attempts   INTEGER NOT NULL DEFAULT 3,
    created_at     REAL NOT NULL,
    claimed_by     TEXT,
    lease_until    REAL,
    lease_epoch    INTEGER NOT NULL DEFAULT 0,
    result         TEXT,
    completed_at   REAL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_dedup ON tasks(capability, dedup_key)
    WHERE dedup_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_pending ON tasks(status, priority, created_at);

CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    type       TEXT NOT NULL,
    payload    TEXT,
    created_at REAL NOT NULL
);
"""


class SwarmError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def _json(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class SwarmStore:
    """Потокобезопасный SQLite-store; WAL, один writer."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.path = str(path)
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            cols = {str(row["name"]) for row in self.conn.execute("PRAGMA table_info(tasks)").fetchall()}
            if "expires_at" not in cols:
                self.conn.execute("ALTER TABLE tasks ADD COLUMN expires_at REAL")
            if "depends_on" not in cols:
                self.conn.execute("ALTER TABLE tasks ADD COLUMN depends_on TEXT")
            if "attempts" not in cols:
                self.conn.execute("ALTER TABLE tasks ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")
            if "max_attempts" not in cols:
                self.conn.execute("ALTER TABLE tasks ADD COLUMN max_attempts INTEGER NOT NULL DEFAULT 3")

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def _one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.lock:
            cur = self.conn.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.lock:
            return [dict(row) for row in self.conn.execute(sql, params).fetchall()]

    def event(self, event_type: str, payload: dict[str, Any]) -> int:
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO events(type, payload, created_at) VALUES (?, ?, ?)",
                (event_type, _json(payload), time.time()),
            )
            return int(cur.lastrowid or 0)

    # -- agents ------------------------------------------------------------
    def register(self, agent_id: str, capabilities: list[str], endpoint: str | None = None) -> dict[str, Any]:
        caps = sorted({str(c).strip() for c in capabilities if str(c).strip()})
        if not agent_id:
            raise SwarmError("BAD_REQUEST", "agent_id is required")
        now = time.time()
        with self.lock:
            self.conn.execute(
                "INSERT INTO agents(agent_id, capabilities, endpoint, status, last_seen_at) "
                "VALUES (?, ?, ?, 'idle', ?) ON CONFLICT(agent_id) DO UPDATE SET "
                "capabilities=excluded.capabilities, endpoint=excluded.endpoint, last_seen_at=excluded.last_seen_at",
                (agent_id, _json(caps), endpoint, now),
            )
        self.event("agent.registered", {"agent_id": agent_id, "capabilities": caps})
        return {"agent_id": agent_id, "capabilities": caps, "endpoint": endpoint, "last_seen_at": now}

    def heartbeat(self, agent_id: str, status: str = "idle") -> dict[str, Any]:
        now = time.time()
        with self.lock:
            changed = self.conn.execute(
                "UPDATE agents SET last_seen_at=?, status=? WHERE agent_id=?", (now, status, agent_id)
            ).rowcount
        if not changed:
            raise SwarmError("NOT_FOUND", f"agent {agent_id} not found")
        return {"agent_id": agent_id, "status": status, "last_seen_at": now}

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM agents WHERE agent_id = ?", (agent_id,))
        if not row:
            return None
        row["capabilities"] = json.loads(row.get("capabilities") or "[]")
        return row

    def deregister(self, agent_id: str) -> dict[str, Any]:
        with self.lock:
            deleted = self.conn.execute("DELETE FROM agents WHERE agent_id=?", (agent_id,)).rowcount
        if deleted:
            self.event("agent.deregistered", {"agent_id": agent_id})
        return {"agent_id": agent_id, "deleted": bool(deleted)}

    def discover(self, capability: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        clauses = ["last_seen_at >= ?"]
        params: list[Any] = [time.time() - float(os.environ.get("SWARMLAB_AGENT_TTL") or 90)]
        if capability:
            clauses.append("capabilities LIKE ?")
            params.append(f'%"{capability}"%')
        params.append(max(1, min(100, int(limit))))
        rows = self._all(
            "SELECT * FROM agents WHERE " + " AND ".join(clauses) + " ORDER BY last_seen_at DESC LIMIT ?",
            tuple(params),
        )
        for row in rows:
            row["capabilities"] = json.loads(row["capabilities"] or "[]")
        return rows

    # -- tasks -------------------------------------------------------------
    def submit(
        self,
        capability: str,
        payload: Any = None,
        *,
        priority: int = 0,
        dedup_key: str | None = None,
        affinity_agent_id: str | None = None,
        ttl_s: float | None = None,
        depends_on: str | None = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        if not capability:
            raise SwarmError("BAD_REQUEST", "capability is required")
        if dedup_key:
            existing = self._one(
                "SELECT * FROM tasks WHERE capability = ? AND dedup_key = ?", (capability, dedup_key)
            )
            if existing:
                return {**self._decode(existing), "duplicate": True}
        try:
            limit = int(__import__("os").environ.get("SWARMLAB_MAX_PENDING", "0"))
        except ValueError:
            limit = 0
        if limit > 0:
            row = self._one("SELECT COUNT(*) AS n FROM tasks WHERE status = 'pending'") or {}
            if int(row.get("n") or 0) >= limit:
                raise SwarmError("BACKPRESSURE", "pending tasks limit exceeded")
        task_id = _id("task")
        now = time.time()
        with self.lock:
            self.conn.execute(
                "INSERT INTO tasks(task_id, capability, payload, priority, status, dedup_key, "
                "affinity_agent_id, expires_at, depends_on, max_attempts, created_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)",
                (task_id, capability, _json(payload), int(priority), dedup_key, affinity_agent_id,
                 now + max(0.0, ttl_s) if ttl_s is not None else None, depends_on,
                 max(1, int(max_attempts)), now),
            )
        self.event("task.submitted", {"task_id": task_id, "capability": capability})
        return {"task_id": task_id, "capability": capability, "status": "pending", "created_at": now}

    @staticmethod
    def _decode(row: dict[str, Any]) -> dict[str, Any]:
        for key in ("payload", "result"):
            if row.get(key):
                try:
                    row[key] = json.loads(row[key])
                except (ValueError, TypeError):
                    pass
        return row

    def claim(self, agent_id: str, capability: str | None = None, lease_s: float = 60.0) -> dict[str, Any] | None:
        now = time.time()
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                self.conn.execute(
                    "UPDATE tasks SET status='failed' WHERE status='claimed' "
                    "AND lease_until IS NOT NULL AND lease_until < ? AND attempts >= max_attempts",
                    (now,),
                )
                self.conn.execute(
                    "UPDATE tasks SET status='pending', claimed_by=NULL, lease_until=NULL "
                    "WHERE status='claimed' AND lease_until IS NOT NULL AND lease_until < ? "
                    "AND attempts < max_attempts",
                    (now,),
                )
                self.conn.execute(
                    "UPDATE tasks SET status='expired' WHERE status='pending' AND expires_at IS NOT NULL AND expires_at < ?",
                    (now,),
                )
                clauses = [
                    "status='pending'",
                    "attempts < max_attempts",
                    "(affinity_agent_id IS NULL OR affinity_agent_id = ?)",
                    "(depends_on IS NULL OR depends_on IN (SELECT task_id FROM tasks WHERE status='completed'))",
                ]
                params: list[Any] = [agent_id]
                if capability:
                    clauses.append("capability = ?")
                    params.append(capability)
                row = self._one(
                    "SELECT * FROM tasks WHERE " + " AND ".join(clauses) + " "
                    "ORDER BY priority DESC, created_at LIMIT 1",
                    tuple(params),
                )
                if row is None:
                    self.conn.execute("COMMIT")
                    return None
                self.conn.execute(
                    "UPDATE tasks SET status='claimed', claimed_by=?, lease_until=?, "
                    "lease_epoch=lease_epoch+1, attempts=attempts+1 WHERE task_id=?",
                    (agent_id, now + max(1.0, lease_s), row["task_id"]),
                )
                self.conn.execute(
                    "UPDATE agents SET status='working', last_seen_at=? WHERE agent_id=?", (now, agent_id)
                )
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
        self.event("task.claimed", {"task_id": row["task_id"], "agent_id": agent_id})
        return self.get(row["task_id"])

    def get(self, task_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        return self._decode(row) if row else None

    def complete(
        self,
        task_id: str,
        agent_id: str,
        result: Any = None,
        *,
        success: bool = True,
        fence: int | None = None,
    ) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            raise SwarmError("NOT_FOUND", "task not found")
        if fence is not None and int(task.get("lease_epoch") or 0) != int(fence):
            raise SwarmError("STALE_LEASE", "lease epoch mismatch")
        if task.get("claimed_by") != agent_id:
            raise SwarmError("FORBIDDEN", "task is not claimed by agent")
        if task.get("status") in ("completed", "failed"):
            return {**task, "idempotent": True}
        now = time.time()
        status = "completed" if success else "failed"
        with self.lock:
            self.conn.execute(
                "UPDATE tasks SET status=?, result=?, completed_at=? WHERE task_id=?",
                (status, _json(result), now, task_id),
            )
            self.conn.execute(
                "UPDATE agents SET status='idle', last_seen_at=? WHERE agent_id=?", (now, agent_id)
            )
        self.event("task." + status, {"task_id": task_id, "agent_id": agent_id})
        return {"task_id": task_id, "status": status, "completed_at": now}

    def cancel(self, task_id: str, agent_id: str | None = None) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            raise SwarmError("NOT_FOUND", "task not found")
        if task.get("status") in ("completed", "failed", "cancelled"):
            return {**task, "idempotent": True}
        if agent_id and task.get("claimed_by") and task["claimed_by"] != agent_id:
            raise SwarmError("FORBIDDEN", "task is claimed by another agent")
        with self.lock:
            self.conn.execute("UPDATE tasks SET status='cancelled' WHERE task_id=?", (task_id,))
        self.event("task.cancelled", {"task_id": task_id, "agent_id": agent_id})
        return self.get(task_id) or {"task_id": task_id, "status": "cancelled"}

    def expire(self) -> dict[str, Any]:
        now = time.time()
        with self.lock:
            count = self.conn.execute(
                "UPDATE tasks SET status='expired' WHERE status='pending' AND expires_at IS NOT NULL AND expires_at < ?",
                (now,),
            ).rowcount
        if count:
            self.event("task.expired", {"count": int(count)})
        return {"expired": int(count or 0)}

    def requeue(self, task_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            raise SwarmError("NOT_FOUND", "task not found")
        if task.get("status") not in ("cancelled", "failed"):
            raise SwarmError("CONFLICT", f"cannot requeue status {task.get('status')}")
        with self.lock:
            self.conn.execute(
                "UPDATE tasks SET status='pending', claimed_by=NULL, lease_until=NULL, attempts=0, "
                "result=NULL, completed_at=NULL WHERE task_id=?",
                (task_id,),
            )
        self.event("task.requeued", {"task_id": task_id})
        return self.get(task_id) or {"task_id": task_id, "status": "pending"}

    def renew(self, task_id: str, agent_id: str, lease_s: float = 60.0, fence: int | None = None) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            raise SwarmError("NOT_FOUND", "task not found")
        if fence is not None and int(task.get("lease_epoch") or 0) != int(fence):
            raise SwarmError("STALE_LEASE", "lease epoch mismatch")
        if task.get("claimed_by") != agent_id:
            raise SwarmError("FORBIDDEN", "task is not claimed by agent")
        until = time.time() + max(1.0, lease_s)
        with self.lock:
            self.conn.execute("UPDATE tasks SET lease_until=? WHERE task_id=?", (until, task_id))
        return {"task_id": task_id, "lease_until": until}

    def tasks(self, status: str | None = None, limit: int = 50, capability: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if capability:
            clauses.append("capability = ?")
            params.append(capability)
        sql = "SELECT * FROM tasks"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))
        return [self._decode(row) for row in self._all(sql, tuple(params))]

    def events(self, after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._all("SELECT * FROM events WHERE seq > ? ORDER BY seq LIMIT ?", (int(after), int(limit)))
        for row in rows:
            if row.get("payload"):
                try:
                    row["payload"] = json.loads(row["payload"])
                except ValueError:
                    pass
        return rows

    def check(self) -> dict[str, Any]:
        row = self._one("PRAGMA quick_check")
        value = str(next(iter(row.values()))) if row else "unknown"
        return {"ok": value == "ok", "quick_check": value}

    def stats(self) -> dict[str, Any]:
        agents = self._one("SELECT COUNT(*) AS n FROM agents") or {}
        tasks = self._all("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status")
        events = self._one("SELECT COUNT(*) AS n, MAX(seq) AS last_seq FROM events") or {}
        return {
            "agents": int(agents.get("n") or 0),
            "tasks": {str(r["status"]): int(r["n"]) for r in tasks},
            "events": {"total": int(events.get("n") or 0), "last_seq": int(events.get("last_seq") or 0)},
        }
