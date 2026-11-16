# Security — swarm-lab

## Аутентификация

- **Static bearer** (`SWARMLAB_TOKEN`, legacy) — один токен.
- **Multi-token/scopes** (`SWARMLAB_TOKENS='{"token":["read","write"]}'`) — RBAC: `read` для GET, `write` для POST/DELETE.
- **JWT HS256/RS256** (`SWARMLAB_JWT_SECRET` или `SWARMLAB_JWT_PUBLIC_KEY`, optional `SWARMLAB_JWT_ISSUER`/`SWARMLAB_JWT_AUDIENCE`):
  - HS256: shared secret; RS256: PEM public key (optional dependency `swarm-lab[oidc]`);
  - `exp`/`nbf`, `iss`, `aud`; scopes из `scope`/`scopes` (default `read write`);
  - RS256 подходит для OIDC-провайдера; discovery/JWKS rotation — на gateway (внешний блокер).
- Публичные: `/health`, `/ready`, `/metrics` (probes); остальное — auth.

## Транспорт

- HTTP/1.1, keep-alive, `TCP_NODELAY`, `SO_KEEPALIVE`.
- TLS — на ingress/reverse proxy (cert-manager), не в приложении.
- Security headers: `X-Content-Type-Options`, `X-Frame-Options: DENY`, CSP `default-src 'none'`, Permissions-Policy.
- Body limit (`SWARMLAB_MAX_BODY`, default 1 MiB), JSON only.
- Rate limit (`SWARMLAB_RATE_RPS`), `Retry-After`.

## Данные/секреты

- SQLite/PG; PG DSN и токены — Kubernetes Secrets/ESO, не в values.
- `prune`/`vacuum`; backup CronJob в Helm (SQLite VACUUM INTO/PG pg_dump).
- KMS/S3 — внешний блокер, не реализовано.

## Аудит/логи

- JSON access logs (`SWARMLAB_LOG_FORMAT=json`): request_id, path, status, duration.
- Prometheus alerts/SLO — `deploy/observability`.
- Отдельного immutable audit log нет; access log + events.

## Угрозы/чеклист пентеста

- [ ] TLS/ingress, HSTS на proxy
- [ ] OIDC/RS256 вместо/рядом с HS256
- [ ] Secret rotation, KMS/ESO
- [ ] Rate-limit на proxy + app
- [ ] SQL injection (параметризовано), path traversal, JSON bombs
- [ ] DoS: body limit, rate limit, thread limits
- [ ] Dependency/CVE scan (pip-audit/trivy)
- [ ] Backup restore drill
- [ ] Log redaction токенов/DSN
- [ ] Pen-test внешним исполнителем

## Reporting

При уязвимости — приватный issue/security advisory в GitHub, не публичный.
