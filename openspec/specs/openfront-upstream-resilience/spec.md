# openfront-upstream-resilience Specification

## Purpose
TBD - created by archiving change harden-openfront-upstream-resilience. Update Purpose after archive.
## Requirements
### Requirement: Coordinate OpenFront traffic through one shared gate

The system SHALL coordinate all OpenFront API traffic through one shared
cross-process gate backed by the shared MariaDB database. The gate SHALL allow
at most one in-flight OpenFront request at a time across the bot, website,
worker, and historical backfill CLI, and it SHALL enforce a one-second minimum
spacing between successful upstream requests.

#### Scenario: Two processes want to call OpenFront at the same time

- **WHEN** two separate processes attempt OpenFront requests concurrently
- **THEN** exactly one request is issued upstream first and the other waits for
  the shared lease and cooldown to clear

#### Scenario: Request succeeds without upstream throttling

- **WHEN** an OpenFront request completes successfully and no longer cooldown
  is provided by the upstream response
- **THEN** the shared gate records a one-second cooldown before the next
  OpenFront request may begin

### Requirement: Honor upstream cooldown headers before retrying

The system SHALL derive OpenFront cooldown timing from upstream rate-limit
headers in this precedence order: numeric `Retry-After`, HTTP-date
`Retry-After`, standard `RateLimit-Reset`, supported vendor reset headers, and
only then a conservative local fallback. Every OpenFront caller SHALL use the
same parsing and cooldown behavior.

#### Scenario: Numeric Retry-After is present

- **WHEN** an OpenFront response includes a numeric `Retry-After` value
- **THEN** the shared gate delays the next request by that number of seconds

#### Scenario: HTTP-date Retry-After is present

- **WHEN** an OpenFront response includes an HTTP-date `Retry-After` value
- **THEN** the shared gate delays the next request until that timestamp

#### Scenario: No retry-after value is present

- **WHEN** an OpenFront response signals a transient upstream failure without a
  usable cooldown header
- **THEN** the shared gate applies a conservative fallback delay before the
  next request

### Requirement: Survive transient shared database disconnects during gating

The system SHALL use reconnecting pooled MariaDB connections for shared
OpenFront coordination state. A transient database disconnect during OpenFront
coordination or failure recording SHALL be treated as retryable database
infrastructure failure and SHALL NOT replace the original OpenFront error in
operator-visible logs or persisted run state.

#### Scenario: Database disconnect occurs while recording an upstream failure

- **WHEN** an OpenFront request fails and the shared MariaDB connection drops
  while recording that failure
- **THEN** the original OpenFront failure remains visible and the database
  layer retries or reconnects instead of terminating the process immediately

