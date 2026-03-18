## MODIFIED Requirements

### Requirement: Publish a public guild leaderboard

The system SHALL expose public `Team`, `FFA`, and `Support` leaderboard views
for each guild. Each view SHALL use its own default ranking field and SHALL
allow visitors to sort by additional supported metrics returned by the backend.
The public leaderboard SHALL use explicit view-specific column labels rather
than generic labels such as `Score` or `Support`. The public Team and FFA
leaderboards SHALL continue to expose public `ratio` and `win rate` values.

The default visible columns SHALL be:

- `Team`: `Player`, `Team Score`, `Wins`, `Win Rate`, `Games`,
  `Games 30d`, `Support Bonus`, `Role`, plus public `ratio`
- `FFA`: `Player`, `FFA Score`, `Wins`, `Win Rate`, `Games`, `Games 30d`,
  plus public `ratio`
- `Support`: `Player`, `Support Bonus`, `Troops Donated`, `Gold Donated`,
  `Donation Actions`, `Games 30d`, `Role`

Each leaderboard entry SHALL indicate whether the profile is observed-only or
linked, SHALL render the public player name without tracked guild clan-tag
prefixes, and SHALL surface recent activity beside the score rather than
embedding recency into the score itself. The `FFA` leaderboard SHALL include
only players with at least one guild-relevant FFA game and SHALL NOT list
players whose guild activity exists only in Team or Support scopes.

#### Scenario: Visitor opens Team leaderboard

- **WHEN** a visitor opens the Team leaderboard for a guild
- **THEN** the page shows the default Team columns with explicit `Team Score`
  and `Support Bonus` labels, includes the `Role` column, and keeps the public
  Team `ratio` visible

#### Scenario: Visitor opens FFA leaderboard

- **WHEN** a visitor opens the FFA leaderboard for a guild
- **THEN** the page shows the default FFA columns with an explicit `FFA Score`
  label, keeps the public FFA `ratio` visible, and includes only players with
  guild-relevant FFA participation

#### Scenario: Visitor opens Support leaderboard

- **WHEN** a visitor opens the Support leaderboard for a guild
- **THEN** the page shows support-focused columns with explicit donation metric
  labels plus the `Role` column

#### Scenario: Visitor sorts the Support leaderboard

- **WHEN** a visitor switches to the Support leaderboard and sorts by a
  supported metric such as donated troops or donated gold
- **THEN** the leaderboard reorders the same guild-scoped player rows by that
  metric and shows support-focused columns plus recent activity
