"""swarm-lab: agent-native task market (SQLite)."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 16

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
CREATE TABLE IF NOT EXISTS agent_tokens (
    token_hash TEXT PRIMARY KEY,
    agent_id   TEXT NOT NULL,
    scopes     TEXT NOT NULL DEFAULT 'read write',
    created_at REAL NOT NULL,
    revoked    INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS roles (
    scope       TEXT NOT NULL,
    name        TEXT NOT NULL,
    agent_id    TEXT NOT NULL,
    lease_until REAL NOT NULL,
    epoch       INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (scope, name)
);
CREATE TABLE IF NOT EXISTS artifacts (
    name         TEXT PRIMARY KEY,
    owner        TEXT NOT NULL DEFAULT '',
    channel      TEXT,
    content      TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text/plain',
    version      INTEGER NOT NULL DEFAULT 1,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS channel_members (
    channel    TEXT NOT NULL,
    agent_id   TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'member',
    joined_at  REAL NOT NULL,
    PRIMARY KEY (channel, agent_id)
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    from_agent TEXT NOT NULL,
    to_agent   TEXT,
    channel    TEXT,
    body       TEXT NOT NULL,
    created_at REAL NOT NULL,
    read_at    REAL
);
CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_agent, id);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel, id);
CREATE TABLE IF NOT EXISTS audit (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at REAL NOT NULL,
    actor      TEXT NOT NULL DEFAULT '',
    action     TEXT NOT NULL,
    target     TEXT NOT NULL DEFAULT '',
    detail     TEXT NOT NULL DEFAULT '',
    ip         TEXT NOT NULL DEFAULT ''
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
            self.conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

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
            self.conn.execute("UPDATE agent_tokens SET revoked=1 WHERE agent_id=?", (agent_id,))
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

    def audit(self, action: str, actor: str = "", target: str = "", detail: Any = None, ip: str = "") -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO audit(created_at, actor, action, target, detail, ip) VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), actor, action, target, json.dumps(detail or {}), ip),
            )

    def token_agent(self, token: str) -> str | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = self._one("SELECT agent_id FROM agent_tokens WHERE token_hash=? AND revoked=0", (digest,))
        return str(row["agent_id"]) if row else None

    def claim_role(self, scope: str, name: str, agent_id: str, ttl_s: float = 60) -> dict[str, Any]:
        if not str(scope).strip() or not str(name).strip() or not str(agent_id).strip():
            raise SwarmError("BAD_REQUEST", "scope, name and agent_id are required")
        now = time.time()
        with self.lock:
            row = self._one("SELECT * FROM roles WHERE scope=? AND name=?", (str(scope), str(name)))
            if row and float(row["lease_until"]) > now and row["agent_id"] != str(agent_id):
                raise SwarmError("CONFLICT", f"role held by {row['agent_id']}")
            epoch = int(row["epoch"]) + 1 if row else 1
            self.conn.execute(
                "INSERT INTO roles(scope, name, agent_id, lease_until, epoch) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(scope, name) DO UPDATE SET agent_id=excluded.agent_id, lease_until=excluded.lease_until, epoch=excluded.epoch",
                (str(scope), str(name), str(agent_id), now + max(1.0, float(ttl_s)), epoch),
            )
        return self._one("SELECT * FROM roles WHERE scope=? AND name=?", (str(scope), str(name))) or {}

    def renew_role(self, scope: str, name: str, agent_id: str, ttl_s: float = 60) -> dict[str, Any]:
        now = time.time()
        with self.lock:
            row = self._one("SELECT * FROM roles WHERE scope=? AND name=?", (str(scope), str(name)))
            if not row or row["agent_id"] != str(agent_id):
                raise SwarmError("CONFLICT", "role not held by agent")
            self.conn.execute("UPDATE roles SET lease_until=? WHERE scope=? AND name=?", (now + max(1.0, float(ttl_s)), str(scope), str(name)))
        return self._one("SELECT * FROM roles WHERE scope=? AND name=?", (str(scope), str(name))) or {}

    def release_role(self, scope: str, name: str, agent_id: str) -> dict[str, Any]:
        with self.lock:
            deleted = self.conn.execute("DELETE FROM roles WHERE scope=? AND name=? AND agent_id=?", (str(scope), str(name), str(agent_id))).rowcount
        return {"scope": scope, "name": name, "released": bool(deleted)}

    def roles(self, scope: str | None = None) -> list[dict[str, Any]]:
        if scope:
            return self._all("SELECT * FROM roles WHERE scope=? ORDER BY name", (str(scope),))
        return self._all("SELECT * FROM roles ORDER BY scope, name")

    def put_artifact(self, name: str, content: str, owner: str = "", channel: str | None = None, content_type: str = "text/plain") -> dict[str, Any]:
        if not str(name).strip():
            raise SwarmError("BAD_REQUEST", "name is required")
        now = time.time()
        with self.lock:
            self.conn.execute(
                "INSERT INTO artifacts(name, owner, channel, content, content_type, version, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?) ON CONFLICT(name) DO UPDATE SET "
                "owner=excluded.owner, channel=excluded.channel, content=excluded.content, "
                "content_type=excluded.content_type, version=artifacts.version+1, updated_at=excluded.updated_at",
                (str(name), owner, channel, str(content), content_type, now, now),
            )
        return self.get_artifact(name) or {"name": name}

    def get_artifact(self, name: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM artifacts WHERE name=?", (str(name),))

    def list_artifacts(self, channel: str | None = None, prefix: str = "", limit: int = 100) -> list[dict[str, Any]]:
        clauses, params = [], []
        if channel:
            clauses.append("channel = ?")
            params.append(channel)
        if prefix:
            clauses.append("name LIKE ?")
            params.append(prefix + "%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(500, int(limit))))
        return self._all(f"SELECT name, owner, channel, content_type, version, updated_at FROM artifacts{where} ORDER BY name LIMIT ?", tuple(params))

    def delete_artifact(self, name: str) -> bool:
        with self.lock:
            return bool(self.conn.execute("DELETE FROM artifacts WHERE name=?", (str(name),)).rowcount)

    def join_channel(self, channel: str, agent_id: str, role: str = "member") -> dict[str, Any]:
        if not str(channel).strip():
            raise SwarmError("BAD_REQUEST", "channel is required")
        if not str(agent_id).strip():
            raise SwarmError("BAD_REQUEST", "agent_id is required")
        with self.lock:
            self.conn.execute(
                "INSERT INTO channel_members(channel, agent_id, role, joined_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(channel, agent_id) DO UPDATE SET role=excluded.role",
                (str(channel), str(agent_id), str(role), time.time()),
            )
        return self._one("SELECT * FROM channel_members WHERE channel=? AND agent_id=?", (str(channel), str(agent_id))) or {}

    def leave_channel(self, channel: str, agent_id: str) -> dict[str, Any]:
        with self.lock:
            deleted = self.conn.execute("DELETE FROM channel_members WHERE channel=? AND agent_id=?", (str(channel), str(agent_id))).rowcount
        return {"channel": channel, "agent_id": agent_id, "deleted": bool(deleted)}

    def channel_members(self, channel: str) -> list[dict[str, Any]]:
        return self._all("SELECT * FROM channel_members WHERE channel=? ORDER BY joined_at", (str(channel),))

    def send_message(self, from_agent: str, to_agent: str | None = None, channel: str | None = None, body: str = "") -> dict[str, Any]:
        if not str(from_agent).strip():
            raise SwarmError("BAD_REQUEST", "from_agent is required")
        if not str(body).strip():
            raise SwarmError("BAD_REQUEST", "body is required")
        if not to_agent and not channel:
            raise SwarmError("BAD_REQUEST", "to_agent or channel is required")
        with self.lock:
            if channel:
                self.conn.execute(
                    "INSERT INTO channel_members(channel, agent_id, role, joined_at) VALUES (?, ?, 'member', ?) "
                    "ON CONFLICT(channel, agent_id) DO NOTHING",
                    (str(channel), str(from_agent), time.time()),
                )
            cur = self.conn.execute(
                "INSERT INTO messages(from_agent, to_agent, channel, body, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(from_agent), to_agent, channel, str(body), time.time()),
            )
            msg_id = int(cur.lastrowid)
        return self._one("SELECT * FROM messages WHERE id=?", (msg_id,)) or {"id": msg_id}

    def messages(self, agent_id: str | None = None, channel: str | None = None, after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        clauses = ["id > ?"]
        params: list[Any] = [int(after)]
        if channel:
            clauses.append("channel = ?")
            params.append(channel)
        elif agent_id:
            clauses.append("(to_agent = ? OR from_agent = ?)")
            params.extend([agent_id, agent_id])
        params.append(max(1, min(500, int(limit))))
        return self._all(f"SELECT * FROM messages WHERE {' AND '.join(clauses)} ORDER BY id LIMIT ?", tuple(params))

    def mark_read(self, message_id: int, agent_id: str) -> dict[str, Any]:
        with self.lock:
            self.conn.execute("UPDATE messages SET read_at=? WHERE id=? AND to_agent=?", (time.time(), int(message_id), agent_id))
        return {"id": int(message_id), "read": True}

    def channels(self) -> list[dict[str, Any]]:
        return self._all("SELECT channel, COUNT(*) AS n FROM messages WHERE channel IS NOT NULL GROUP BY channel ORDER BY channel")

    def issue_agent_token(self, agent_id: str, scopes: tuple[str, ...] = ("read", "write")) -> str:
        token = "agt_" + secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            self.conn.execute(
                "INSERT INTO agent_tokens(token_hash, agent_id, scopes, created_at) VALUES (?, ?, ?, ?)",
                (digest, agent_id, " ".join(scopes), time.time()),
            )
        return token

    def token_scopes(self, token: str) -> set[str] | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = self._one("SELECT scopes FROM agent_tokens WHERE token_hash=? AND revoked=0", (digest,))
        return set(str(row["scopes"]).split()) if row else None

    def revoke_agent_tokens(self, agent_id: str) -> None:
        with self.lock:
            self.conn.execute("UPDATE agent_tokens SET revoked=1 WHERE agent_id=?", (agent_id,))

    def audits(self, limit: int = 100, action: str = "", actor: str = "") -> list[dict[str, Any]]:
        where, params = "", []
        if action:
            where += " AND action = ?"
            params.append(action)
        if actor:
            where += " AND actor = ?"
            params.append(actor)
        params.append(max(1, min(500, int(limit))))
        rows = self._all(f"SELECT * FROM audit WHERE 1=1{where} ORDER BY id DESC LIMIT ?", tuple(params))
        for row in rows:
            try:
                row["detail"] = json.loads(row.get("detail") or "{}")
            except (ValueError, TypeError):
                pass
        return rows

    def task_events(self, task_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM events WHERE payload LIKE ? ORDER BY seq DESC LIMIT ?",
            (f'%"{task_id}"%', max(1, min(500, int(limit)))),
        )
        out = []
        for row in rows:
            try:
                payload = json.loads(row.get("payload") or "{}")
            except (ValueError, TypeError):
                payload = {}
            if payload.get("task_id") == task_id:
                row["payload"] = payload
                out.append(row)
        return out

    def events(self, after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._all("SELECT * FROM events WHERE seq > ? ORDER BY seq LIMIT ?", (int(after), int(limit)))
        for row in rows:
            if row.get("payload"):
                try:
                    row["payload"] = json.loads(row["payload"])
                except ValueError:
                    pass
        return rows

    def prune(self, older_than_s: float = 86400) -> dict[str, Any]:
        cutoff = time.time() - max(60.0, float(older_than_s))
        with self.lock:
            tasks = self.conn.execute(
                "DELETE FROM tasks WHERE status IN ('completed', 'failed', 'cancelled') "
                "AND completed_at IS NOT NULL AND completed_at < ?",
                (cutoff,),
            ).rowcount
            events = self.conn.execute("DELETE FROM events WHERE created_at < ?", (cutoff,)).rowcount
            audits = self.conn.execute("DELETE FROM audit WHERE created_at < ?", (cutoff,)).rowcount
        return {"ok": True, "tasks": int(tasks or 0), "events": int(events or 0), "audits": int(audits or 0), "cutoff": cutoff}

    def vacuum(self) -> dict[str, Any]:
        with self.lock:
            row = self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        return {"ok": True, "checkpoint": list(row) if row else []}

    def schema_version(self) -> int:
        row = self._one("PRAGMA user_version")
        return int(next(iter(row.values()))) if row else 0

    def check(self) -> dict[str, Any]:
        row = self._one("PRAGMA quick_check")
        value = str(next(iter(row.values()))) if row else "unknown"
        return {"ok": value == "ok", "quick_check": value}

    def stats(self) -> dict[str, Any]:
        agents = self._one("SELECT COUNT(*) AS n FROM agents") or {}
        tasks = self._all("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status")
        events = self._one("SELECT COUNT(*) AS n, MAX(seq) AS last_seq FROM events") or {}
        audit = self._one("SELECT COUNT(*) AS n FROM audit") or {}
        return {
            "agents": int(agents.get("n") or 0),
            "tasks": {str(r["status"]): int(r["n"]) for r in tasks},
            "events": {"total": int(events.get("n") or 0), "last_seq": int(events.get("last_seq") or 0)},
            "audit": int(audit.get("n") or 0),
        }
