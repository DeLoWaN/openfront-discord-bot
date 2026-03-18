# openfront-upstream-resilience Specification

## Purpose

TBD - created by archiving change harden-openfront-upstream-resilience.
Update Purpose after archive.

## Requirements

### Requirement: Coordinate OpenFront traffic through one shared gate

The system SHALL coordinate all OpenFront API traffic through one shared
cross-process gate backed by the shared MariaDB database unless an explicit
configured OpenFront bypass is active. Without a bypass, the gate SHALL allow
at most two in-flight OpenFront requests at a time across the bot, website,
worker, and historical backfill CLI, and it SHALL enforce the configured
minimum spacing between successful upstream requests when the upstream response
does not provide a longer cooldown. With a bypass, callers SHALL send the
configured custom header and optional `User-Agent` on every OpenFront API
request and SHALL skip client-side gate and cooldown waits.

#### Scenario: Two processes want to call OpenFront at the same time

- **WHEN** two separate processes attempt OpenFront requests concurrently
- **THEN** both requests may issue upstream without waiting for each other if
  the shared cooldown has cleared

#### Scenario: Third request arrives while two shared slots are busy

- **WHEN** two OpenFront requests are already in flight and a third request
  attempts to start
- **THEN** the third request waits until one shared gate slot is released or
  the existing lease state expires

#### Scenario: Request succeeds without upstream throttling

- **WHEN** an OpenFront request completes successfully and no longer cooldown
  is provided by the upstream response while bypass mode is not configured
- **THEN** the shared gate records the configured post-success cooldown before
  the next request may begin

#### Scenario: Bypass mode is configured

- **WHEN** the operator configures an OpenFront bypass header and value
- **THEN** every OpenFront caller sends that header and the optional configured
  `User-Agent` and does not wait on the shared gate before issuing requests

### Requirement: Honor upstream cooldown headers before retrying

The system SHALL derive OpenFront cooldown timing from upstream rate-limit
headers in this precedence order: numeric `Retry-After`, HTTP-date
`Retry-After`, standard `RateLimit-Reset`, supported vendor reset headers, and
only then a conservative local fallback. Every OpenFront caller SHALL use the
same parsing and cooldown behavior, and a `429` with an absent or zero-second
retry-after SHALL apply a configured minimum fallback cooldown when bypass mode
is not active.

#### Scenario: Numeric Retry-After is present

- **WHEN** an OpenFront response includes a numeric `Retry-After` value
- **THEN** the shared gate delays the next request by that number of seconds

#### Scenario: HTTP-date Retry-After is present

- **WHEN** an OpenFront response includes an HTTP-date `Retry-After` value
- **THEN** the shared gate delays the next request until that timestamp

#### Scenario: No retry-after value is present

- **WHEN** an OpenFront response signals a transient upstream failure without a
  usable cooldown header while bypass mode is not configured
- **THEN** the shared gate applies the configured minimum fallback cooldown
  before the next request

#### Scenario: Bypass mode still receives a 429

- **WHEN** an OpenFront request receives `429` while bypass mode is configured
- **THEN** the logs warn that the configured bypass key may be wrong instead of
  silently retrying through the ordinary cooldown loop

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
