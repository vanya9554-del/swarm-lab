"""Minimal agent-native HTTP API: JSON, batch, SSE. No UI."""
from __future__ import annotations

import base64
import gzip
import hashlib
import hmac
import json
import os
import re
import threading
import time
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import __version__
from .mcp import McpDispatcher
from .metrics import CONTENT_TYPE as METRICS_TYPE
from .metrics import SwarmMetrics
from .openapi import spec as openapi_spec
from .store import SwarmError, SwarmStore

MAX_BODY = int(os.environ.get("SWARMLAB_MAX_BODY") or (1 << 20))
DASHBOARD = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>swarm-lab — agent-native swarm runtime</title>
<meta name="description" content="Agent-native swarm runtime: task market, leases, SSE, MCP, OpenAPI, SQLite/PostgreSQL. Built for autonomous agents.">
<meta name="keywords" content="agent-native, multi-agent, task market, MCP server, SSE, OpenAPI, SQLite, PostgreSQL, AI agents">
<meta name="robots" content="index,follow">
<link rel="canonical" href="/">
<link rel="alternate" hreflang="en" href="/">
<style>
body{font-family:system-ui,Segoe UI,Arial,sans-serif;background:#0f1420;color:#e6edf7;margin:0;padding:24px}
h1{margin:0 0 4px;font-size:26px}h2{font-size:15px;text-transform:uppercase;letter-spacing:.08em;color:#8aa4c8;margin:22px 0 10px}
.sub{color:#8aa4c8;margin-bottom:18px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.card{background:#171f30;border:1px solid #26344d;border-radius:10px;padding:14px}.card b{display:block;margin-bottom:6px}
a.btn,button{display:inline-block;margin:4px 6px 4px 0;padding:7px 11px;border-radius:7px;background:#2563eb;color:#fff;text-decoration:none;border:0;font-size:13px;cursor:pointer}
a.btn.alt{background:#25324a}a.btn.green{background:#15803d}a.btn.warn{background:#a16207}
.ok{color:#4ade80}.bad{color:#f87171}.muted{color:#8aa4c8;font-size:13px}
code{background:#0b101a;padding:2px 5px;border-radius:4px;color:#c7d7f0}
</style>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"SoftwareApplication","name":"swarm-lab","applicationCategory":"DeveloperApplication","operatingSystem":"Linux, Docker, Kubernetes","description":"Agent-native swarm runtime with task market, MCP, SSE, OpenAPI, SQLite and PostgreSQL.","softwareVersion":"__VERSION__","url":"/","sameAs":["https://github.com/vanya9554-del/swarm-lab"]}
</script>
</head><body>
<h1>swarm-lab <span class="muted">__VERSION__</span></h1>
<div class="sub">Agent-native swarm runtime · API/MCP · <span id="health">checking...</span></div>
<div class="grid">
<div class="card"><b>Local API</b>
<a class="btn" href="/ready" target="_blank">/ready</a>
<a class="btn" href="/v1/capabilities" target="_blank">/capabilities</a>
<a class="btn" href="/v1/openapi" target="_blank">/openapi</a>
<a class="btn" href="/metrics" target="_blank">/metrics</a>
<a class="btn" href="/llms.txt" target="_blank">/llms.txt</a>
<a class="btn" href="/agents.json" target="_blank">/agents.json</a>
</div>
<div class="card"><b>Agent discovery</b>
<a class="btn green" href="/llms.txt" target="_blank">LLM index</a>
<a class="btn" href="/agents.json" target="_blank">agents.json</a>
<a class="btn" href="/.well-known/ai-plugin.json" target="_blank">ai-plugin.json</a>
<a class="btn" href="/sitemap.xml" target="_blank">sitemap</a>
<div class="muted">machine-readable entry points for agents and crawlers</div>
</div>
<div class="card"><b>GitHub / CI</b>
<a class="btn" href="https://github.com/vanya9554-del/swarm-lab" target="_blank">Repository</a>
<a class="btn" href="https://github.com/vanya9554-del/swarm-lab/actions" target="_blank">Actions (12 jobs)</a>
<a class="btn" href="https://github.com/vanya9554-del/swarm-lab/releases" target="_blank">Releases</a>
<a class="btn" href="https://github.com/vanya9554-del/swarm-lab/pkgs/container/swarm-lab" target="_blank">GHCR image</a>
</div>
<div class="card"><b>Cloud</b>
<a class="btn" href="https://console.aws.amazon.com/eks/home" target="_blank">AWS EKS</a>
<a class="btn" href="https://console.cloud.google.com/kubernetes" target="_blank">GCP GKE</a>
<a class="btn" href="https://portal.azure.com/#create/Microsoft.AKS" target="_blank">Azure AKS</a>
<a class="btn" href="https://dashboard.render.com/web/srv-dbv14p0m7kps739u37ag" target="_blank">Render</a>
</div>
<div class="card"><b>KMS / secrets</b>
<a class="btn" href="https://console.aws.amazon.com/kms" target="_blank">AWS KMS</a>
<a class="btn" href="https://console.cloud.google.com/security/kms" target="_blank">GCP KMS</a>
<a class="btn" href="https://developer.hashicorp.com/vault" target="_blank">Vault</a>
<a class="btn" href="https://external-secrets.io" target="_blank">External Secrets</a>
</div>
<div class="card"><b>Docs</b>
<a class="btn green" href="https://github.com/vanya9554-del/swarm-lab/blob/main/README.md" target="_blank">README</a>
<a class="btn" href="https://github.com/vanya9554-del/swarm-lab/blob/main/START_HERE.md" target="_blank">Quick start</a>
<a class="btn" href="https://github.com/vanya9554-del/swarm-lab/blob/main/PRODUCTION.md" target="_blank">Production</a>
<a class="btn" href="https://github.com/vanya9554-del/swarm-lab/blob/main/SECURITY.md" target="_blank">Security</a>
<a class="btn" href="https://github.com/vanya9554-del/swarm-lab/blob/main/PENTEST.md" target="_blank">Pentest</a>
</div>
</div>
<script>
Promise.all([fetch('/ready').then(r=>r.json()),fetch('/v1/capabilities').then(r=>r.json())])
 .then(([r,c])=>{document.getElementById('health').innerHTML='<span class="ok">ready</span> · backend '+r.backend})
 .catch(()=>{document.getElementById('health').innerHTML='<span class="bad">not ready</span>'});
</script></body></html>"""

_JWKS_LOCK = threading.Lock()
_JWKS_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_JWKS_TTL_S = 300.0


def _fetch_jwks(url: str) -> list[dict[str, Any]]:
    now = time.time()
    with _JWKS_LOCK:
        cached = _JWKS_CACHE.get(url)
        if cached and now - cached[0] < _JWKS_TTL_S:
            return cached[1]
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    keys = data.get("keys") if isinstance(data, dict) else None
    if not isinstance(keys, list):
        return []
    result = [key for key in keys if isinstance(key, dict)]
    with _JWKS_LOCK:
        _JWKS_CACHE[url] = (now, result)
    return result
ROUTES = {
    ("GET", "/"),
    ("GET", "/llms.txt"),
    ("GET", "/robots.txt"),
    ("GET", "/sitemap.xml"),
    ("GET", "/agents.json"),
    ("GET", "/.well-known/ai-plugin.json"),
    ("GET", "/"),
    ("GET", "/llms.txt"),
    ("GET", "/robots.txt"),
    ("GET", "/sitemap.xml"),
    ("GET", "/agents.json"),
    ("GET", "/.well-known/ai-plugin.json"),
    ("GET", "/dashboard"),
    ("GET", "/health"),
    ("GET", "/ready"),
    ("GET", "/v1/stats"),
    ("GET", "/v1/version"),
    ("GET", "/v1/capabilities"),
    ("GET", "/v1/openapi"),
    ("GET", "/v1/audit"),
    ("POST", "/v1/agents"),
    ("POST", "/v1/agents/register"),
    ("DELETE", "/v1/agents/{agent_id}"),
    ("GET", "/v1/agents"),
    ("GET", "/v1/agents/{agent_id}"),
    ("POST", "/v1/heartbeat"),
    ("POST", "/v1/tasks"),
    ("POST", "/v1/tasks/{task_id}/cancel"),
    ("GET", "/v1/tasks"),
    ("POST", "/v1/messages"),
    ("GET", "/v1/messages"),
    ("GET", "/v1/messages/stream"),
    ("POST", "/v1/messages/{message_id}/read"),
    ("GET", "/v1/channels"),
    ("GET", "/v1/reputation"),
    ("GET", "/v1/reputation/{agent_id}"),
    ("POST", "/v1/reputation/feedback"),
    ("GET", "/v1/roles"),
    ("POST", "/v1/roles/claim"),
    ("POST", "/v1/roles/renew"),
    ("POST", "/v1/roles/release"),
    ("GET", "/v1/artifacts"),
    ("GET", "/v1/artifacts/{name}"),
    ("POST", "/v1/artifacts"),
    ("DELETE", "/v1/artifacts/{name}"),
    ("POST", "/v1/channels/{channel}/join"),
    ("POST", "/v1/channels/{channel}/leave"),
    ("GET", "/v1/channels/{channel}/members"),
    ("GET", "/v1/tasks/{task_id}"),
    ("GET", "/v1/tasks/{task_id}/events"),
    ("POST", "/v1/tasks/claim"),
    ("GET", "/v1/events"),
    ("GET", "/v1/stream"),
    ("POST", "/v1/batch"),
    ("POST", "/v1/maintenance/expire"),
    ("POST", "/v1/maintenance/vacuum"),
    ("POST", "/v1/maintenance/prune"),
    ("POST", "/mcp"),
    ("GET", "/metrics"),
}
ARTIFACT_RE = re.compile(r"^/v1/artifacts/([^/]+)$")
CHANNEL_RE = re.compile(r"^/v1/channels/([^/]+)/(join|leave|members)$")
MSG_READ_RE = re.compile(r"^/v1/messages/([0-9]+)/read$")
TASK_RE = re.compile(r"^/v1/tasks/([^/]+)/(complete|renew|cancel|requeue)$")


def _b64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _json(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class SwarmHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128

    def server_bind(self) -> None:
        super().server_bind()
        try:
            import socket
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        except OSError:
            pass

    def __init__(self, addr: tuple[str, int], store: SwarmStore, token: str | None = None) -> None:
        self.store = store
        self.token = token
        raw_tokens = os.environ.get("SWARMLAB_TOKENS", "").strip()
        self.tokens: dict[str, set[str]] = {}
        if raw_tokens:
            try:
                parsed = json.loads(raw_tokens)
                self.tokens = {str(k): set(v if isinstance(v, list) else [v]) for k, v in parsed.items()}
            except (ValueError, TypeError):
                self.tokens = {}
        self.mcp = McpDispatcher(store)
        self.metrics = SwarmMetrics()
        self.started_at = time.time()
        self.rate: dict[str, list[float]] = {}
        self.rate_lock = threading.Lock()
        super().__init__(addr, SwarmHandler)


class SwarmHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "swarm-lab/" + __version__

    @property
    def swarm(self) -> SwarmHTTPServer:  # type: ignore[override]
        return self.server  # type: ignore[return-value]

    def handle_one_request(self) -> None:
        self.request_id = uuid.uuid4().hex[:12]
        self.audit_actor = ""
        self.agent_id = ""
        self._started = time.perf_counter()
        super().handle_one_request()

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        if os.environ.get("SWARMLAB_LOG_FORMAT", "text") == "json":
            elapsed = round((time.perf_counter() - getattr(self, "_started", time.perf_counter())) * 1000, 3)
            print(json.dumps({
                "ts": round(time.time(), 3),
                "level": "info",
                "request_id": getattr(self, "request_id", ""),
                "remote": self.address_string(),
                "method": getattr(self, "command", ""),
                "path": getattr(self, "path", ""),
                "status": code,
                "bytes": size,
                "duration_ms": elapsed,
            }, ensure_ascii=False), flush=True)
            return
        super().log_request(code, size)

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("SWARMLAB_LOG_FORMAT", "text") == "json":
            print(json.dumps({"ts": round(time.time(), 3), "level": "info", "request_id": getattr(self, "request_id", ""), "msg": fmt % args}, ensure_ascii=False), flush=True)
            return
        if os.environ.get("SWARMLAB_LOG", "1") != "0":
            print(f"[swarmlab] {self.address_string()} {fmt % args}", flush=True)

    def _send_text(self, text: str, content_type: str) -> None:
        path = urlparse(self.path).path
        self.swarm.metrics.observe(self.command, path, 200, time.perf_counter() - getattr(self, "_started", time.perf_counter()))
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Request-Id", getattr(self, "request_id", ""))
        self.end_headers()
        if not getattr(self, "_head", False):
            self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        path = urlparse(self.path).path
        self.swarm.metrics.observe(self.command, path, 200, time.perf_counter() - getattr(self, "_started", time.perf_counter()))
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; frame-ancestors 'none'")
        self.send_header("X-Request-Id", getattr(self, "request_id", ""))
        self.end_headers()
        if not getattr(self, "_head", False):
            self.wfile.write(body)

    def _send(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
        path = urlparse(self.path).path
        self.swarm.metrics.observe(
            self.command, path, status,
            time.perf_counter() - getattr(self, "_started", time.perf_counter()),
        )
        if self.command in ("POST", "DELETE") and status < 400 and not path.startswith("/mcp"):
            self._record_audit("api.mutation", path, {"status": status})
        body = _json(payload)
        encoding = ""
        if len(body) >= 512 and "gzip" in self.headers.get("Accept-Encoding", ""):
            body = gzip.compress(body, 6)
            encoding = "gzip"
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if encoding:
            self.send_header("Content-Encoding", encoding)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.send_header("X-Request-Id", getattr(self, "request_id", ""))
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for key, value in (headers or {}).items():
            self.send_header(str(key), str(value))
        self.end_headers()
        if not getattr(self, "_head", False):
            self.wfile.write(body)

    def _rate_ok(self) -> bool:
        try:
            rps = float(os.environ.get("SWARMLAB_RATE_RPS", "0"))
        except ValueError:
            rps = 0.0
        if rps <= 0:
            return True
        now = time.time()
        key = self.headers.get("Authorization") or self.client_address[0]
        with self.swarm.rate_lock:
            bucket = [t for t in self.swarm.rate.get(key, []) if now - t < 1.0]
            if len(bucket) >= max(1, int(rps)):
                self.swarm.rate[key] = bucket
                return False
            bucket.append(now)
            self.swarm.rate[key] = bucket
        return True

    def _error(self, status: int, code: str, message: str) -> None:
        self._send(status, {"ok": False, "error": {"code": code, "message": message}})

    def _record_audit(self, action: str, target: str = "", detail: Any = None) -> None:
        try:
            self.swarm.store.audit(
                action,
                actor=getattr(self, "audit_actor", ""),
                target=target,
                detail=detail,
                ip=self.address_string(),
            )
        except Exception:  # noqa: BLE001, S110
            pass

    def _jwt_scopes(self, token: str) -> set[str] | None:
        secret = os.environ.get("SWARMLAB_JWT_SECRET", "")
        public_key = os.environ.get("SWARMLAB_JWT_PUBLIC_KEY", "")
        jwks_url = os.environ.get("SWARMLAB_JWT_JWKS_URL", "")
        if (not secret and not public_key and not jwks_url) or not token or token.count(".") != 2:
            return None
        try:
            head_b64, body_b64, sig_b64 = token.split(".")
            head = json.loads(_b64url_decode(head_b64))
            signing_input = f"{head_b64}.{body_b64}".encode()
            signature = _b64url_decode(sig_b64)
            if head.get("alg") == "HS256":
                if not secret:
                    return None
                expected = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
                if not hmac.compare_digest(expected, signature):
                    return None
            elif head.get("alg") == "RS256":
                from cryptography.hazmat.primitives import hashes
                from cryptography.hazmat.primitives.asymmetric import padding, rsa
                try:
                    if public_key:
                        from cryptography.hazmat.primitives import serialization
                        key = serialization.load_pem_public_key(public_key.encode())
                        key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
                    elif jwks_url:
                        kid = head.get("kid")
                        jwk = next(
                            (item for item in _fetch_jwks(jwks_url)
                             if item.get("kty") == "RSA" and item.get("kid") == kid),
                            None,
                        )
                        if not jwk:
                            return None
                        numbers = rsa.RSAPublicNumbers(
                            int.from_bytes(_b64url_decode(jwk["e"]), "big"),
                            int.from_bytes(_b64url_decode(jwk["n"]), "big"),
                        )
                        numbers.public_key().verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
                    else:
                        return None
                except Exception:  # noqa: BLE001
                    return None
            else:
                return None
            payload = json.loads(_b64url_decode(body_b64))
            now = int(time.time())
            if payload.get("exp") is not None and int(payload["exp"]) < now:
                return None
            if payload.get("nbf") is not None and int(payload["nbf"]) > now:
                return None
            issuer = os.environ.get("SWARMLAB_JWT_ISSUER")
            if issuer and payload.get("iss") != issuer:
                return None
            audience = os.environ.get("SWARMLAB_JWT_AUDIENCE")
            if audience:
                aud = payload.get("aud")
                if isinstance(aud, list):
                    if audience not in aud:
                        return None
                elif aud != audience:
                    return None
            raw = payload.get("scope") or payload.get("scopes") or "read write"
            scopes = set(str(raw).replace(",", " ").split())
            return scopes or None
        except (ValueError, TypeError, KeyError):
            return None

    def _auth(self) -> bool:
        header = self.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else ""
        self.audit_actor = f"token:{hashlib.sha256(token.encode()).hexdigest()[:12]}" if token else "anonymous"
        self.agent_id = self.swarm.store.token_agent(token) or ""
        jwt_scopes = self._jwt_scopes(token)
        dynamic_scopes = self.swarm.store.token_scopes(token)
        scopes: set[str] | None = None
        if self.swarm.tokens:
            scopes = set(self.swarm.tokens.get(token, set())) or None
            if scopes is None and jwt_scopes is None and dynamic_scopes is None:
                self._record_audit("auth.denied", self.path)
                self._error(401, "UNAUTHORIZED", "invalid bearer token")
                return False
        elif self.swarm.token:
            if header != f"Bearer {self.swarm.token}" and jwt_scopes is None and dynamic_scopes is None:
                self._record_audit("auth.denied", self.path)
                self._error(401, "UNAUTHORIZED", "invalid bearer token")
                return False
        elif (os.environ.get("SWARMLAB_JWT_SECRET") or os.environ.get("SWARMLAB_JWT_PUBLIC_KEY") or os.environ.get("SWARMLAB_JWT_JWKS_URL")) and jwt_scopes is None and dynamic_scopes is None:
            self._record_audit("auth.denied", self.path)
            self._error(401, "UNAUTHORIZED", "JWT required")
            return False
        if jwt_scopes is not None:
            scopes = jwt_scopes
        elif dynamic_scopes is not None:
            scopes = dynamic_scopes
        if scopes is None:
            scopes = {"read", "write"}
        needed = "write" if self.command == "POST" else "read"
        if needed not in scopes:
            self._record_audit("auth.forbidden", self.path, {"needed": needed})
            self._error(403, "FORBIDDEN", f"scope '{needed}' required")
            return False
        self.scopes = scopes
        return True

    def _body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise SwarmError("PAYLOAD_TOO_LARGE", "body > 1 MiB")
        raw = self.rfile.read(length)
        try:
            value = json.loads(raw)
        except ValueError as exc:
            raise SwarmError("BAD_JSON", "invalid JSON") from exc
        if not isinstance(value, dict):
            raise SwarmError("BAD_REQUEST", "body must be object")
        return value

    def do_HEAD(self) -> None:
        self._head = True
        try:
            self.do_GET()
        finally:
            self._head = False

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        public = path in ("/", "/dashboard", "/health", "/ready", "/metrics", "/v1/capabilities",
                          "/llms.txt", "/robots.txt", "/sitemap.xml", "/agents.json", "/.well-known/ai-plugin.json")
        if not public and not self._auth():
            return
        if not self._rate_ok():
            self._send(429, {"ok": False, "error": {"code": "RATE_LIMIT", "message": "too many requests"}}, {"Retry-After": "1"})
            return
        try:
            if path == "/llms.txt":
                base = f"{self.headers.get('X-Forwarded-Proto', 'http')}://{self.headers.get('Host', '127.0.0.1:8788')}"
                self._send_text(
                    "# swarm-lab\n\n"
                    "> Agent-native swarm runtime: task market, leases/fencing, SSE, MCP, OpenAPI, SQLite/PostgreSQL.\n\n"
                    "## API\n"
                    f"- [Health]({base}/health)\n- [Ready]({base}/ready)\n"
                    f"- [Capabilities]({base}/v1/capabilities)\n- [OpenAPI]({base}/v1/openapi)\n"
                    f"- [Agents]({base}/v1/agents)\n- [Tasks]({base}/v1/tasks)\n"
                    f"- [MCP endpoint]({base}/mcp) (POST)\n\n"
                    "## Docs\n"
                    "- https://github.com/vanya9554-del/swarm-lab\n"
                    "- https://github.com/vanya9554-del/swarm-lab/blob/main/README.md\n",
                    "text/plain; charset=utf-8",
                )
            elif path == "/robots.txt":
                base = f"{self.headers.get('X-Forwarded-Proto', 'http')}://{self.headers.get('Host', '127.0.0.1:8788')}"
                self._send_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", "text/plain; charset=utf-8")
            elif path == "/sitemap.xml":
                base = f"{self.headers.get('X-Forwarded-Proto', 'http')}://{self.headers.get('Host', '127.0.0.1:8788')}"
                urls = ["/", "/health", "/ready", "/v1/capabilities", "/v1/openapi", "/llms.txt", "/agents.json"]
                items = "".join(f"<url><loc>{base}{u}</loc></url>" for u in urls)
                self._send_text(f"<?xml version=\"1.0\" encoding=\"UTF-8\"?><urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">{items}</urlset>", "application/xml; charset=utf-8")
            elif path == "/agents.json":
                base = f"{self.headers.get('X-Forwarded-Proto', 'http')}://{self.headers.get('Host', '127.0.0.1:8788')}"
                self._send(200, {
                    "name": "swarm-lab", "version": __version__,
                    "description": "Agent-native swarm runtime: task market, leases, SSE, MCP, OpenAPI.",
                    "url": base, "openapi": f"{base}/v1/openapi", "llms": f"{base}/llms.txt",
                    "mcp": {"transport": "http", "endpoint": f"{base}/mcp"},
                    "capabilities": ["tasks", "agents", "messages", "channels", "events", "sse", "mcp", "audit", "postgres", "sqlite"],
                    "auth": ["bearer", "jwt"],
                })
            elif path == "/.well-known/ai-plugin.json":
                base = f"{self.headers.get('X-Forwarded-Proto', 'http')}://{self.headers.get('Host', '127.0.0.1:8788')}"
                self._send(200, {
                    "schema_version": "v1",
                    "name_for_model": "swarm_lab",
                    "name_for_human": "swarm-lab",
                    "description_for_model": "Agent-native task market and swarm runtime. Use /v1/tasks to submit and claim work, /v1/agents to register agents, /mcp for MCP.",
                    "description_for_human": "Task market, discovery and event exchange for autonomous agents.",
                    "auth": {"type": "user_http", "authorization_type": "bearer"},
                    "api": {"type": "openapi", "url": f"{base}/v1/openapi"},
                    "legal_info_url": "https://github.com/vanya9554-del/swarm-lab/blob/main/LICENSE",
                })
            elif path in ("/", "/dashboard"):
                self._send_html(DASHBOARD.replace("__VERSION__", __version__))
            elif path == "/v1/messages/stream":
                self._messages_stream(
                    int((query.get("after") or ["0"])[0]),
                    (query.get("agent_id") or [self.agent_id or ""])[0],
                    (query.get("channel") or [None])[0],
                    int((query.get("limit") or ["50"])[0]),
                    float((query.get("timeout_s") or ["5"])[0]),
                )
            elif path == "/v1/messages":
                self._send(200, {"ok": True, "data": self.swarm.store.messages(
                    (query.get("agent_id") or [self.agent_id or ""])[0],
                    (query.get("channel") or [None])[0],
                    int((query.get("after") or ["0"])[0]),
                    int((query.get("limit") or ["100"])[0]),
                )})
            elif path == "/v1/reputation":
                self._send(200, {"ok": True, "data": self.swarm.store.leaderboard(int((query.get("limit") or ["20"])[0]))})
            elif path.startswith("/v1/reputation/"):
                self._send(200, {"ok": True, "data": self.swarm.store.reputation(path.rsplit("/", 1)[-1])})
            elif path == "/v1/roles":
                self._send(200, {"ok": True, "data": self.swarm.store.roles((query.get("scope") or [None])[0])})
            elif path == "/v1/artifacts":
                self._send(200, {"ok": True, "data": self.swarm.store.list_artifacts(
                    (query.get("channel") or [None])[0],
                    (query.get("prefix") or [""])[0],
                    int((query.get("limit") or ["100"])[0]),
                )})
            elif path.startswith("/v1/artifacts/"):
                artifact = self.swarm.store.get_artifact(path.rsplit("/", 1)[-1])
                if artifact is None:
                    self._error(404, "NOT_FOUND", "artifact not found")
                else:
                    self._send(200, {"ok": True, "data": artifact})
            elif path.startswith("/v1/channels/") and path.endswith("/members"):
                channel = path.split("/")[3]
                self._send(200, {"ok": True, "data": self.swarm.store.channel_members(channel)})
            elif path == "/v1/channels":
                self._send(200, {"ok": True, "data": self.swarm.store.channels()})
            elif path == "/v1/audit":
                self._send(200, {"ok": True, "data": self.swarm.store.audits(
                    int((query.get("limit") or ["100"])[0]),
                    (query.get("action") or [""])[0],
                    (query.get("actor") or [""])[0],
                )})
            elif path == "/ready":
                try:
                    stats = self.swarm.store.stats()
                    check = self.swarm.store.check() if hasattr(self.swarm.store, "check") else {"ok": True}
                    self._send(200, {"ok": True, "ready": True, "backend": getattr(self.swarm.store, "backend", "sqlite"), "check": check, "stats": stats})
                except Exception as exc:  # noqa: BLE001
                    self._send(503, {"ok": False, "ready": False, "error": str(exc)})
            elif path == "/metrics":
                body = self.swarm.metrics.render(self.swarm.store).encode("utf-8")
                self.swarm.metrics.observe("GET", path, 200)
                self.send_response(200)
                self.send_header("Content-Type", METRICS_TYPE)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Request-Id", getattr(self, "request_id", ""))
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
                self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
                self.end_headers()
                if not getattr(self, "_head", False):
                    self.wfile.write(body)
            elif path == "/health":
                self._send(200, {
                    "ok": True,
                    "service": "swarm-lab",
                    "version": __version__,
                    "uptime_s": round(time.time() - self.swarm.started_at, 1),
                })
            elif path == "/v1/openapi":
                self._send(200, openapi_spec())
            elif path == "/v1/version":
                self._send(200, {"ok": True, "data": {"version": __version__, "name": "swarm-lab"}})
            elif path == "/v1/capabilities":
                self._send(200, {"ok": True, "data": {
                    "version": __version__,
                    "features": ["batch", "sse", "mcp", "postgres", "fencing", "cancel", "backpressure", "scopes"],
                    "protocol": "2024-11-05",
                }})
            elif path == "/v1/stats":
                self._send(200, {"ok": True, "data": self.swarm.store.stats()})
            elif path == "/v1/agents":
                cap = (query.get("capability") or [None])[0]
                limit = int((query.get("limit") or ["20"])[0])
                self._send(200, {"ok": True, "data": self.swarm.store.discover(cap, limit)})
            elif path.startswith("/v1/agents/"):
                agent = self.swarm.store.get_agent(path.rsplit("/", 1)[-1])
                if agent is None:
                    self._error(404, "NOT_FOUND", "agent not found")
                else:
                    self._send(200, {"ok": True, "data": agent})
            elif path == "/v1/tasks":
                status = (query.get("status") or [None])[0]
                capability = (query.get("capability") or [None])[0]
                limit = int((query.get("limit") or ["50"])[0])
                self._send(200, {"ok": True, "data": self.swarm.store.tasks(status, limit, capability)})
            elif path.startswith("/v1/tasks/") and path.endswith("/events"):
                task_id = path.split("/")[-2]
                self._send(200, {"ok": True, "data": self.swarm.store.task_events(task_id, int((query.get("limit") or ["50"])[0]))})
            elif path.startswith("/v1/tasks/"):
                task = self.swarm.store.get(path.rsplit("/", 1)[-1])
                if task is None:
                    self._error(404, "NOT_FOUND", "task not found")
                else:
                    self._send(200, {"ok": True, "data": task})
            elif path == "/v1/events":
                after = int((query.get("after") or ["0"])[0])
                limit = int((query.get("limit") or ["100"])[0])
                self._send(200, {"ok": True, "data": self.swarm.store.events(after, limit)})
            elif path == "/v1/stream":
                self._stream(
                    int((query.get("after") or ["0"])[0]),
                    int((query.get("limit") or ["50"])[0]),
                    float((query.get("timeout_s") or ["5"])[0]),
                )
            else:
                self._error(404, "NOT_FOUND", f"no route {path}")
        except SwarmError as exc:
            self._error(400 if exc.code in ("BAD_REQUEST", "BAD_JSON", "PAYLOAD_TOO_LARGE") else 409, exc.code, exc.message)
        except (ValueError, TypeError) as exc:
            self._error(400, "BAD_REQUEST", str(exc))

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/v1/agents/register":
            if not self._rate_ok():
                self._send(429, {"ok": False, "error": {"code": "RATE_LIMIT", "message": "too many requests"}}, {"Retry-After": "1"})
                return
            try:
                body = self._body()
                join = os.environ.get("SWARMLAB_JOIN_CODE", "")
                if not join:
                    raise SwarmError("FORBIDDEN", "registration is closed")
                if str(body.get("join_code") or "") != join:
                    raise SwarmError("FORBIDDEN", "invalid join code")
                caps = body.get("capabilities") or []
                if not isinstance(caps, list):
                    raise SwarmError("BAD_REQUEST", "capabilities must be array")
                agent = self.swarm.store.register(str(body.get("agent_id") or ""), caps, body.get("endpoint"))
                token = self.swarm.store.issue_agent_token(agent["agent_id"])
                self._record_audit("agent.self_registered", agent["agent_id"])
                self._send(201, {"ok": True, "data": {"agent": agent, "token": token}})
            except SwarmError as exc:
                status = 403 if exc.code == "FORBIDDEN" else 400
                self._error(status, exc.code, exc.message)
            except (ValueError, TypeError) as exc:
                self._error(400, "BAD_REQUEST", str(exc))
            return
        if not self._auth():
            return
        if not self._rate_ok():
            self._send(429, {"ok": False, "error": {"code": "RATE_LIMIT", "message": "too many requests"}}, {"Retry-After": "1"})
            return
        try:
            body = self._body()
            if path == "/v1/agents":
                caps = body.get("capabilities") or []
                if not isinstance(caps, list):
                    raise SwarmError("BAD_REQUEST", "capabilities must be array")
                data = self.swarm.store.register(str(body.get("agent_id") or ""), caps, body.get("endpoint"))
                self._send(200, {"ok": True, "data": data})
            elif path == "/v1/heartbeat":
                agent_id = str(body.get("agent_id") or "")
                if not agent_id:
                    raise SwarmError("BAD_REQUEST", "agent_id required")
                data = self.swarm.store.heartbeat(agent_id, str(body.get("status") or "idle"))
                self._send(200, {"ok": True, "data": data})
            elif path == "/v1/reputation/feedback":
                from_agent = self.agent_id or str(body.get("from_agent") or "")
                data = self.swarm.store.add_feedback(
                    from_agent, str(body.get("to_agent") or ""),
                    int(body.get("score") or 1), body.get("task_id"), str(body.get("comment") or ""),
                )
                self._send(201, {"ok": True, "data": data})
            elif path in ("/v1/roles/claim", "/v1/roles/renew", "/v1/roles/release"):
                scope = str(body.get("scope") or "global")
                name = str(body.get("name") or "")
                actor = self.agent_id or str(body.get("agent_id") or "")
                ttl = float(body.get("ttl_s") or 60)
                if path.endswith("/claim"):
                    data = self.swarm.store.claim_role(scope, name, actor, ttl)
                elif path.endswith("/renew"):
                    data = self.swarm.store.renew_role(scope, name, actor, ttl)
                else:
                    data = self.swarm.store.release_role(scope, name, actor)
                self._send(200, {"ok": True, "data": data})
            elif path == "/v1/artifacts":
                name = str(body.get("name") or "")
                owner = self.agent_id or str(body.get("owner") or "")
                data = self.swarm.store.put_artifact(
                    name, str(body.get("content") or ""), owner,
                    body.get("channel"), str(body.get("content_type") or "text/plain"),
                )
                self._send(201, {"ok": True, "data": data})
            elif path.startswith("/v1/channels/") and (path.endswith("/join") or path.endswith("/leave")):
                parts = path.split("/")
                channel, action = parts[3], parts[4]
                actor = self.agent_id or str(body.get("agent_id") or "")
                if action == "join":
                    data = self.swarm.store.join_channel(channel, actor)
                else:
                    data = self.swarm.store.leave_channel(channel, actor)
                self._send(200, {"ok": True, "data": data})
            elif path == "/v1/messages":
                from_agent = self.agent_id or str(body.get("from_agent") or "")
                data = self.swarm.store.send_message(
                    from_agent,
                    body.get("to_agent"),
                    body.get("channel"),
                    str(body.get("body") or ""),
                )
                self._send(201, {"ok": True, "data": data})
            elif path == "/v1/tasks":
                data = self.swarm.store.submit(
                    str(body.get("capability") or ""),
                    body.get("payload"),
                    priority=int(body.get("priority") or 0),
                    dedup_key=body.get("dedup_key"),
                    affinity_agent_id=body.get("affinity_agent_id"),
                    ttl_s=float(body["ttl_s"]) if body.get("ttl_s") is not None else None,
                    depends_on=body.get("depends_on"),
                    max_attempts=int(body.get("max_attempts") or 3),
                )
                self._send(200, {"ok": True, "data": data})
            elif path == "/v1/tasks/claim":
                task = self.swarm.store.claim(
                    str(body.get("agent_id") or ""),
                    body.get("capability"),
                    float(body.get("lease_s") or os.environ.get("SWARMLAB_LEASE_S") or 60),
                )
                self._send(200, {"ok": True, "data": task})
            elif path == "/mcp":
                message = body
                response = self.swarm.mcp.handle(message)
                self._send(200, response or {})
            elif path == "/v1/maintenance/prune":
                self._send(200, {"ok": True, "data": self.swarm.store.prune(float(body.get("older_than_s") or 86400))})
            elif path == "/v1/maintenance/vacuum":
                self._send(200, {"ok": True, "data": self.swarm.store.vacuum()})
            elif path == "/v1/maintenance/expire":
                self._send(200, {"ok": True, "data": self.swarm.store.expire()})
            elif path == "/v1/batch":
                ops = body.get("ops")
                if not isinstance(ops, list):
                    raise SwarmError("BAD_REQUEST", "ops must be array")
                self._send(200, {"ok": True, "data": self._batch(ops)})
            else:
                msg_match = MSG_READ_RE.match(path)
                if msg_match:
                    self._send(200, {"ok": True, "data": self.swarm.store.mark_read(
                        int(msg_match.group(1)),
                        self.agent_id or str(body.get("agent_id") or ""),
                    )})
                    return
                match = TASK_RE.match(path)
                if not match:
                    self._error(404, "NOT_FOUND", f"no route {path}")
                    return
                task_id, action = match.group(1), match.group(2)
                agent_id = str(body.get("agent_id") or "")
                fence = int(body["fence"]) if body.get("fence") is not None else None
                if action == "requeue":
                    data = self.swarm.store.requeue(task_id)
                elif action == "cancel":
                    data = self.swarm.store.cancel(task_id, agent_id or None)
                elif action == "complete":
                    data = self.swarm.store.complete(
                        task_id, agent_id, body.get("result"), success=bool(body.get("success", True)), fence=fence
                    )
                else:
                    data = self.swarm.store.renew(task_id, agent_id, float(body.get("lease_s") or 60), fence)
                self._send(200, {"ok": True, "data": data})
        except SwarmError as exc:
            status = (
                404 if exc.code == "NOT_FOUND"
                else 403 if exc.code == "FORBIDDEN"
                else 429 if exc.code == "BACKPRESSURE"
                else 409 if exc.code in ("STALE_LEASE", "CONFLICT")
                else 400
            )
            self._error(status, exc.code, exc.message)
        except (ValueError, TypeError) as exc:
            self._error(400, "BAD_REQUEST", str(exc))

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if not self._auth():
            return
        if not self._rate_ok():
            self._send(429, {"ok": False, "error": {"code": "RATE_LIMIT", "message": "too many requests"}}, {"Retry-After": "1"})
            return
        if path.startswith("/v1/artifacts/"):
            name = path.rsplit("/", 1)[-1]
            self._send(200, {"ok": True, "data": {"name": name, "deleted": self.swarm.store.delete_artifact(name)}})
            return
        if not path.startswith("/v1/agents/"):
            self._error(404, "NOT_FOUND", f"no route {path}")
            return
        agent_id = path.rsplit("/", 1)[-1]
        self._send(200, {"ok": True, "data": self.swarm.store.deregister(agent_id)})

    def _batch(self, ops: list[Any]) -> list[dict[str, Any]]:
        results = []
        for index, op in enumerate(ops[:100]):
            try:
                if not isinstance(op, dict):
                    raise SwarmError("BAD_REQUEST", "op must be object")
                name = str(op.get("op") or "")
                agent = str(op.get("agent_id") or "")
                if name == "claim":
                    data = self.swarm.store.claim(
                        agent, op.get("capability"),
                        float(op.get("lease_s") or os.environ.get("SWARMLAB_LEASE_S") or 60),
                    )
                elif name == "complete":
                    data = self.swarm.store.complete(
                        str(op.get("task_id") or ""), agent, op.get("result"),
                        fence=int(op["fence"]) if op.get("fence") is not None else None,
                    )
                elif name == "requeue":
                    data = self.swarm.store.requeue(str(op.get("task_id") or ""))
                elif name == "cancel":
                    data = self.swarm.store.cancel(str(op.get("task_id") or ""), agent or None)
                elif name == "renew":
                    data = self.swarm.store.renew(
                        str(op.get("task_id") or ""), agent, float(op.get("lease_s") or 60),
                        int(op["fence"]) if op.get("fence") is not None else None,
                    )
                elif name == "submit":
                    data = self.swarm.store.submit(
                        str(op.get("capability") or ""), op.get("payload"),
                        ttl_s=float(op["ttl_s"]) if op.get("ttl_s") is not None else None,
                        depends_on=op.get("depends_on"),
                        max_attempts=int(op.get("max_attempts") or 3),
                    )
                elif name == "events":
                    data = self.swarm.store.events(int(op.get("after") or 0), int(op.get("limit") or 100))
                elif name == "expire":
                    data = self.swarm.store.expire()
                elif name == "stats":
                    data = self.swarm.store.stats()
                else:
                    raise SwarmError("BAD_REQUEST", f"unknown op {name}")
                results.append({"index": index, "ok": True, "data": data})
            except SwarmError as exc:
                results.append({"index": index, "ok": False, "code": exc.code, "message": exc.message})
        return results

    def _messages_stream(self, after: int, agent_id: str, channel: str | None, limit: int, timeout_s: float) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        if getattr(self, "_head", False):
            self.close_connection = True
            return
        self.close_connection = True
        deadline = time.time() + min(30.0, max(0.2, timeout_s))
        keepalive_s = float(os.environ.get("SWARMLAB_STREAM_KEEPALIVE_S") or 1.0)
        last_ping = time.time()
        sent = 0
        try:
            while sent < limit and time.time() < deadline:
                rows = self.swarm.store.messages(agent_id, channel, after, min(50, limit - sent))
                for row in rows:
                    self.wfile.write(f"id: {row['id']}\ndata: {json.dumps(row, ensure_ascii=False, default=str)}\n\n".encode())
                    after = int(row["id"])
                    sent += 1
                self.wfile.flush()
                if not rows and sent < limit:
                    time.sleep(0.05)
                    if time.time() - last_ping >= keepalive_s:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_ping = time.time()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _stream(self, after: int, limit: int, timeout_s: float) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        if getattr(self, "_head", False):
            self.close_connection = True
            return
        self.close_connection = True
        deadline = time.time() + min(30.0, max(0.2, timeout_s))
        sent = 0
        keepalive_s = float(os.environ.get("SWARMLAB_STREAM_KEEPALIVE_S") or 1.0)
        last_ping = time.time()
        listener = None
        if getattr(self.swarm.store, "backend", "sqlite") == "postgres" and getattr(self.swarm.store, "dsn", ""):
            try:
                from .events import PgEventStream
                listener = PgEventStream(self.swarm.store.dsn)
            except Exception:  # noqa: BLE001
                listener = None
        try:
            while sent < limit and time.time() < deadline:
                events = self.swarm.store.events(after, min(50, limit - sent))
                for event in events:
                    self.wfile.write(f"id: {event['seq']}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n".encode())
                    after = int(event["seq"])
                    sent += 1
                self.wfile.flush()
                if not events and sent < limit:
                    if listener is not None:
                        listener.wait(0.2)
                    else:
                        time.sleep(0.05)
                    if time.time() - last_ping >= keepalive_s:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_ping = time.time()
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            if listener is not None:
                listener.close()


def build_server(store: SwarmStore, host: str = "127.0.0.1", port: int = 8788, token: str | None = None) -> SwarmHTTPServer:
    return SwarmHTTPServer((host, port), store, token)
