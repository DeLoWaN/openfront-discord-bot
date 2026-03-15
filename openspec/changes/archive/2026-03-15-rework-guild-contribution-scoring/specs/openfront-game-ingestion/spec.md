# openfront-game-ingestion Delta

## MODIFIED Requirements

### Requirement: Maintain guild player aggregates from observations

The system SHALL maintain per-guild player aggregates derived from persisted
guild-relevant observations so leaderboard and public profile pages can be
served from stored guild stats rather than recalculating from raw observations
on each request. The aggregate model SHALL maintain separate inputs for Team,
FFA, and Support views, including mode-specific game counts, win counts,
donation totals, donation action counts, recent-activity metadata, and
player-facing sort metrics. The aggregate model SHALL NOT compute or persist a
public `overall` score.

#### Scenario: New Team observation refreshes Team aggregates

- **WHEN** a new guild-relevant Team observation is persisted for a player
- **THEN** the corresponding guild player aggregates are refreshed for Team and
  Support views

#### Scenario: New FFA observation refreshes FFA aggregates

- **WHEN** a new guild-relevant Free For All observation is persisted for a
  player
- **THEN** the corresponding guild player aggregates are refreshed for the FFA
  view

## ADDED Requirements

### Requirement: Compute Team score as cumulative guild contribution

The system SHALL compute Team score as a positive cumulative guild-contribution
metric. Every guild-relevant Team game SHALL add participation value. Team
wins SHALL add extra value beyond participation. Team losses SHALL NOT subtract
historical score. Team win rate SHALL act only as a light multiplier on the
positive cumulative total. `support_bonus` SHALL remain a visible additive
bonus derived from persisted donation metrics and SHALL NOT be rank-normalized
independently from the Team score.

#### Scenario: Player loses a Team game

- **WHEN** a player participates in a guild-relevant Team game and does not win
- **THEN** that game still contributes positive participation value to the
  player's cumulative Team score

#### Scenario: Player wins a Team game

- **WHEN** a player wins a guild-relevant Team game
- **THEN** that game contributes the participation value plus extra Team win
  bonus value to the player's cumulative Team score

#### Scenario: Support player donates heavily

- **WHEN** a player records strong donation totals and support share across
  Team games
- **THEN** the persisted `support_bonus` increases the player's Team score as
  a capped additive modifier

### Requirement: Value larger Team lobbies without a hard cap at ten teams

The system SHALL infer Team difficulty from stored game data and SHALL make the
Team score increase monotonically with the number of teams in the lobby. The
difficulty model MUST value a `60`-team win more than a `10`-team win, while
using damped growth so a few extreme lobbies do not dominate the entire
leaderboard.

#### Scenario: Large Team lobby is ingested

- **WHEN** a guild-relevant Team game is inferred to have more than `10` teams
- **THEN** the Team contribution model applies a higher difficulty value than
  it would for a `10`-team game

#### Scenario: Difficulty grows without exploding

- **WHEN** the system compares two Team wins from different lobby sizes
- **THEN** the larger lobby win is worth more, but the growth remains damped
  rather than linearly exploding with team count

### Requirement: Surface recency as metadata instead of score decay

The system SHALL persist recent-activity metadata beside the cumulative Team
and FFA scores. The aggregate recomputation SHALL maintain timestamps and
recent-game counters without using them to decay the main Team or FFA score.

#### Scenario: Player has not played recently

- **WHEN** a player has not played for many weeks
- **THEN** the stored cumulative Team score remains unchanged while the recent
  activity metadata reflects the inactivity

#### Scenario: Player is currently active

- **WHEN** a player has played many recent Team or FFA games
- **THEN** the stored recent-activity metadata reflects that activity beside
  the cumulative score
