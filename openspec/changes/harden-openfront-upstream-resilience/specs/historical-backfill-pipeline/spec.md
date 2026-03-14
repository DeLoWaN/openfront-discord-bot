# Historical Backfill Pipeline Delta

## MODIFIED Requirements

### Requirement: Hydrate discovered games with bounded concurrency

The system SHALL fetch queued game details through a bounded worker pool while
routing every discovery and hydration request through the shared OpenFront
upstream gate. The shared gate SHALL be the effective upstream concurrency
limit across processes, and the pipeline SHALL track per-item success and
failure state without aborting the entire run on one transient error.

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

### Requirement: Skip previously hydrated games during ordinary backfill runs

The system SHALL treat prior successful hydration from earlier runs as known
history during ordinary `start` and `resume` backfills. When newly discovered
work overlaps games that were already hydrated successfully in an earlier run
and the cached payload is readable, the ordinary backfill pipeline SHALL
classify those games as skipped known history before any new upstream fetch or
payload re-ingestion work is attempted. Explicit `replay` remains the only
ordinary operator action that reparses known history.

#### Scenario: Start run overlaps earlier successful readable history

- **WHEN** a new backfill run discovers a game that was already hydrated
  successfully in an earlier run and its cached payload is readable
- **THEN** ordinary hydration skips that game and records it as known history
  instead of refetching or re-ingesting it

#### Scenario: Resume run encounters earlier successful readable history

- **WHEN** a resumed backfill run encounters overlap with a game that was
  already hydrated successfully in an earlier run and its cached payload is
  readable
- **THEN** the resumed run skips that game by default without reparsing it and
  preserves replay as a separate operator action

#### Scenario: Explicit replay reprocesses known history

- **WHEN** an operator explicitly requests replay for a run that references
  already hydrated games
- **THEN** the system reprocesses those games from cache instead of classifying
  them as ordinary overlap skips
