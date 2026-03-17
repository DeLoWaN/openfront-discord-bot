# Design

## Context

The supported backfill path persists large cached OpenFront payloads into the
shared MariaDB database. The repository already provides a local MariaDB
container through Docker Compose, but it was still running with the server
default `max_allowed_packet`. Real backfill runs showed that this default is no
longer sufficient for some cached Team payloads, causing MariaDB to abort the
client connection during insert or update operations.

## Goals / Non-Goals

**Goals:**

- Make the local MariaDB container accept larger cached payloads during
  historical backfill.
- Keep the packet-size setting configurable through environment variables.
- Preserve the existing Compose structure and local startup flow.

**Non-Goals:**

- No application-side payload chunking or compression changes.
- No schema, ORM, or ingestion-pipeline behavior changes.
- No production deployment automation changes beyond the tracked Compose setup.

## Decisions

### 1. Configure `max_allowed_packet` through Compose server flags

Set MariaDB's packet-size limit via the existing `command` list in
`docker-compose.yml` by adding
`--max_allowed_packet=${MARIADB_MAX_ALLOWED_PACKET:-256M}`.

This keeps the configuration close to the container definition and avoids
adding a separate custom config file for one server parameter.

Alternative considered:

- mount a custom `my.cnf`: rejected because it adds another tracked file and a
  more complex override path for one operational setting

### 2. Expose the setting in `.env.example`

Add `MARIADB_MAX_ALLOWED_PACKET=256M` to `.env.example` so local operators have
an obvious documented override point.

Alternative considered:

- hardcode `256M` in Compose only: rejected because packet-size requirements
  can change with payload growth and should not require repo edits each time

## Risks / Trade-offs

- [Packet size is still too small for future payload growth] -> operators can
  raise `MARIADB_MAX_ALLOWED_PACKET` without editing Compose.
- [Larger packets increase memory pressure for the server] -> use a moderate
  default of `256M` and keep it operator-tunable.
- [This only covers environments using the tracked Compose file] -> document
  the behavior in OpenSpec so other deployment surfaces can align separately if
  needed.
