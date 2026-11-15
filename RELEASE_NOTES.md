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
