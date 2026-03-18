# Spec Delta: Historical Backfill Pipeline

## MODIFIED Requirements

### Requirement: Skip previously hydrated games during ordinary backfill runs

The system SHALL treat prior successful hydration from earlier runs as known
history during ordinary `start` and `resume` backfills. When newly discovered
work overlaps games that were already hydrated successfully in an earlier run
and the cached payload is readable, the ordinary backfill pipeline SHALL
classify those games as skipped known history during discovery before new
hydration work is queued, fetched, or re-ingested. Explicit `replay` remains
the only ordinary operator action that reparses known history. Ordinary
hydration SHALL retain a compatibility guard that can still classify queued
rows as skipped known history before any new upstream fetch or payload
re-ingestion work is attempted.

#### Scenario: Start run overlaps earlier successful readable history

- **WHEN** a new backfill run discovers a game that was already hydrated
  successfully in an earlier run and its cached payload is readable
- **THEN** ordinary discovery excludes that game from the queued hydration set
  and records it as known history instead of refetching or re-ingesting it

#### Scenario: Resume run encounters earlier successful readable history

- **WHEN** a resumed backfill run encounters overlap with a game that was
  already hydrated successfully in an earlier run and its cached payload is
  readable
- **THEN** ordinary discovery skips that game by default before queuing new
  hydration work and preserves replay as a separate operator action

#### Scenario: Explicit replay reprocesses known history

- **WHEN** an operator explicitly requests replay for a run that references
  already hydrated games
- **THEN** the system reprocesses those games from cache instead of classifying
  them as ordinary overlap skips
