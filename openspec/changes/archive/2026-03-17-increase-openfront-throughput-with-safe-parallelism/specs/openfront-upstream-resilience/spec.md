# Spec Delta: OpenFront Upstream Resilience

## MODIFIED Requirements

### Requirement: Coordinate OpenFront traffic through one shared gate

The system SHALL coordinate all OpenFront API traffic through one shared
cross-process gate backed by the shared MariaDB database. The gate SHALL allow
at most two in-flight OpenFront requests at a time across the bot, website,
worker, and historical backfill CLI, and it SHALL enforce a 0.5 second minimum
spacing between successful upstream requests when the upstream response does not
provide a longer cooldown.

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
  is provided by the upstream response
- **THEN** the shared gate records a 0.5 second cooldown before the next
  request may begin
