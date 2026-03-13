# openfront-game-cache Specification

## Purpose

Define how hydrated OpenFront game payloads are cached for replay, recovery,
and later aggregate rebuilds.

## Requirements

### Requirement: Cache turn-free game details locally

The system SHALL persist the raw payload from `/public/game/:id?turns=false`
for every hydrated historical game, regardless of whether that game currently
matches any tracked guild. For guild-relevant Team games that need
donation-aware scoring, the system SHALL additionally persist turn-level detail
from `/public/game/:id` so support metrics can be rebuilt locally.

#### Scenario: Hydrated game has no matching guild

- **WHEN** a hydrated game detail does not match any tracked guild clan tags
- **THEN** the system still stores the turn-free payload in the local game
  cache

#### Scenario: Guild-relevant Team game is hydrated

- **WHEN** a hydrated Team game matches one or more tracked guilds
- **THEN** the system stores the turn-free payload and the turn-level detail
  required for support scoring replay

#### Scenario: Non-Team or irrelevant game is hydrated

- **WHEN** a hydrated game is not both Team-mode and guild-relevant
- **THEN** the system still stores the turn-free payload even if no turn-level
  detail is retained

### Requirement: Reuse cached payloads for replay and recovery

The system SHALL reuse locally cached game payloads when reprocessing already
hydrated history so operators do not need to crawl OpenFront a second time to
repair ingestion logic or rebuild derived data. If turn-level detail has been
cached for a relevant Team game, replay SHALL use the cached turnful payload
instead of refetching the upstream detail endpoint.

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

### Requirement: Keep cached games separate from guild-relevant observations

The system SHALL store raw cached game details separately from guild-relevant
observed game records so cached but currently irrelevant games do not
contribute to guild stats unless later ingestion determines that they match a
guild.

#### Scenario: Cached irrelevant game remains outside leaderboard data

- **WHEN** a cached game has no participants matching any tracked guild clan
  tag
- **THEN** the game remains available for later replay but does not create
  guild leaderboard input rows

#### Scenario: Replay later makes a cached game relevant

- **WHEN** later replay rules or tracked clan tags cause a cached game to match
  a guild
- **THEN** the system ingests that cached payload into the guild-relevant
  observation tables without requiring a new upstream fetch
