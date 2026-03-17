## ADDED Requirements

### Requirement: Configure local MariaDB for large cached backfill payloads

The repository SHALL provide a Docker Compose MariaDB configuration that allows
operators to set `max_allowed_packet` through an environment variable when
running the local shared database for historical backfill and replay work. The
Compose configuration SHALL define a default packet-size override large enough
to support payload-heavy cached game inserts without requiring tracked-file
edits for ordinary local use.

#### Scenario: Operator starts local MariaDB with default settings

- **WHEN** an operator runs the repository's MariaDB Compose service without
  overriding `MARIADB_MAX_ALLOWED_PACKET`
- **THEN** the MariaDB server starts with a default `max_allowed_packet`
  override suitable for large cached backfill payloads

#### Scenario: Operator needs a larger or smaller packet limit

- **WHEN** an operator sets `MARIADB_MAX_ALLOWED_PACKET` in the environment
- **THEN** the MariaDB Compose service starts with that packet-size value
  instead of the default

### Requirement: Document the local MariaDB packet-size override

The repository SHALL document the local MariaDB packet-size environment
variable in the checked-in environment example so operators can discover and
change the setting without inspecting Compose internals.

#### Scenario: Operator reviews the example environment file

- **WHEN** an operator inspects `.env.example`
- **THEN** the file lists `MARIADB_MAX_ALLOWED_PACKET` with the repository's
  default value
