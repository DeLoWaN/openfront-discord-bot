# guild-player-leaderboards Specification

## MODIFIED Requirements

### Requirement: Publish a public guild leaderboard

The system SHALL expose public `Team`, `FFA`, `Overall`, and `Support`
leaderboard views for each guild. Each view SHALL use its own default ranking
field and SHALL allow visitors to sort by additional supported metrics returned
by the backend. The default visible table columns SHALL be explicit to the
active view and SHALL NOT use generic placeholder labels such as
`Primary Metric`. Each leaderboard entry SHALL indicate whether the profile is
observed-only or linked, SHALL render the public player name without tracked
guild clan-tag prefixes, and SHALL expose `support_bonus` as a visible metric
in the `Team`, `Overall`, and `Support` views.

The default visible columns SHALL be:

- `Team`: `Player`, `Team Score`, `Support Bonus`, `Wins`, `Win Rate`, `Games`,
  `Troops Donated`, `Role`
- `FFA`: `Player`, `FFA Score`, `Wins`, `Win Rate`, `Games`
- `Overall`: `Player`, `Overall Score`, `Team Score`, `FFA Score`,
  `Support Bonus`, `Team Games`, `FFA Games`
- `Support`: `Player`, `Support Bonus`, `Troops Donated`, `Gold Donated`,
  `Donation Actions`, `Team Games`, `Role`

#### Scenario: Visitor opens Overall leaderboard

- **WHEN** a visitor opens the Overall leaderboard for a guild
- **THEN** the page shows `Overall Score`, both component mode scores,
  `Support Bonus`, and the component mode game counts

#### Scenario: Visitor opens Support leaderboard

- **WHEN** a visitor opens the Support leaderboard for a guild
- **THEN** the page ranks rows by `Support Bonus` by default and still shows
  the exact donation metrics

### Requirement: Explain score composition in player-facing language

The system SHALL present a concise explanation of how Team, FFA, and Overall
scores are evaluated, and SHALL also offer an expandable exact-computation
section for visitors who want the full rules.

The Team summary SHALL state that wins matter most, harder Team lobbies count
more, stacked guild games count less, recent games matter more, losses reduce
score, and support adds a visible bonus. The Overall summary SHALL state that
it combines normalized Team and FFA scores with a Team-first target weighting
and reduced impact from small samples.

The exact-computation section SHALL describe:

- Team difficulty inference from stored game fields
- the guild-stack adjustment
- per-game recency weighting
- support bonus computation
- mode normalization and Overall confidence weighting

#### Scenario: Visitor opens Team scoring explanation

- **WHEN** a visitor opens scoring help for the Team leaderboard
- **THEN** the page shows a short summary by default and offers the exact Team
  computation in an expandable section

#### Scenario: Visitor opens Overall scoring explanation

- **WHEN** a visitor opens scoring help for the Overall leaderboard
- **THEN** the page explains that Overall is built only from normalized Team
  and FFA outputs and damped by mode confidence rather than falling back to raw
  single-mode scores

### Requirement: Reward team support without penalizing frontliners

The system SHALL apply team support only as a positive adjustment to Team score
and SHALL NOT subtract points solely because a player has low donation totals.
The visible `support_bonus` metric SHALL represent the normalized support
component that contributes to Team score.

#### Scenario: Support player has meaningful donation history

- **WHEN** a player has recorded Team donation activity that ranks strongly
  against the guild sample
- **THEN** the player's visible `support_bonus` is materially higher than a
  similarly successful frontline-only player
