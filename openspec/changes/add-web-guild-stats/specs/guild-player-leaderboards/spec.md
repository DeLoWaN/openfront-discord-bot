# Guild Player Leaderboards Specification

## ADDED Requirements

### Requirement: Build guild leaderboards from guild-relevant games

The system SHALL build each guild leaderboard only from observed OpenFront
games where at least one participant has an effective clan tag that matches one
of the guild's tracked clan tags.

#### Scenario: Relevant game contributes to leaderboard

- **WHEN** an observed game contains at least one participant whose effective
  clan tag matches a tracked guild clan tag
- **THEN** the game is eligible to contribute to that guild's leaderboard

#### Scenario: Irrelevant game is excluded

- **WHEN** an observed game contains no participant whose effective clan tag
  matches a tracked guild clan tag
- **THEN** the game does not contribute to that guild's leaderboard

### Requirement: Merge observed players by username within a guild

For unlinked players, the system SHALL treat normalized username as the
observed identity key within a guild. The same normalized username appearing
under multiple tracked clan tags for the same guild SHALL be treated as one
observed player.

#### Scenario: Same username across multiple tracked tags

- **WHEN** the same normalized username appears in guild-relevant games under
  two or more tracked clan tags for the same guild
- **THEN** the system records those observations under one guild player entry

### Requirement: Publish a public guild leaderboard

The system SHALL expose a public guild leaderboard that ranks guild player
entries by guild-scoped win totals derived from guild-relevant observations.
Each leaderboard entry SHALL indicate whether the profile is observed-only or
linked.

#### Scenario: Linked player appears in leaderboard

- **WHEN** a leaderboard entry belongs to a player with a linked OpenFront
  identity
- **THEN** the public leaderboard shows that entry as linked

#### Scenario: Unlinked player appears in leaderboard

- **WHEN** a leaderboard entry belongs to a player without a linked OpenFront
  identity
- **THEN** the public leaderboard shows that entry as observed

### Requirement: Expose public guild player profiles

The system SHALL expose a public player profile page within each guild site for
every player entry that appears on the guild leaderboard, including players who
have never signed in.

#### Scenario: Visitor opens observed player profile

- **WHEN** a visitor opens a guild player profile for an observed-only player
- **THEN** the system serves the public guild-scoped profile without requiring
  authentication
