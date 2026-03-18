# Spec Delta: Historical Backfill Pipeline

## MODIFIED Requirements

### Requirement: Hydrate discovered games with bounded concurrency

The system SHALL fetch queued game details through a bounded worker pool while
routing every discovery and hydration request through the shared OpenFront
upstream gate. Historical backfill discovery SHALL use bounded concurrency that
can exploit the shared gate's two-request global limit, and the pipeline SHALL
track per-item success and failure state without aborting the entire run on one
transient error.

#### Scenario: Team and FFA discovery overlap in time

- **WHEN** ordinary historical backfill starts discovery for team and FFA
  sources
- **THEN** the pipeline may advance those discovery streams concurrently while
  still respecting the shared OpenFront gate

#### Scenario: Queued game hydration succeeds

- **WHEN** a queued game detail fetch succeeds
- **THEN** the system marks the work item complete and makes the payload
  available for ingestion

#### Scenario: Queued game hydration is rate limited

- **WHEN** a queued game detail fetch receives an upstream cooldown signal
- **THEN** later discovery and hydration work waits on the shared OpenFront
  gate before issuing another upstream request

#### Scenario: Queued game hydration fails transiently

- **WHEN** a queued game detail fetch encounters a transient upstream failure
- **THEN** the system records the failure and leaves the work item eligible for
  retry according to worker policy
