# OpenFront Game Ingestion Specification

## ADDED Requirements

### Requirement: Resolve effective clan tags for observations

For each observed session or game participant, the system SHALL determine an
effective clan tag by using the API `clanTag` when present and otherwise
parsing the first `[TAG]` token found anywhere in the username. The system
SHALL store the raw username, raw clan tag, effective clan tag, and the source
used to determine that effective clan tag.

#### Scenario: API clan tag present

- **WHEN** an observation includes a non-empty API `clanTag`
- **THEN** the system uses that value as the effective clan tag and records the
  source as the API

#### Scenario: API clan tag missing

- **WHEN** an observation has an empty or null API `clanTag` and the username
  contains `[TAG]`
- **THEN** the system uses the parsed tag as the effective clan tag and records
  the source as username parsing

### Requirement: Persist guild-relevant games and participants

The system SHALL persist observed public OpenFront games and participant data
needed to compute guild-scoped stats. A game SHALL be considered guild-relevant
for a guild when at least one participant's effective clan tag matches one of
that guild's tracked clan tags.

#### Scenario: Game relevant to one guild

- **WHEN** a game's participants match tracked clan tags for one guild only
- **THEN** the system persists the game for that guild's stats scope

#### Scenario: Game relevant to multiple guilds

- **WHEN** a game's participants match tracked clan tags from more than one
  guild
- **THEN** the system allows the same observed game to contribute to each
  matching guild scope

### Requirement: Maintain guild player aggregates from observations

The system SHALL maintain per-guild player aggregates derived from persisted
guild-relevant observations so leaderboard and public profile pages can be
served from stored guild stats rather than recalculating from raw observations
on each request.

#### Scenario: New observed win ingested

- **WHEN** a new guild-relevant observation is persisted for a player
- **THEN** the corresponding guild player aggregates are refreshed to reflect
  that observation
