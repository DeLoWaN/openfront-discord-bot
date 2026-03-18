# Spec Delta: Guild Player Leaderboards

## MODIFIED Requirements

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

Public Team and FFA leaderboard math SHALL remain internally valid for every
published row. A row that is shown publicly SHALL NOT expose more wins than
games, SHALL NOT expose a recent-game count greater than the corresponding mode
game count, and SHALL NOT expose a win rate above `100%`.

#### Scenario: Visitor opens FFA leaderboard with valid public stats

- **WHEN** a visitor opens the FFA leaderboard for a guild
- **THEN** every published row shows a mathematically valid `Wins`, `Games`,
  `Ratio`, and `Win Rate`

#### Scenario: Stored aggregate row is invalid

- **WHEN** a stored guild aggregate row would expose more wins than games for a
  public leaderboard entry
- **THEN** the public leaderboard does not publish that invalid row as if it
  were valid competitive data

### Requirement: Expose public guild player profiles

The system SHALL expose a public player profile page within each guild site for
every player entry that appears on a guild leaderboard, including players who
have never signed in. Each profile SHALL show the player's guild-scoped Team,
FFA, and Support sections when available, SHALL omit an `overall` section, and
SHALL render the public player name without tracked guild clan-tag prefixes.
The profile SHALL also surface recent-activity metadata beside the cumulative
score sections.

Public Team and FFA profile sections SHALL obey the same validity constraints
as leaderboard rows. A published Team or FFA section SHALL NOT show more wins
than games or a win rate above `100%`.

#### Scenario: Visitor opens player profile with valid FFA section

- **WHEN** a visitor opens a public guild player profile that includes an FFA
  section
- **THEN** the profile shows mathematically valid FFA wins, games, ratio, and
  win rate values
