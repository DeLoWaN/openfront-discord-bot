# Spec Delta: Guild Stats API

## MODIFIED Requirements

### Requirement: Expose guild-scoped leaderboard API views

The system SHALL expose machine-readable guild-scoped leaderboard endpoints for
the `team`, `ffa`, and `support` views. Each leaderboard response SHALL include
the view identifier, the default ranking field for that view, the numeric
values needed for client-side sorting, explicit recent-activity metadata, and
the player identity state needed to label entries as linked or observed.
Public player-name fields in the response SHALL omit tracked guild clan-tag
prefixes. The API SHALL NOT expose an `overall` leaderboard view.

For published Team and FFA rows, the API SHALL only expose mathematically valid
competitive stats. A returned row SHALL NOT expose more wins than games, a
recent-game count greater than the corresponding mode game count, or a win rate
outside the inclusive range `0..1`.

#### Scenario: Client requests FFA leaderboard data

- **WHEN** a client requests the `ffa` leaderboard view for a guild
- **THEN** the response contains only rows whose public FFA wins, games, ratio,
  recent-game count, and win rate are internally valid

#### Scenario: Stored aggregate row is invalid for a public leaderboard

- **WHEN** the API reads a stored aggregate row whose public Team or FFA stats
  would violate leaderboard math invariants
- **THEN** the API does not serialize that row as a valid public leaderboard
  entry

### Requirement: Expose guild player profile API data

The system SHALL expose machine-readable guild player profile data for every
player entry that appears on a guild leaderboard. The response SHALL provide
separate Team, FFA, and Support sections when that data exists for the player,
along with linked-versus-observed state and recent-activity metadata. The
response SHALL NOT expose an `overall` profile section.

When the API publishes Team or FFA profile data, the section SHALL obey the
same public math invariants as the corresponding leaderboard view.

#### Scenario: Client requests player profile with valid Team data

- **WHEN** a client requests a guild player profile that includes Team data
- **THEN** the response contains Team wins, games, recent-game counts, ratio,
  and win rate values that satisfy the public leaderboard math invariants
