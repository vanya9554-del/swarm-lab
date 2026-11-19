"""swarm-lab PostgreSQL backend (optional): multi-replica claim."""
from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
import uuid
from typing import Any

from .store import SwarmError

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    id INTEGER PRIMARY KEY,
    version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS agents (
    agent_id TEXT PRIMARY KEY,
    capabilities TEXT NOT NULL DEFAULT '[]',
    endpoint TEXT,
    status TEXT NOT NULL DEFAULT 'idle',
    last_seen_at DOUBLE PRECISION NOT NULL DEFAULT 0,
    meta TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    capability TEXT NOT NULL,
    payload TEXT,
    priority INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    dedup_key TEXT,
    affinity_agent_id TEXT,
    expires_at DOUBLE PRECISION,
    depends_on TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    created_at DOUBLE PRECISION NOT NULL,
    claimed_by TEXT,
    lease_until DOUBLE PRECISION,
    lease_epoch INTEGER NOT NULL DEFAULT 0,
    result TEXT,
    completed_at DOUBLE PRECISION
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_dedup ON tasks(capability, dedup_key)
    WHERE dedup_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_pending ON tasks(status, priority, created_at);
CREATE TABLE IF NOT EXISTS agent_tokens (
    token_hash TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT 'read write',
    created_at DOUBLE PRECISION NOT NULL,
    revoked INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS roles (
    scope TEXT NOT NULL,
    name TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    lease_until DOUBLE PRECISION NOT NULL,
    epoch INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (scope, name)
);
CREATE TABLE IF NOT EXISTS artifacts (
    name TEXT PRIMARY KEY,
    owner TEXT NOT NULL DEFAULT '',
    channel TEXT,
    content TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'text/plain',
    version INTEGER NOT NULL DEFAULT 1,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);
CREATE TABLE IF NOT EXISTS channel_members (
    channel TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    joined_at DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (channel, agent_id)
);
CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    from_agent TEXT NOT NULL,
    to_agent TEXT,
    channel TEXT,
    body TEXT NOT NULL,
    created_at DOUBLE PRECISION NOT NULL,
    read_at DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_messages_to ON messages(to_agent, id);
CREATE INDEX IF NOT EXISTS idx_messages_channel ON messages(channel, id);
CREATE TABLE IF NOT EXISTS audit (
    id BIGSERIAL PRIMARY KEY,
    created_at DOUBLE PRECISION NOT NULL,
    actor TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    target TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS events (
    seq BIGSERIAL PRIMARY KEY,
    type TEXT NOT NULL,
    payload TEXT,
    created_at DOUBLE PRECISION NOT NULL
);
"""


def available() -> bool:
    try:
        import psycopg  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def _json(value: Any) -> str | None:
    return None if value is None else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class PgSwarmStore:
    backend = "postgres"

    def __init__(self, dsn: str) -> None:
        if not available():
            raise RuntimeError("psycopg is not installed")
        from psycopg.rows import dict_row

        self.dsn = str(dsn)
        self._row_factory = dict_row
        self.lock = threading.RLock()
        self._connect()

    def _connect(self) -> None:
        import os

        import psycopg

        attempts = max(1, int(os.environ.get("SWARMLAB_PG_ATTEMPTS", "2")))
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                self.conn = psycopg.connect(self.dsn, row_factory=self._row_factory)
                self.conn.execute("SELECT pg_advisory_xact_lock(20261119)")
                self.conn.execute(SCHEMA)
                for migration in (
                    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS expires_at DOUBLE PRECISION",
                    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS depends_on TEXT",
                    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0",
                    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 3",
                ):
                    self.conn.execute(migration)
                self.conn.execute(
                    "INSERT INTO schema_meta(id, version) VALUES (1, 16) "
                    "ON CONFLICT (id) DO UPDATE SET version=EXCLUDED.version"
                )
                self.conn.commit()
                return
            except Exception as exc:  # noqa: BLE001
                last = exc
                if attempt + 1 < attempts:
                    import time
                    time.sleep(0.1 * (attempt + 1))
        raise RuntimeError(f"PG connect failed: {last}")

    def _ensure(self) -> None:
        if getattr(self.conn, "closed", False):
            with self.lock:
                if getattr(self.conn, "closed", False):
                    self._connect()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    def _one(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        self._ensure()
        with self.lock, self.conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def _all(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        self._ensure()
        with self.lock, self.conn.cursor() as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def event(self, event_type: str, payload: dict[str, Any]) -> int:
        self._ensure()
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO events(type, payload, created_at) VALUES (%s, %s, %s) RETURNING seq",
                    (event_type, _json(payload), time.time()),
                )
                seq = int(cur.fetchone()["seq"])
            self.conn.commit()
            try:
                with self.conn.cursor() as cur:
                    cur.execute("SELECT pg_notify(%s, %s)", ("swarmlab_events", str(seq)))
                self.conn.commit()
            except Exception:  # noqa: BLE001, S110
                pass
            return seq

    def register(self, agent_id: str, capabilities: list[str], endpoint: str | None = None) -> dict[str, Any]:
        self._ensure()
        caps = sorted({str(c).strip() for c in capabilities if str(c).strip()})
        now = time.time()
        with self.lock:
            self.conn.execute(
                "INSERT INTO agents(agent_id, capabilities, endpoint, status, last_seen_at) "
                "VALUES (%s, %s, %s, 'idle', %s) ON CONFLICT(agent_id) DO UPDATE SET "
                "capabilities=EXCLUDED.capabilities, endpoint=EXCLUDED.endpoint, last_seen_at=EXCLUDED.last_seen_at",
                (agent_id, _json(caps), endpoint, now),
            )
            self.conn.commit()
        self.event("agent.registered", {"agent_id": agent_id, "capabilities": caps})
        return {"agent_id": agent_id, "capabilities": caps, "endpoint": endpoint, "last_seen_at": now}

    def heartbeat(self, agent_id: str, status: str = "idle") -> dict[str, Any]:
        now = time.time()
        with self.lock:
            row = self._one("UPDATE agents SET last_seen_at=%s, status=%s WHERE agent_id=%s RETURNING *", (now, status, agent_id))
            self.conn.commit()
        if row is None:
            raise RuntimeError(f"agent {agent_id} not found")
        return {"agent_id": agent_id, "status": status, "last_seen_at": now}

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM agents WHERE agent_id = %s", (agent_id,))
        return self._decode(row) if row else None

    def deregister(self, agent_id: str) -> dict[str, Any]:
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute("DELETE FROM agents WHERE agent_id=%s", (agent_id,))
                deleted = cur.rowcount
            self.conn.commit()
        if deleted:
            self.event("agent.deregistered", {"agent_id": agent_id})
        return {"agent_id": agent_id, "deleted": bool(deleted)}

    def discover(self, capability: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        clauses = ["last_seen_at >= %s"]
        params: list[Any] = [time.time() - 90]
        if capability:
            clauses.append("capabilities LIKE %s")
            params.append(f'%"{capability}"%')
        params.append(max(1, min(100, int(limit))))
        rows = self._all(
            "SELECT * FROM agents WHERE " + " AND ".join(clauses) + " ORDER BY last_seen_at DESC LIMIT %s",
            tuple(params),
        )
        for row in rows:
            row["capabilities"] = json.loads(row["capabilities"] or "[]")
        return rows

    def submit(self, capability: str, payload: Any = None, *, priority: int = 0,
               dedup_key: str | None = None, affinity_agent_id: str | None = None,
               ttl_s: float | None = None, depends_on: str | None = None,
               max_attempts: int = 3) -> dict[str, Any]:
        self._ensure()
        if dedup_key:
            existing = self._one("SELECT * FROM tasks WHERE capability=%s AND dedup_key=%s", (capability, dedup_key))
            if existing:
                return {**self._decode(existing), "duplicate": True}
        try:
            limit = int(__import__("os").environ.get("SWARMLAB_MAX_PENDING", "0"))
        except ValueError:
            limit = 0
        if limit > 0:
            row = self._one("SELECT COUNT(*) AS n FROM tasks WHERE status='pending'") or {}
            if int(row.get("n") or 0) >= limit:
                raise RuntimeError("BACKPRESSURE: pending tasks limit exceeded")
        task_id = _id("task")
        now = time.time()
        with self.lock:
            self.conn.execute(
                "INSERT INTO tasks(task_id, capability, payload, priority, status, dedup_key, "
                "affinity_agent_id, expires_at, depends_on, max_attempts, created_at) "
                "VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s, %s)",
                (task_id, capability, _json(payload), int(priority), dedup_key, affinity_agent_id,
                 now + max(0.0, ttl_s) if ttl_s is not None else None, depends_on,
                 max(1, int(max_attempts)), now),
            )
            self.conn.commit()
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
        self._ensure()
        now = time.time()
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE tasks SET status='failed' WHERE status='claimed' "
                    "AND lease_until IS NOT NULL AND lease_until < %s AND attempts >= max_attempts", (now,)
                )
                cur.execute(
                    "UPDATE tasks SET status='pending', claimed_by=NULL, lease_until=NULL "
                    "WHERE status='claimed' AND lease_until IS NOT NULL AND lease_until < %s "
                    "AND attempts < max_attempts", (now,)
                )
                cur.execute(
                    "UPDATE tasks SET status='expired' WHERE status='pending' AND expires_at IS NOT NULL AND expires_at < %s",
                    (now,),
                )
                clauses = [
                    "status='pending'",
                    "attempts < max_attempts",
                    "(affinity_agent_id IS NULL OR affinity_agent_id = %s)",
                    "(depends_on IS NULL OR depends_on IN (SELECT task_id FROM tasks WHERE status='completed'))",
                ]
                params: list[Any] = [agent_id]
                if capability:
                    clauses.append("capability = %s")
                    params.append(capability)
                cur.execute(
                    "SELECT * FROM tasks WHERE " + " AND ".join(clauses) +
                    " ORDER BY priority DESC, created_at LIMIT 1 FOR UPDATE SKIP LOCKED",
                    tuple(params),
                )
                row = cur.fetchone()
                if row is None:
                    self.conn.commit()
                    return None
                task_id = row["task_id"]
                cur.execute(
                    "UPDATE tasks SET status='claimed', claimed_by=%s, lease_until=%s, "
                    "lease_epoch=lease_epoch+1, attempts=attempts+1 WHERE task_id=%s",
                    (agent_id, now + max(1.0, lease_s), task_id),
                )
                cur.execute("UPDATE agents SET status='working', last_seen_at=%s WHERE agent_id=%s", (now, agent_id))
            self.conn.commit()
        self.event("task.claimed", {"task_id": task_id, "agent_id": agent_id})
        return self.get(task_id)

    def get(self, task_id: str) -> dict[str, Any] | None:
        row = self._one("SELECT * FROM tasks WHERE task_id=%s", (task_id,))
        return self._decode(row) if row else None

    def complete(self, task_id: str, agent_id: str, result: Any = None, *, success: bool = True,
                 fence: int | None = None) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            raise RuntimeError("task not found")
        if fence is not None and int(task.get("lease_epoch") or 0) != int(fence):
            raise RuntimeError("STALE_LEASE")
        if task.get("claimed_by") != agent_id:
            raise RuntimeError("FORBIDDEN")
        if task.get("status") in ("completed", "failed"):
            return {**task, "idempotent": True}
        now = time.time()
        status = "completed" if success else "failed"
        with self.lock:
            self.conn.execute(
                "UPDATE tasks SET status=%s, result=%s, completed_at=%s WHERE task_id=%s",
                (status, _json(result), now, task_id),
            )
            self.conn.execute("UPDATE agents SET status='idle', last_seen_at=%s WHERE agent_id=%s", (now, agent_id))
            self.conn.commit()
        self.event("task." + status, {"task_id": task_id, "agent_id": agent_id})
        return {"task_id": task_id, "status": status, "completed_at": now}

    def cancel(self, task_id: str, agent_id: str | None = None) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            raise RuntimeError("NOT_FOUND")
        if task.get("status") in ("completed", "failed", "cancelled"):
            return {**task, "idempotent": True}
        if agent_id and task.get("claimed_by") and task["claimed_by"] != agent_id:
            raise RuntimeError("FORBIDDEN")
        with self.lock:
            self.conn.execute("UPDATE tasks SET status='cancelled' WHERE task_id=%s", (task_id,))
            self.conn.commit()
        self.event("task.cancelled", {"task_id": task_id, "agent_id": agent_id})
        return self.get(task_id) or {"task_id": task_id, "status": "cancelled"}

    def expire(self) -> dict[str, Any]:
        now = time.time()
        with self.lock:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE tasks SET status='expired' WHERE status='pending' AND expires_at IS NOT NULL AND expires_at < %s",
                    (now,),
                )
                count = cur.rowcount
            self.conn.commit()
        if count:
            self.event("task.expired", {"count": int(count)})
        return {"expired": int(count or 0)}

    def requeue(self, task_id: str) -> dict[str, Any]:
        task = self.get(task_id)
        if not task:
            raise RuntimeError("NOT_FOUND")
        if task.get("status") not in ("cancelled", "failed"):
            raise RuntimeError(f"CONFLICT: {task.get('status')}")
        with self.lock:
            self.conn.execute(
                "UPDATE tasks SET status='pending', claimed_by=NULL, lease_until=NULL, attempts=0, "
                "result=NULL, completed_at=NULL WHERE task_id=%s",
                (task_id,),
            )
            self.conn.commit()
        self.event("task.requeued", {"task_id": task_id})
        return self.get(task_id) or {"task_id": task_id, "status": "pending"}

    def renew(self, task_id: str, agent_id: str, lease_s: float = 60.0, fence: int | None = None) -> dict[str, Any]:
        task = self.get(task_id)
        if not task or task.get("claimed_by") != agent_id:
            raise RuntimeError("FORBIDDEN")
        if fence is not None and int(task.get("lease_epoch") or 0) != int(fence):
            raise RuntimeError("STALE_LEASE")
        until = time.time() + max(1.0, lease_s)
        with self.lock:
            self.conn.execute("UPDATE tasks SET lease_until=%s WHERE task_id=%s", (until, task_id))
            self.conn.commit()
        return {"task_id": task_id, "lease_until": until}

    def tasks(self, status: str | None = None, limit: int = 50, capability: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status = %s")
            params.append(status)
        if capability:
            clauses.append("capability = %s")
            params.append(capability)
        sql = "SELECT * FROM tasks"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT %s"
        params.append(int(limit))
        return [self._decode(row) for row in self._all(sql, tuple(params))]

    def audit(self, action: str, actor: str = "", target: str = "", detail: Any = None, ip: str = "") -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO audit(created_at, actor, action, target, detail, ip) VALUES (%s, %s, %s, %s, %s, %s)",
                (time.time(), actor, action, target, json.dumps(detail or {}), ip),
            )
            self.conn.commit()

    def token_agent(self, token: str) -> str | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = self._one("SELECT agent_id FROM agent_tokens WHERE token_hash=%s AND revoked=0", (digest,))
        return str(row["agent_id"]) if row else None

    def claim_role(self, scope: str, name: str, agent_id: str, ttl_s: float = 60) -> dict[str, Any]:
        if not str(scope).strip() or not str(name).strip() or not str(agent_id).strip():
            raise SwarmError("BAD_REQUEST", "scope, name and agent_id are required")
        now = time.time()
        with self.lock:
            row = self._one("SELECT * FROM roles WHERE scope=%s AND name=%s", (str(scope), str(name)))
            if row and float(row["lease_until"]) > now and row["agent_id"] != str(agent_id):
                raise SwarmError("CONFLICT", f"role held by {row['agent_id']}")
            epoch = int(row["epoch"]) + 1 if row else 1
            self.conn.execute(
                "INSERT INTO roles(scope, name, agent_id, lease_until, epoch) VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (scope, name) DO UPDATE SET agent_id=EXCLUDED.agent_id, lease_until=EXCLUDED.lease_until, epoch=EXCLUDED.epoch",
                (str(scope), str(name), str(agent_id), now + max(1.0, float(ttl_s)), epoch),
            )
            self.conn.commit()
        return self._one("SELECT * FROM roles WHERE scope=%s AND name=%s", (str(scope), str(name))) or {}

    def renew_role(self, scope: str, name: str, agent_id: str, ttl_s: float = 60) -> dict[str, Any]:
        now = time.time()
        with self.lock:
            row = self._one("SELECT * FROM roles WHERE scope=%s AND name=%s", (str(scope), str(name)))
            if not row or row["agent_id"] != str(agent_id):
                raise SwarmError("CONFLICT", "role not held by agent")
            self.conn.execute("UPDATE roles SET lease_until=%s WHERE scope=%s AND name=%s", (now + max(1.0, float(ttl_s)), str(scope), str(name)))
            self.conn.commit()
        return self._one("SELECT * FROM roles WHERE scope=%s AND name=%s", (str(scope), str(name))) or {}

    def release_role(self, scope: str, name: str, agent_id: str) -> dict[str, Any]:
        with self.lock:
            deleted = self.conn.execute("DELETE FROM roles WHERE scope=%s AND name=%s AND agent_id=%s", (str(scope), str(name), str(agent_id))).rowcount
            self.conn.commit()
        return {"scope": scope, "name": name, "released": bool(deleted)}

    def roles(self, scope: str | None = None) -> list[dict[str, Any]]:
        if scope:
            return self._all("SELECT * FROM roles WHERE scope=%s ORDER BY name", (str(scope),))
        return self._all("SELECT * FROM roles ORDER BY scope, name")

    def put_artifact(self, name: str, content: str, owner: str = "", channel: str | None = None, content_type: str = "text/plain") -> dict[str, Any]:
        if not str(name).strip():
            raise SwarmError("BAD_REQUEST", "name is required")
        now = time.time()
        with self.lock:
            self.conn.execute(
                "INSERT INTO artifacts(name, owner, channel, content, content_type, version, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s, 1, %s, %s) ON CONFLICT (name) DO UPDATE SET "
                "owner=EXCLUDED.owner, channel=EXCLUDED.channel, content=EXCLUDED.content, "
                "content_type=EXCLUDED.content_type, version=artifacts.version+1, updated_at=EXCLUDED.updated_at",
                (str(name), owner, channel, str(content), content_type, now, now),
            )
            self.conn.commit()
        return self.get_artifact(name) or {"name": name}

    def get_artifact(self, name: str) -> dict[str, Any] | None:
        return self._one("SELECT * FROM artifacts WHERE name=%s", (str(name),))

    def list_artifacts(self, channel: str | None = None, prefix: str = "", limit: int = 100) -> list[dict[str, Any]]:
        clauses, params = [], []
        if channel:
            clauses.append("channel = %s")
            params.append(channel)
        if prefix:
            clauses.append("name LIKE %s")
            params.append(prefix + "%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(500, int(limit))))
        return self._all(f"SELECT name, owner, channel, content_type, version, updated_at FROM artifacts{where} ORDER BY name LIMIT %s", tuple(params))

    def delete_artifact(self, name: str) -> bool:
        with self.lock:
            deleted = self.conn.execute("DELETE FROM artifacts WHERE name=%s", (str(name),)).rowcount
            self.conn.commit()
        return bool(deleted)

    def join_channel(self, channel: str, agent_id: str, role: str = "member") -> dict[str, Any]:
        if not str(channel).strip():
            raise SwarmError("BAD_REQUEST", "channel is required")
        if not str(agent_id).strip():
            raise SwarmError("BAD_REQUEST", "agent_id is required")
        with self.lock:
            self.conn.execute(
                "INSERT INTO channel_members(channel, agent_id, role, joined_at) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (channel, agent_id) DO UPDATE SET role=EXCLUDED.role",
                (str(channel), str(agent_id), str(role), time.time()),
            )
            self.conn.commit()
        return self._one("SELECT * FROM channel_members WHERE channel=%s AND agent_id=%s", (str(channel), str(agent_id))) or {}

    def leave_channel(self, channel: str, agent_id: str) -> dict[str, Any]:
        with self.lock:
            deleted = self.conn.execute("DELETE FROM channel_members WHERE channel=%s AND agent_id=%s", (str(channel), str(agent_id))).rowcount
            self.conn.commit()
        return {"channel": channel, "agent_id": agent_id, "deleted": bool(deleted)}

    def channel_members(self, channel: str) -> list[dict[str, Any]]:
        return self._all("SELECT * FROM channel_members WHERE channel=%s ORDER BY joined_at", (str(channel),))

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
                    "INSERT INTO channel_members(channel, agent_id, role, joined_at) VALUES (%s, %s, 'member', %s) "
                    "ON CONFLICT (channel, agent_id) DO NOTHING",
                    (str(channel), str(from_agent), time.time()),
                )
            row = self._one(
                "INSERT INTO messages(from_agent, to_agent, channel, body, created_at) VALUES (%s, %s, %s, %s, %s) RETURNING *",
                (str(from_agent), to_agent, channel, str(body), time.time()),
            )
        return row or {"from_agent": from_agent}

    def messages(self, agent_id: str | None = None, channel: str | None = None, after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        clauses = ["id > %s"]
        params: list[Any] = [int(after)]
        if channel:
            clauses.append("channel = %s")
            params.append(channel)
        elif agent_id:
            clauses.append("(to_agent = %s OR from_agent = %s)")
            params.extend([agent_id, agent_id])
        params.append(max(1, min(500, int(limit))))
        return self._all(f"SELECT * FROM messages WHERE {' AND '.join(clauses)} ORDER BY id LIMIT %s", tuple(params))

    def mark_read(self, message_id: int, agent_id: str) -> dict[str, Any]:
        with self.lock:
            self.conn.execute("UPDATE messages SET read_at=%s WHERE id=%s AND to_agent=%s", (time.time(), int(message_id), agent_id))
            self.conn.commit()
        return {"id": int(message_id), "read": True}

    def channels(self) -> list[dict[str, Any]]:
        return self._all("SELECT channel, COUNT(*) AS n FROM messages WHERE channel IS NOT NULL GROUP BY channel ORDER BY channel")

    def issue_agent_token(self, agent_id: str, scopes: tuple[str, ...] = ("read", "write")) -> str:
        token = "agt_" + secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            self.conn.execute(
                "INSERT INTO agent_tokens(token_hash, agent_id, scopes, created_at) VALUES (%s, %s, %s, %s)",
                (digest, agent_id, " ".join(scopes), time.time()),
            )
            self.conn.commit()
        return token

    def token_scopes(self, token: str) -> set[str] | None:
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        row = self._one("SELECT scopes FROM agent_tokens WHERE token_hash=%s AND revoked=0", (digest,))
        return set(str(row["scopes"]).split()) if row else None

    def revoke_agent_tokens(self, agent_id: str) -> None:
        with self.lock:
            self.conn.execute("UPDATE agent_tokens SET revoked=1 WHERE agent_id=%s", (agent_id,))
            self.conn.commit()

    def audits(self, limit: int = 100, action: str = "", actor: str = "") -> list[dict[str, Any]]:
        where, params = "", []
        if action:
            where += " AND action = %s"
            params.append(action)
        if actor:
            where += " AND actor = %s"
            params.append(actor)
        params.append(max(1, min(500, int(limit))))
        rows = self._all(f"SELECT * FROM audit WHERE 1=1{where} ORDER BY id DESC LIMIT %s", tuple(params))
        for row in rows:
            try:
                row["detail"] = json.loads(row.get("detail") or "{}")
            except (ValueError, TypeError):
                pass
        return rows

    def task_events(self, task_id: str, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._all(
            "SELECT * FROM events WHERE payload LIKE %s ORDER BY seq DESC LIMIT %s",
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
        rows = self._all("SELECT * FROM events WHERE seq > %s ORDER BY seq LIMIT %s", (int(after), int(limit)))
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
            with self.conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM tasks WHERE status IN ('completed', 'failed', 'cancelled') "
                    "AND completed_at IS NOT NULL AND completed_at < %s", (cutoff,)
                )
                tasks = cur.rowcount
                cur.execute("DELETE FROM events WHERE created_at < %s", (cutoff,))
                events = cur.rowcount
                cur.execute("DELETE FROM audit WHERE created_at < %s", (cutoff,))
                audits = cur.rowcount
            self.conn.commit()
        return {"ok": True, "tasks": int(tasks or 0), "events": int(events or 0), "audits": int(audits or 0), "cutoff": cutoff}

    def vacuum(self) -> dict[str, Any]:
        with self.lock:
            self.conn.commit()
        return {"ok": True}

    def schema_version(self) -> int:
        row = self._one("SELECT version FROM schema_meta WHERE id=1")
        return int(row["version"]) if row else 0

    def check(self) -> dict[str, Any]:
        row = self._one("SELECT 1 AS ok")
        return {"ok": bool(row and row.get("ok") == 1)}

    def stats(self) -> dict[str, Any]:
        agents = self._one("SELECT COUNT(*) AS n FROM agents") or {}
        tasks = self._all("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status")
        events = self._one("SELECT COUNT(*) AS n, MAX(seq) AS last_seq FROM events") or {}
        return {
            "agents": int(agents.get("n") or 0),
            "tasks": {str(r["status"]): int(r["n"]) for r in tasks},
            "events": {"total": int(events.get("n") or 0), "last_seq": int(events.get("last_seq") or 0)},
        }
