# historical-backfill-pipeline Specification

## MODIFIED Requirements

### Requirement: Persist resumable backfill progress

The system SHALL persist backfill runs and discovery cursor state so an
interrupted historical backfill can resume from the last saved position instead
of restarting from the beginning of the requested range. The persisted run
state SHALL distinguish clean completion from completion with unresolved
failures, and it SHALL expose operator-readable counters that separate ordinary
overlap skips, explicit replay work, cache-integrity failures, and other
hydration failures.

#### Scenario: Worker stops mid-backfill

- **WHEN** a historical backfill run stops after some discovery windows or
  pages have completed
- **THEN** a resumed run continues from the saved cursor state and preserves
  previously queued work

#### Scenario: Operator requests backfill status

- **WHEN** an operator inspects a historical backfill run
- **THEN** the system reports persisted lifecycle state, progress counters, and
  cursor positions for that run

#### Scenario: Run completes with unresolved failures

- **WHEN** a historical backfill finishes its pass with one or more unresolved
  cache-integrity or hydration failures
- **THEN** the persisted run outcome distinguishes that result from a clean
  fully successful completion

### Requirement: Emit progress logs for long historical runs

The system SHALL emit operator-readable progress logs for historical backfill
runs, including run start, periodic progress, cursor advancement, overlap skip
counts, replay counts, cache-integrity failures, retry or failure events, and
completion summaries.

#### Scenario: Historical run is in progress

- **WHEN** a long-running backfill continues across multiple windows or batches
- **THEN** the worker logs progress counters and the current cursor or window

#### Scenario: Historical run completes cleanly

- **WHEN** a historical backfill finishes without unresolved failures
- **THEN** the worker logs a final outcome that is clearly distinguishable from
  a completion with failures

#### Scenario: Historical run completes with failures

- **WHEN** a historical backfill finishes with unresolved cache-integrity or
  hydration failures
- **THEN** the worker logs the final run outcome and summary counters without
  implying a clean success

## ADDED Requirements

### Requirement: Skip previously hydrated games during ordinary backfill runs

The system SHALL treat prior successful hydration from earlier runs as known
history during ordinary `start` and `resume` backfills. When newly discovered
work overlaps games that were already hydrated successfully in an earlier run,
the ordinary backfill pipeline SHALL classify those games as skipped known
history rather than replaying them again.

#### Scenario: Start run overlaps earlier successful history

- **WHEN** a new backfill run discovers a game that was already hydrated
  successfully in an earlier run
- **THEN** ordinary hydration skips that game and records it as known history
  instead of re-ingesting it

#### Scenario: Resume run encounters earlier successful history

- **WHEN** a resumed backfill run encounters overlap with a game that was
  already hydrated successfully in an earlier run
- **THEN** the resumed run skips that game by default and preserves replay as a
  separate operator action

#### Scenario: Explicit replay reprocesses known history

- **WHEN** an operator explicitly requests replay for a run that references
  already hydrated games
- **THEN** the system reprocesses those games from cache instead of classifying
  them as ordinary overlap skips

### Requirement: Repair or report unreadable cached payloads by workflow

The system SHALL treat unreadable cached payloads as cache-integrity problems,
not as overlap duplicates. During ordinary `start` and `resume` flows, the
pipeline MAY repair unreadable cached payloads by invalidating that cache and
refetching upstream detail. During explicit `replay`, the pipeline SHALL
report unreadable cached payloads as replay failures without silently crawling
upstream data.

#### Scenario: Ordinary backfill encounters unreadable cached payload

- **WHEN** `start` or `resume` needs to process a queued game whose cached
  payload is unreadable
- **THEN** the system treats that cache state as repairable and may refetch the
  upstream game detail instead of classifying the game as duplicate history

#### Scenario: Replay encounters unreadable cached payload

- **WHEN** explicit replay attempts to read a cached payload that is unreadable
- **THEN** the system reports a cache-integrity replay failure and does not
  silently perform a new crawl
