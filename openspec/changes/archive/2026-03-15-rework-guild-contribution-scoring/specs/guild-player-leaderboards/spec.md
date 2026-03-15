# guild-player-leaderboards Delta

## MODIFIED Requirements

### Requirement: Build guild leaderboards from guild-relevant games

The system SHALL build each guild leaderboard only from observed public
OpenFront games where at least one participant has an effective clan tag that
matches one of the guild's tracked clan tags. Team leaderboard inputs SHALL
use only guild-relevant Team games. FFA leaderboard inputs SHALL use only
guild-relevant Free For All games. Support leaderboard inputs SHALL use only
guild-relevant Team games with persisted support metrics. The public web
experience SHALL NOT expose an `overall` leaderboard that combines Team and
FFA.

#### Scenario: Relevant Team game contributes to Team views

- **WHEN** an observed guild-relevant Team game is persisted for a player
- **THEN** that game can contribute to the player's Team and Support
  leaderboard values

#### Scenario: Relevant FFA game contributes to solo views

- **WHEN** an observed guild-relevant Free For All game is persisted for a
  player
- **THEN** that game can contribute to the player's FFA leaderboard value but
  not to Support

#### Scenario: Irrelevant game is excluded

- **WHEN** an observed public game contains no participant whose effective clan
  tag matches a tracked guild clan tag
- **THEN** the game does not contribute to any leaderboard view for that guild

### Requirement: Publish a public guild leaderboard

The system SHALL expose public `Team`, `FFA`, and `Support` leaderboard views
for each guild. Each view SHALL use its own default ranking field and SHALL
allow visitors to sort by additional supported metrics returned by the backend.
The default visible table columns SHALL be explicit to the active view and
SHALL NOT use generic placeholder labels such as `Primary Metric`. Each
leaderboard entry SHALL indicate whether the profile is observed-only or
linked, SHALL render the public player name without tracked guild clan-tag
prefixes, and SHALL surface recent activity beside the score rather than
embedding recency into the score itself.

The default visible columns SHALL be:

- `Team`: `Player`, `Team Score`, `Wins`, `Win Rate`, `Games`,
  `Games 30d`, `Support Bonus`, `Role`
- `FFA`: `Player`, `FFA Score`, `Wins`, `Win Rate`, `Games`, `Games 30d`
- `Support`: `Player`, `Support Bonus`, `Troops Donated`, `Gold Donated`,
  `Donation Actions`, `Games 30d`, `Role`

#### Scenario: Visitor opens Team leaderboard

- **WHEN** a visitor opens the Team leaderboard for a guild
- **THEN** the page shows the default Team columns with explicit stat labels,
  does not show a generic `Primary Metric` header, and labels each row as
  linked or observed

#### Scenario: Visitor opens FFA leaderboard

- **WHEN** a visitor opens the FFA leaderboard for a guild
- **THEN** the page shows the default FFA columns with `FFA Score`, `Wins`,
  `Win Rate`, `Games`, and recent activity

#### Scenario: Visitor sorts the Support leaderboard

- **WHEN** a visitor switches to the Support leaderboard and sorts by a
  supported metric such as donated troops or donated gold
- **THEN** the leaderboard reorders the same guild-scoped player rows by that
  metric and shows support-focused columns plus recent activity

### Requirement: Expose public guild player profiles

The system SHALL expose a public player profile page within each guild site for
every player entry that appears on a guild leaderboard, including players who
have never signed in. Each profile SHALL show the player's guild-scoped Team,
FFA, and Support sections when available, SHALL omit an `overall` section, and
SHALL render the public player name without tracked guild clan-tag prefixes.
The profile SHALL also surface recent-activity metadata beside the cumulative
score sections.

#### Scenario: Visitor opens observed player profile

- **WHEN** a visitor opens a guild player profile for an observed-only player
- **THEN** the system serves the public guild-scoped competitive profile
  without requiring authentication

#### Scenario: Visitor opens linked player profile

- **WHEN** a visitor opens a guild player profile for a linked player
- **THEN** the system shows the guild-scoped competitive sections plus the
  linked-only sections already supported for that player

### Requirement: Explain score composition in player-facing language

The system SHALL present a concise explanation of how Team, FFA, and Support
scores are evaluated. The Team explanation SHALL state that every guild-relevant
Team game contributes positive score, that wins add extra value, that larger
Team lobbies count more, that win rate is a light modifier, and that support
adds a visible bonus. The explanation SHALL also state that recency is shown as
activity context and SHALL NOT describe recency as a direct score factor.

#### Scenario: Visitor opens Team scoring explanation

- **WHEN** a visitor opens scoring help for the Team leaderboard
- **THEN** the page explains that participation volume is primary, wins add
  bonus points, large Team lobbies are worth more, and support is additive

#### Scenario: Visitor opens FFA scoring explanation

- **WHEN** a visitor opens scoring help for the FFA leaderboard
- **THEN** the page explains that FFA is scored separately from Team and does
  not use support metrics

### Requirement: Reward team support without penalizing frontliners

The system SHALL apply team support only as a positive adjustment to Team score
and SHALL NOT subtract points solely because a player has low donation totals.
The support bonus SHALL remain visible as its own metric on Team and Support
views.

#### Scenario: Frontliner has no support events

- **WHEN** a player contributes through Team participation and results but has
  zero recorded donation events
- **THEN** the player's Team score is based on the non-support factors only

#### Scenario: Support player has recorded donation events

- **WHEN** a player has recorded Team donation events that qualify for the
  support adjustment
- **THEN** the player's Team score includes the support bonus in addition to
  the non-support factors
