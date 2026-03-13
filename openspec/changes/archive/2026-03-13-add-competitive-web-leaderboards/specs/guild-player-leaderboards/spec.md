# guild-player-leaderboards Specification

## MODIFIED Requirements

### Requirement: Build guild leaderboards from guild-relevant games

The system SHALL build each guild leaderboard only from observed public
OpenFront games where at least one participant has an effective clan tag that
matches one of the guild's tracked clan tags. Team leaderboard inputs SHALL use
only guild-relevant Team games. FFA leaderboard inputs SHALL use only
guild-relevant Free For All games. Support leaderboard inputs SHALL use only
guild-relevant Team games with persisted support metrics. Overall leaderboard
inputs SHALL combine normalized Team and FFA scores with a Team-first target
weighting that converges toward `70% Team` and `30% FFA` only when the player
has meaningful sample sizes in both modes.

#### Scenario: Relevant Team game contributes to Team views

- **WHEN** an observed guild-relevant Team game is persisted for a player
- **THEN** that game can contribute to the player's Team, Support, and Overall
  leaderboard values

#### Scenario: Relevant FFA game contributes to solo views

- **WHEN** an observed guild-relevant Free For All game is persisted for a
  player
- **THEN** that game can contribute to the player's FFA and Overall leaderboard
  values but not to Support

#### Scenario: Irrelevant game is excluded

- **WHEN** an observed public game contains no participant whose effective clan
  tag matches a tracked guild clan tag
- **THEN** the game does not contribute to any leaderboard view for that guild

### Requirement: Publish a public guild leaderboard

The system SHALL expose public `Team`, `FFA`, `Overall`, and `Support`
leaderboard views for each guild. Each view SHALL use its own default ranking
field and SHALL allow visitors to sort by additional supported metrics returned
by the backend. Each leaderboard entry SHALL indicate whether the profile is
observed-only or linked, and SHALL render the public player name without
tracked guild clan-tag prefixes.

#### Scenario: Visitor opens Team leaderboard

- **WHEN** a visitor opens the Team leaderboard for a guild
- **THEN** the page shows rows ranked by Team score and labels each row as
  linked or observed

#### Scenario: Visitor sorts the Support leaderboard

- **WHEN** a visitor switches to the Support leaderboard and sorts by a
  supported metric such as donated troops or donated gold
- **THEN** the leaderboard reorders the same guild-scoped player rows by that
  metric

### Requirement: Expose public guild player profiles

The system SHALL expose a public player profile page within each guild site for
every player entry that appears on a guild leaderboard, including players who
have never signed in. Each profile SHALL show the player's guild-scoped Team,
FFA, Overall, and Support sections when available, and SHALL render the public
player name without tracked guild clan-tag prefixes.

#### Scenario: Visitor opens observed player profile

- **WHEN** a visitor opens a guild player profile for an observed-only player
- **THEN** the system serves the public guild-scoped competitive profile
  without requiring authentication

#### Scenario: Visitor opens linked player profile

- **WHEN** a visitor opens a guild player profile for a linked player
- **THEN** the system shows the guild-scoped competitive sections plus the
  linked-only sections already supported for that player

## ADDED Requirements

### Requirement: Explain score composition in player-facing language

The system SHALL present a concise explanation of how Team, FFA, and Overall
scores are evaluated. The Team explanation SHALL state that wins matter most,
recent matches matter more, matches with more teams count more, and donations
add a limited bonus. The Overall explanation SHALL state that it combines Team
and FFA after separate normalization, that it remains Team-first, and that a
mode with only a small sample size has reduced influence.

#### Scenario: Visitor opens Team scoring explanation

- **WHEN** a visitor opens scoring help for the Team leaderboard
- **THEN** the page explains the Team score factors without requiring the full
  internal formula to be shown

#### Scenario: Visitor opens Overall scoring explanation

- **WHEN** a visitor opens scoring help for the Overall leaderboard
- **THEN** the page states that Overall is a Team-first weighted combination of
  separately normalized Team and FFA performance, with reduced influence from
  modes where the player has only a small sample

### Requirement: Hide tracked clan tags from public player names

The system SHALL not render tracked guild clan-tag prefixes as part of the
public player name on guild leaderboard or player-profile pages.

#### Scenario: Observed player uses tracked tag prefix

- **WHEN** an observed player's raw username is `[NU] Temujin` and `NU` is a
  tracked clan tag for the guild
- **THEN** the public leaderboard and player profile render the player name as
  `Temujin`

#### Scenario: Raw username uses untracked prefix

- **WHEN** an observed player's raw username starts with a prefix that is not a
  tracked clan tag for the guild
- **THEN** the system does not strip that prefix solely for public display

### Requirement: Reward team support without penalizing frontliners

The system SHALL apply team support only as a positive adjustment to Team score
and SHALL NOT subtract points solely because a player has low donation totals.

#### Scenario: Frontliner has no support events

- **WHEN** a player contributes through Team results but has zero recorded
  donation events
- **THEN** the player's Team score is based on the non-support factors only

#### Scenario: Support player has recorded donation events

- **WHEN** a player has recorded Team donation events that qualify for the
  support adjustment
- **THEN** the player's Team score includes the support bonus in addition to
  the non-support factors
