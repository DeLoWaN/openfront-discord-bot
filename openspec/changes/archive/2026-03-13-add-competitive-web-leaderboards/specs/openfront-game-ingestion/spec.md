# openfront-game-ingestion Specification

## MODIFIED Requirements

### Requirement: Persist guild-relevant games and participants

The system SHALL persist observed public OpenFront games and participant data
needed to compute guild-scoped stats. A game SHALL be considered guild-relevant
for a guild when at least one participant's effective clan tag matches one of
that guild's tracked clan tags. For guild-relevant Team games, the system
SHALL also derive per-participant support metrics from turn data, including
exact donation totals and donation action counts. For guild-relevant Free For
All games, the system SHALL persist the mode-appropriate participant data
without requiring team support metrics.

#### Scenario: Guild-relevant Team game stores support metrics

- **WHEN** a guild-relevant Team game is ingested with turn data available
- **THEN** the system persists the game, the participants, and the derived
  donor-centric support metrics for that game's players

#### Scenario: Guild-relevant FFA game stores solo metrics

- **WHEN** a guild-relevant Free For All game is ingested
- **THEN** the system persists the game and participants without requiring Team
  donation metrics

#### Scenario: Game relevant to multiple guilds

- **WHEN** a game's participants match tracked clan tags from more than one
  guild
- **THEN** the system allows the same observed game and its derived metrics to
  contribute to each matching guild scope

### Requirement: Maintain guild player aggregates from observations

The system SHALL maintain per-guild player aggregates derived from persisted
guild-relevant observations so leaderboard and public profile pages can be
served from stored guild stats rather than recalculating from raw observations
on each request. The aggregate model SHALL maintain separate inputs for Team,
FFA, Overall, and Support views, including mode-specific game counts, win
counts, donation totals, donation action counts, and player-facing sort
metrics.

#### Scenario: New Team observation refreshes Team aggregates

- **WHEN** a new guild-relevant Team observation is persisted for a player
- **THEN** the corresponding guild player aggregates are refreshed for Team,
  Support, and Overall views

#### Scenario: New FFA observation refreshes FFA aggregates

- **WHEN** a new guild-relevant Free For All observation is persisted for a
  player
- **THEN** the corresponding guild player aggregates are refreshed for FFA and
  Overall views

### Requirement: Merge observed players across tracked clan-tag username variants

The system SHALL derive observed player identity within a guild from a
guild-aware base username rather than the raw username string. If a player's
raw username starts with a `[TAG]` prefix and that tag belongs to the guild's
tracked clan tags, the system SHALL strip that tracked prefix before deriving
the observed identity key. If the prefix does not belong to the guild's
tracked clan tags, the system SHALL leave the username untouched for identity
purposes.

#### Scenario: Tracked tag variants merge inside one guild

- **WHEN** a guild tracks both `NU` and `UN` and the observed usernames are
  `[NU] Temujin` and `[UN] Temujin`
- **THEN** the system derives the same guild-scoped observed identity for both
  rows

#### Scenario: Untracked tag variant does not merge

- **WHEN** a guild does not track `XYZ` and the observed username is
  `[XYZ] Temujin`
- **THEN** the system does not strip that prefix when deriving the observed
  identity key

## ADDED Requirements

### Requirement: Derive role-oriented metrics without territory reconstruction

The system SHALL derive support and frontline signals from stored donation and
attack metrics and SHALL NOT require reconstructing full territory ownership
history in order to score support behavior.

#### Scenario: Territory history is unavailable

- **WHEN** the system computes support and role-oriented metrics for a Team
  player
- **THEN** the calculation succeeds from stored donation and attack data
  without replaying territory state

#### Scenario: Team player has no donation events

- **WHEN** the system computes support and role-oriented metrics for a Team
  player with no donation events
- **THEN** the calculation still produces non-support metrics without requiring
  territory-derived substitutes

### Requirement: Attribute support metrics to the donor

The system SHALL attribute support totals and support actions to the player who
performed each donation intent even when the recipient identity cannot yet be
resolved to a public player entry.

#### Scenario: Donation recipient is not publicly resolvable

- **WHEN** a Team donation intent references a recipient identifier that cannot
  be matched to a public player row
- **THEN** the donation still counts toward the donor's support metrics

#### Scenario: Multiple donation events from one player

- **WHEN** one player performs multiple donation intents in a Team game
- **THEN** the system accumulates each supported donation event into that
  player's support totals
