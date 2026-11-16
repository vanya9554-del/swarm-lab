"""swarm-lab PostgreSQL backend (optional): multi-replica claim."""
from __future__ import annotations

import json
import threading
import time
import uuid
from typing import Any

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
                self.conn.execute(SCHEMA)
                for migration in (
                    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS expires_at DOUBLE PRECISION",
                    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS depends_on TEXT",
                    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS attempts INTEGER NOT NULL DEFAULT 0",
                    "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 3",
                ):
                    self.conn.execute(migration)
                self.conn.execute(
                    "INSERT INTO schema_meta(id, version) VALUES (1, 11) "
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

    def audits(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._all("SELECT * FROM audit ORDER BY id DESC LIMIT %s", (max(1, min(500, int(limit))),))
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
            self.conn.commit()
        return {"ok": True, "tasks": int(tasks or 0), "events": int(events or 0), "cutoff": cutoff}

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
