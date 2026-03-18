# guild-stats-api Specification

## Purpose

Define the guild-scoped JSON contracts used by the public guild website.
## Requirements
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
recent-game count greater than the corresponding mode game count, or a win
rate outside the inclusive range `0..1`.

#### Scenario: Client requests Team leaderboard data

- **WHEN** a client requests the `team` leaderboard view for a guild
- **THEN** the response contains Team leaderboard rows ranked by Team score and
  includes sortable Team, support, and recent-activity metrics for each row

#### Scenario: Client requests Support leaderboard data

- **WHEN** a client requests the `support` leaderboard view for a guild
- **THEN** the response contains Support leaderboard rows ranked by the
  support-view default metric and includes sortable donation and recent-activity
  metrics

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

#### Scenario: Client requests observed player profile data

- **WHEN** a client requests a guild player profile for an observed-only player
- **THEN** the response contains guild-scoped competitive sections that can be
  rendered without requiring sign-in

#### Scenario: Client requests linked player profile data

- **WHEN** a client requests a guild player profile for a linked player
- **THEN** the response contains the guild-scoped competitive sections plus any
  linked-only sections already supported for that player

#### Scenario: Client requests player profile with valid Team data

- **WHEN** a client requests a guild player profile that includes Team data
- **THEN** the response contains Team wins, games, recent-game counts, ratio,
  and win rate values that satisfy the public leaderboard math invariants

### Requirement: Expose scoring explanation data

The system SHALL expose machine-readable scoring explanation data for the Team,
FFA, and Support leaderboard views. The explanation SHALL describe the major
factors for each score in player-facing language and SHALL state that Team
match difficulty depends on team count with no hard cap at `10`. The
explanation SHALL also state that recent activity is exposed beside the score
instead of being integrated into the score itself.

#### Scenario: Client requests Team scoring explanation

- **WHEN** a client requests scoring explanation data for the Team view
- **THEN** the response states that all Team games contribute positively, wins
  add bonus value, larger lobbies count more, and support adds a visible bonus

#### Scenario: Client requests FFA scoring explanation

- **WHEN** a client requests scoring explanation data for the FFA view
- **THEN** the response states that FFA is scored separately and does not use
  support metrics

### Requirement: Expose guild-scoped public player names without tracked tags

The system SHALL expose player-name fields for public guild views using the
guild-aware public display name rather than the raw observed username.

#### Scenario: Client requests leaderboard row for tracked-tag variant

- **WHEN** a leaderboard row represents an observed player whose raw username
  includes a tracked guild clan-tag prefix
- **THEN** the API response exposes the stripped public player name instead of
  the raw tagged username

### Requirement: Expose recent-activity metadata beside cumulative scores

The system SHALL expose recent-activity fields separately from the score values
for Team, FFA, and Support views. These fields SHALL allow clients to show who
is currently active without altering the cumulative score ordering.

#### Scenario: Client requests Team leaderboard row

- **WHEN** a Team leaderboard row is returned
- **THEN** the row includes recent-activity fields such as `last_team_game_at`
  and a 30-day Team game count beside the cumulative Team score

#### Scenario: Client requests FFA leaderboard row

- **WHEN** an FFA leaderboard row is returned
- **THEN** the row includes recent-activity fields such as `last_ffa_game_at`
  and a 30-day FFA game count beside the cumulative FFA score
