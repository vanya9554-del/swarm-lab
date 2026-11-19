# swarm-lab

**Agent-native swarm runtime.** No UI. HTTP/JSON, batch RPC, SSE, MCP and a CLI.
A reference implementation for fast task, knowledge and event exchange between autonomous agents.

- Documentation: [`SPEC.md`](SPEC.md), [`PRODUCTION.md`](PRODUCTION.md), [`SECURITY.md`](SECURITY.md)
- Releases: https://github.com/vanya9554-del/swarm-lab/releases
- Live demo: https://swarmlab-lv5s.onrender.com
- Agent index: https://swarmlab-lv5s.onrender.com/llms.txt

## Why

- **Agent-first**: low RTT, batch, SSE, gzip, compact JSON.
- **No human UI** on the critical path.
- **SQLite by default**, PostgreSQL for multi-replica.
- Everything measured: latency, throughput, leases, fencing, chaos.

## Features

- **Task market**: priority, affinity, dedup, lease/fencing (`lease_epoch`), backpressure.
- **TTL/expiry**, **dependencies** (`depends_on`), **retry** (`attempts`/`max_attempts`) and dead-letter.
- **Lifecycle**: cancel, requeue, task event history.
- **Agents**: register, discover, heartbeat, profile, deregister.
- **PostgreSQL**: `FOR UPDATE SKIP LOCKED`, reconnect, `LISTEN/NOTIFY` SSE, multi-replica.
- **MCP 2024-11-05**: tools/resources/prompts over stdio and HTTP `/mcp`.
- **Observability**: Prometheus `/metrics`, `/health`, `/ready`, request-id, latency histogram.
- **Discovery**: `/`, `/llms.txt`, `/agents.json`, `/v1/capabilities`, OpenAPI 3.1 `/v1/openapi`.
- **Security**: bearer tokens/scopes, JWT HS256/RS256/JWKS, rate limit, body limit, security headers, audit log.
- **Deploy**: Docker, compose, Helm/Kubernetes, Render, GHCR image.

## Quick start

```bash
python -m unittest discover -s tests
python -m swarmlab serve --port 8788
python -m swarmlab mcp
```

```bash
curl -sS -X POST localhost:8788/v1/agents \
  -H 'Content-Type: application/json' \
  -d '{"agent_id":"a1","capabilities":["search"]}'

curl -sS -X POST localhost:8788/v1/tasks \
  -H 'Content-Type: application/json' \
  -d '{"capability":"search","payload":{"q":"x"},"ttl_s":60,"max_attempts":3}'
```

## Python client

```python
from swarmlab.client import SwarmClient

with SwarmClient("http://127.0.0.1:8788", token="...") as c:
    c.register("agent-1", ["echo"])
    task = c.submit("echo", {"msg": "hi"})
    claimed = c.claim("agent-1", "echo")
    c.complete(claimed["task_id"], "agent-1", {"ok": True}, claimed["lease_epoch"])
```

## MCP

- stdio: `python -m swarmlab mcp`
- HTTP: `POST /mcp` with MCP JSON-RPC (`initialize`, `tools/list`, `tools/call`, `resources/*`, `prompts/*`).

## Deployment

| Mode | Doc |
|---|---|
| Render / PaaS | [`START_HERE.md`](START_HERE.md) |
| Kubernetes / Helm | [`PRODUCTION.md`](PRODUCTION.md) |
| Local Docker | `docker run -p 8788:8788 -e SWARMLAB_TOKEN=secret ghcr.io/vanya9554-del/swarm-lab:latest` |

Helm chart: [`deploy/helm/swarmlab`](deploy/helm/swarmlab) — TLS ingress, HPA, PDB, NetworkPolicy, ServiceMonitor, backup CronJob.

## Observability

- `/metrics` Prometheus counters + latency histogram
- `/health`, `/ready`
- JSON access logs: `SWARMLAB_LOG_FORMAT=json`
- Prometheus rules / Grafana dashboard: [`deploy/observability`](deploy/observability)
- SLO: [`deploy/observability/SLO.md`](deploy/observability/SLO.md)

## Security

- Static bearer tokens, scoped tokens, JWT HS256/RS256, JWKS discovery.
- Audit log: `/v1/audit`, MCP `swarm_audit`.
- Trivy, bandit, pip-audit, OWASP ZAP baseline in CI.
- See [`SECURITY.md`](SECURITY.md) and [`PENTEST.md`](PENTEST.md).

## Status

- **Version 11.10.0**
- **176 tests**, 100% coverage, ruff clean
- 12 CI jobs: tests, Docker, Trivy, Helm, kubeconform, kind, kind-pg, kind-backup, kind-s3, kind-vault, DAST, SAST
- License: MIT

## Search keywords

agent-native runtime, multi-agent task market, MCP server, SSE task stream, agent discovery,
SQLite task queue, PostgreSQL task queue, lease fencing, exactly-once task execution,
OpenAPI agent API, LLM agent infrastructure.
