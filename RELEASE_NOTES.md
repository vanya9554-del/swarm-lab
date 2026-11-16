# swarm-lab v5.22.0

Soak 1000/1000, 529 tasks/s; 117 tests.

# swarm-lab v5.21.0

PG filter/TTL coverage, 117 tests, 97.4%.

# swarm-lab v5.20.0

Task capability filter, 116 tests.

# swarm-lab v5.19.0

MCP stdio/error coverage, 115 tests, 97.3%.

# swarm-lab v5.18.0

PG agent profile/guards, 114 tests, 96.6%.

# swarm-lab v5.17.0

Agent profile API/MCP, 113 tests.

# swarm-lab v5.16.0

API error branches, 110 tests, 96.9%.

# swarm-lab v5.15.0

SSE disconnect coverage, 109 tests, 96.6%.

# swarm-lab v5.14.0

SWARMLAB_STREAM_KEEPALIVE_S, 108 tests.

# swarm-lab v5.13.0

SSE keepalive, 107 tests, 96.5%.

# swarm-lab v5.12.0

SWARMLAB_AGENT_TTL, 106 tests.

# swarm-lab v5.11.0

SSE listener coverage, 105 tests, 96.4%.

# swarm-lab v5.10.1

CI green: SQLite coverage >=90 + manifest validation.

# swarm-lab v5.10.0

CI gates: coverage >=90, manifest validation.

# swarm-lab v5.9.0

CI broken-pipe fix, SSE failure path, 103 tests.

# swarm-lab v5.8.0

MCP runtime exception, 102 tests.

# swarm-lab v5.7.0

Coverage 96.0%, 102 tests, API backpressure/PG unavailable.

# swarm-lab v5.6.0

Manifest validator, 100 tests.

# swarm-lab v5.5.0

SSE/PG decode coverage, 99 tests, 95.7%.

# swarm-lab v5.4.0

Harness smoke-only tests, 96 tests.

# swarm-lab v5.3.0

MCP failure paths, 96 tests.

# swarm-lab v5.2.0

SWARMLAB_LEASE_S, 96 tests.

# swarm-lab v5.1.0

PG affinity/priority, 95 tests.

# swarm-lab v5.0.0

Milestone 5.0: ROUTES/OpenAPI contract tests, 94 tests.

# swarm-lab v4.9.0

Auth/rate edge coverage, 92 tests, 95.4%.

# swarm-lab v4.8.0

README sync + store decode tests, 90 tests.

# swarm-lab v4.7.0

Coverage 95.0%, 88 tests, invalid payload decode.

# swarm-lab v4.6.0

SWARMLAB_MAX_BODY, 87 tests.

# swarm-lab v4.5.0

PG guards/backpressure, 86 tests.

# swarm-lab v4.4.0

DELETE auth coverage, 84 tests.

# swarm-lab v4.3.0

Schema migration test, coverage 94.5%, 82 tests.

# swarm-lab v4.2.0

Store guards, coverage 94.1%, 81 tests.

# swarm-lab v4.1.0

Query coverage, 80 tests.

# swarm-lab v4.0.0

Milestone 4.0: OpenAPI 3.1 discovery, 78 tests.

# swarm-lab v3.9.0

Health version/uptime, 77 tests.

# swarm-lab v3.8.0

HTTP bench 300/300, 586.7 tasks/s; 76 tests.

# swarm-lab v3.7.0

Dead-letter attempts, 74 tests.

# swarm-lab v3.6.0

Coverage 94%, 72 tests, batch maintenance.

# swarm-lab v3.5.0

PG claim guards, coverage 93.6%, 71 tests.

# swarm-lab v3.4.0

PG edge paths, coverage 93.4%, 70 tests.

# swarm-lab v3.3.0

PG edge coverage 93.1%, 69 tests.

# swarm-lab v3.2.0

Task dependencies (depends_on), 68 tests.

# swarm-lab v3.1.0

Gzip JSON responses, 65 tests.

# swarm-lab v3.0.0

Maintenance expiry, MCP swarm_expire, 64 tests.

# swarm-lab v2.9.0

Agent deregistration, 61 tests.

# swarm-lab v2.8.0

Task TTL/expiry, 58 tests.

# swarm-lab v2.7.0

Requeue API/MCP, 55 tests.

# swarm-lab v2.6.0

Retry-After on 429, 52 tests.

# swarm-lab v2.5.0

Version/capabilities discovery, 52 tests, coverage 93.2%.

# swarm-lab v2.4.0

PG K8s HPA/PDB, PG cancel, 51 tests, coverage 93.1%.

# swarm-lab v2.3.0

Task cancellation API/MCP/batch, 50 tests.

# swarm-lab v2.2.0

K8s PDB/NetworkPolicy, reconnect under load, 47 tests.

# swarm-lab v2.1.0

Coverage 93.2%, 45 tests, rate-limit/metrics edge paths.

# swarm-lab v2.0.0

Milestone 2.0: GET task by id, MCP get_task, 41 tests, coverage 92.4%.

# swarm-lab v1.9.0

Batch renew, PG SSE, coverage 92.4%, 39 tests.

# swarm-lab v1.8.0

Readiness failure handling, coverage 91.6%, 36 tests.

# swarm-lab v1.7.0

Readiness probes, public health/metrics, coverage 90.3%, 32 tests.

# swarm-lab v1.6.0

Continuous night harness, coverage 90.4%, 31 tests.

# swarm-lab v1.5.0

SQLite concurrency fix; HTTP 200/200, 726 tasks/s.

# swarm-lab v1.4.0

Transport tuning, request IDs, latency histogram, coverage 86%, 26 tests.

# swarm-lab v1.3.0

Request IDs, latency histogram, coverage 80%, 23 tests.

# swarm-lab v1.2.0

Scopes/RBAC, PG reconnect, quality gate (20 tests, 76% coverage, ruff 0).

# swarm-lab v1.1.0

Post-1.0: PG NOTIFY SSE, backpressure, chaos, compose/K8s.

# swarm-lab v1.0.0

Agent-native swarm runtime: task market, discovery, lease/fencing, SSE, batch, MCP, PostgreSQL.

## Highlights

- **Fast:** SQLite 200 tasks/8 workers → 5412 tasks/s, p50 1.088 ms, p95 2.917 ms.
- **Distributed:** PG `FOR UPDATE SKIP LOCKED`, multi-replica claim, stale-worker fencing.
- **Agent-first:** JSON API, batch 1 RTT, SSE, MCP tools/resources/prompts; **no UI**.
- **Ops:** `/metrics`, rate limit, bearer token, Docker, CI.

## Quick start

```bash
cd swarm-lab
python -m unittest discover -s tests -v
python -m swarmlab serve --port 8788
```

## Verification

- 12/12 tests (store/API/MCP/PG/load/hardening).
- Benchmark `BENCH.md`.
- ACCEPTANCE `ACCEPTANCE.md`.
- SBOM/checksums: `release/v1.0.0/`.

## Limitations

- No human UI; bearer token only; SSE polling; exactly-once side effects not guaranteed.
- GitHub push needs `gh auth login`/PAT.
