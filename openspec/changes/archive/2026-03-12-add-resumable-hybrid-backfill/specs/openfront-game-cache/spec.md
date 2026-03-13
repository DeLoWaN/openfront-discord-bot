# OpenFront Game Cache Specification

## ADDED Requirements

### Requirement: Cache turn-free game details locally

The system SHALL persist the raw payload from `/public/game/:id?turns=false`
for every hydrated historical game, regardless of whether that game currently
matches any tracked guild.

#### Scenario: Hydrated game has no matching guild

- **WHEN** a hydrated game detail does not match any tracked guild clan tags
- **THEN** the system still stores the turn-free payload in the local game
  cache

#### Scenario: Hydrated game matches one or more guilds

- **WHEN** a hydrated game detail matches tracked guild clan tags
- **THEN** the system stores the turn-free payload in the local game cache and
  uses that payload for guild-relevant ingestion

### Requirement: Reuse cached payloads for replay and recovery

The system SHALL reuse locally cached game payloads when reprocessing already
hydrated history so operators do not need to crawl OpenFront a second time to
repair ingestion logic or rebuild derived data.

#### Scenario: Cached game is requested again

- **WHEN** a backfill or replay operation needs a game whose turn-free payload
  already exists in the local cache
- **THEN** the system reuses the cached payload instead of making another
  upstream detail request

#### Scenario: Operator replays a cached historical range

- **WHEN** an operator reruns ingestion for a historical range whose games are
  already cached
- **THEN** the system rebuilds guild-relevant observations from cached payloads
  without repeating the upstream crawl

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
