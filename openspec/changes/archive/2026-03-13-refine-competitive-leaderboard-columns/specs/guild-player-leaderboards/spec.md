# guild-player-leaderboards Specification

## MODIFIED Requirements

### Requirement: Publish a public guild leaderboard

The system SHALL expose public `Team`, `FFA`, `Overall`, and `Support`
leaderboard views for each guild. Each view SHALL use its own default ranking
field and SHALL allow visitors to sort by additional supported metrics returned
by the backend. The default visible table columns SHALL be explicit to the
active view and SHALL NOT use generic placeholder labels such as
`Primary Metric`. Each leaderboard entry SHALL still indicate whether the
profile is observed-only or linked, and the linked-versus-observed state MAY be
rendered as an inline indicator within the player cell instead of a standalone
column.

The default visible columns SHALL be:

- `Team`: `Player`, `Team Score`, `Wins`, `Win Rate`, `Games`,
  `Troops Donated`, `Support Bonus`, `Role`
- `FFA`: `Player`, `FFA Score`, `Wins`, `Win Rate`, `Games`
- `Overall`: `Player`, `Overall Score`, `Team Score`, `FFA Score`,
  `Team Games`, `FFA Games`
- `Support`: `Player`, `Troops Donated`, `Gold Donated`,
  `Donation Actions`, `Support Bonus`, `Team Games`, `Role`

#### Scenario: Visitor opens Team leaderboard

- **WHEN** a visitor opens the Team leaderboard for a guild
- **THEN** the page shows the default Team columns with explicit stat labels
  and does not show a generic `Primary Metric` header

#### Scenario: Visitor opens FFA leaderboard

- **WHEN** a visitor opens the FFA leaderboard for a guild
- **THEN** the page shows the default FFA columns with `FFA Score`, `Wins`,
  `Win Rate`, and `Games`

#### Scenario: Visitor opens Overall leaderboard

- **WHEN** a visitor opens the Overall leaderboard for a guild
- **THEN** the page shows the default Overall columns with both component mode
  scores and component mode game counts

#### Scenario: Visitor opens Support leaderboard

- **WHEN** a visitor opens the Support leaderboard for a guild
- **THEN** the page shows donation-focused columns with `Troops Donated`,
  `Gold Donated`, `Donation Actions`, `Support Bonus`, and `Role`
