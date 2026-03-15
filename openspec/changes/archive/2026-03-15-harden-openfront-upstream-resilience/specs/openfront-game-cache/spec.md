# OpenFront Game Cache Delta

## MODIFIED Requirements

### Requirement: Reuse cached payloads for replay and recovery

The system SHALL reuse locally cached game payloads when reprocessing already
hydrated history so operators do not need to crawl OpenFront a second time to
repair ingestion logic or rebuild derived data. If turn-level detail has been
cached for a relevant Team game, replay SHALL use the cached turnful payload
instead of refetching the upstream detail endpoint. When ordinary backfill
flows encounter a readable cached payload from prior successful hydration, they
SHALL treat that payload as authoritative known history and SHALL NOT refetch
or reparse it. When ordinary backfill flows encounter unreadable cache for work
that still needs hydration, the system MAY invalidate that cache and refetch
upstream detail as a repair path. When explicit replay encounters unreadable
cache, it SHALL report a cache-integrity failure instead of silently performing
a new crawl.

#### Scenario: Ordinary backfill reaches readable known cache

- **WHEN** a `start` or `resume` backfill operation reaches a game whose cached
  payload is readable and was produced by prior successful hydration
- **THEN** the operation skips that game as known history without another
  upstream detail request or payload re-ingestion

#### Scenario: Replay needs Team support metrics again

- **WHEN** a replay operation rebuilds aggregates for a guild-relevant Team
  game whose turn-level detail is already cached
- **THEN** the system recomputes the support metrics from the cached payload
  without another upstream fetch

#### Scenario: Replay needs an FFA game again

- **WHEN** a replay operation rebuilds aggregates for a cached Free For All
- **THEN** the system reuses the cached turn-free payload without requiring
  turn-level data

#### Scenario: Ordinary backfill encounters unreadable cache

- **WHEN** `start` or `resume` encounters a cached game payload that is
  unreadable for work that still needs hydration
- **THEN** the system may invalidate that cache entry and refetch upstream
  detail as a repair path

#### Scenario: Replay encounters unreadable cache

- **WHEN** replay attempts to use a cached game payload that is unreadable
- **THEN** the system reports a cache-integrity failure and does not silently
  issue a new upstream fetch
