# guild-stats-api Specification

## ADDED Requirements

### Requirement: Expose guild-scoped leaderboard API views

The system SHALL expose machine-readable guild-scoped leaderboard endpoints for
the `team`, `ffa`, `overall`, and `support` views. Each leaderboard response
SHALL include the view identifier, the default ranking field for that view, the
numeric values needed for client-side sorting, and the player identity state
needed to label entries as linked or observed. Public player-name fields in the
response SHALL omit tracked guild clan-tag prefixes.

#### Scenario: Client requests Team leaderboard data

- **WHEN** a client requests the `team` leaderboard view for a guild
- **THEN** the response contains Team leaderboard rows ranked by Team score and
  includes sortable Team metrics for each row

#### Scenario: Client requests Support leaderboard data

- **WHEN** a client requests the `support` leaderboard view for a guild
- **THEN** the response contains Support leaderboard rows ranked by the
  support-view default metric and includes sortable donation metrics

### Requirement: Expose guild player profile API data

The system SHALL expose machine-readable guild player profile data for every
player entry that appears on a guild leaderboard. The response SHALL provide
separate Team, FFA, Overall, and Support sections when that data exists for the
player, along with linked-versus-observed state.

#### Scenario: Client requests observed player profile data

- **WHEN** a client requests a guild player profile for an observed-only player
- **THEN** the response contains guild-scoped competitive sections that can be
  rendered without requiring sign-in

#### Scenario: Client requests linked player profile data

- **WHEN** a client requests a guild player profile for a linked player
- **THEN** the response contains the guild-scoped competitive sections plus any
  linked-only sections already supported for that player

### Requirement: Expose scoring explanation data

The system SHALL expose machine-readable scoring explanation data for the Team,
FFA, and Overall leaderboard views. The explanation SHALL describe the major
factors for each score in player-facing language and SHALL state that Team
match difficulty depends on the number of teams in the match rather than the
upstream API difficulty label.

#### Scenario: Client requests Team scoring explanation

- **WHEN** a client requests scoring explanation data for the Team view
- **THEN** the response states that wins matter most, recent matches matter
  more, matches with more teams count more, and support adds a limited bonus

#### Scenario: Client requests Overall scoring explanation

- **WHEN** a client requests scoring explanation data for the Overall view
- **THEN** the response states that Overall combines Team and FFA after
  separate normalization, remains Team-first, and reduces the influence of a
  mode when the player has only a small sample in that mode

### Requirement: Expose guild-scoped public player names without tracked tags

The system SHALL expose player-name fields for public guild views using the
guild-aware public display name rather than the raw observed username.

#### Scenario: Client requests leaderboard row for tracked-tag variant

- **WHEN** a leaderboard row represents an observed player whose raw username
  includes a tracked guild clan-tag prefix
- **THEN** the API response exposes the stripped public player name instead of
  the raw tagged username
