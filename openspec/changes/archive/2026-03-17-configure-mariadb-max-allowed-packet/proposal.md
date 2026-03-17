# Proposal

## Why

Historical backfill now caches complete OpenFront game payloads, and some Team
games are large enough to exceed MariaDB's default `max_allowed_packet`. When
that happens, the local container aborts the connection and the backfill run
fails partway through hydration.

## What Changes

- Add an env-backed MariaDB startup flag in Docker Compose for
  `max_allowed_packet`.
- Document the default packet-size override in `.env.example` so operators can
  raise or lower it without editing tracked Compose files.
- Treat the local MariaDB container as a supported operational surface for
  payload-heavy backfill and replay work.

## Capabilities

### New Capabilities

- `local-mariadb-runtime`: local Docker MariaDB configuration required to
  support large cached historical game payloads

### Modified Capabilities

- None.

## Impact

- Affects `docker-compose.yml` and `.env.example`.
- Changes local operator configuration for MariaDB-backed historical backfill.
- Does not change application schemas, APIs, or ingestion logic.
