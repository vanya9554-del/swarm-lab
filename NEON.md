# Neon Free migration

Neon requires an account login (GitHub/Google/email). This cannot be created
from the agent runtime without the user's consent/browser session.

## What the user does (2 minutes, $0)

1. Open https://console.neon.tech and sign up with GitHub.
2. Create project `swarmlab`, region `Frankfurt`, PostgreSQL 17.
3. Dashboard -> Connect -> copy the **pooled** connection string, e.g.
   `postgresql://user:pass@ep-...-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require`.
4. Add it as GitHub secret `NEON_DATABASE_URL` in
   `vanya9554-del/swarm-lab` -> Settings -> Secrets and variables -> Actions.
   Or send it to the agent, who will set the secret.

## Current status

A live backup was taken on 2026-11-19 (workflow `db-backup`, run 44577741742):
agents=3, tasks=1, messages=2, artifacts=1, plugins=2. The artifact is retained
for 7 days. Render PostgreSQL had to be temporarily allowlisted for GitHub
Actions (0.0.0.0/0); remove it after the Neon switch.

## What the agent does after the secret exists

Run `.github/workflows/neon-migrate.yml`:

- back up Render PostgreSQL (`pg_dump`);
- restore schema+data into Neon;
- point Render `SWARMLAB_DB` at Neon;
- deploy, verify `/ready` backend=postgres and data counts;
- keep Render PostgreSQL as fallback until verified.

Free limits (Neon Free): 0.5 GB storage, autosuspend, no 30-day deletion.
