# openfront-game-cache Specification

## MODIFIED Requirements

### Requirement: Cache turn-free game details locally

The system SHALL persist the raw payload from `/public/game/:id?turns=false`
for every hydrated historical game, regardless of whether that game currently
matches any tracked guild. For guild-relevant Team games that need
donation-aware scoring, the system SHALL additionally persist turn-level detail
from `/public/game/:id` so support metrics can be rebuilt locally. Cache
storage SHALL retain complete Team payloads without truncation so replay and
repair workflows can trust the stored payload.

#### Scenario: Hydrated game has no matching guild

- **WHEN** a hydrated game detail does not match any tracked guild clan tags
- **THEN** the system still stores the turn-free payload in the local game
  cache

#### Scenario: Guild-relevant Team game is hydrated

- **WHEN** a hydrated Team game matches one or more tracked guilds
- **THEN** the system stores the turn-free payload and the turn-level detail
  required for support scoring replay

#### Scenario: Guild-relevant Team payload is large

- **WHEN** a hydrated Team payload exceeds the size of prior text storage
  limits
- **THEN** the cache still retains the complete payload without truncation

#### Scenario: Non-Team or irrelevant game is hydrated

- **WHEN** a hydrated game is not both Team-mode and guild-relevant
- **THEN** the system still stores the turn-free payload even if no turn-level
  detail is retained

### Requirement: Reuse cached payloads for replay and recovery

The system SHALL reuse locally cached game payloads when reprocessing already
hydrated history so operators do not need to crawl OpenFront a second time to
repair ingestion logic or rebuild derived data. If turn-level detail has been
cached for a relevant Team game, replay SHALL use the cached turnful payload
instead of refetching the upstream detail endpoint. When ordinary backfill
flows encounter unreadable cache for work that still needs hydration, the
system MAY invalidate that cache and refetch upstream detail as a repair path.
When explicit replay encounters unreadable cache, it SHALL report a
cache-integrity failure instead of silently performing a new crawl.

#### Scenario: Cached game is requested again

- **WHEN** a backfill or replay operation needs a game whose turn-free payload
  already exists in the local cache
- **THEN** the system reuses the cached payload instead of making another
  upstream detail request

#### Scenario: Replay needs Team support metrics again

- **WHEN** a replay operation rebuilds aggregates for a guild-relevant Team
  game whose turn-level detail is already cached
- **THEN** the system recomputes the support metrics from the cached payload
  without another upstream fetch

#### Scenario: Replay needs an FFA game again

- **WHEN** a replay operation rebuilds aggregates for a cached Free For All
  game
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
