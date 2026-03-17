# guild-player-leaderboards Delta

## MODIFIED Requirements

### Requirement: Publish a public guild leaderboard

The system SHALL expose public `Team`, `FFA`, and `Support` leaderboard views
for each guild. Each view SHALL use explicit stat labels, sortable columns,
visible sort direction, public `ratio` and `win rate` values, and a foldable
scoring explainer instead of a single static paragraph.

#### Scenario: Visitor sorts the Team leaderboard

- **WHEN** a visitor sorts the Team leaderboard by a supported metric
- **THEN** the page reorders the same guild-scoped rows and shows the active
  sort direction

### Requirement: Expose public guild player profiles

The system SHALL expose a public player profile page within each guild site for
every player entry that appears on a guild leaderboard. Each profile SHALL
show explicit `Wins / Games` score-note labels, the full badge catalog with
locked badges, dated progression charts, recent-performance charts, and
multi-week contribution context.

#### Scenario: Visitor opens player profile

- **WHEN** a visitor opens a guild player profile
- **THEN** the page shows full badge state, dated progression context, recent
  performance, and weekly trend data

## ADDED Requirements

### Requirement: Publish public weekly rankings

The system SHALL expose public weekly Team, FFA, and Support competition views
for each guild. These views SHALL use calendar-week UTC windows and SHALL show
leaders plus mover deltas versus the previous full week.

#### Scenario: Visitor opens weekly Support rankings

- **WHEN** a visitor opens the weekly view for Support
- **THEN** the page shows current-week support leaders and movement from the
  previous week

### Requirement: Publish public rosters under a clearer UX name

The system SHALL present `duo`, `trio`, and `quad` rankings under the public
UX label `Rosters`. Compatibility routes MAY keep `Combos` aliases, but the
primary public wording SHALL be `Rosters`.

#### Scenario: Visitor opens roster rankings

- **WHEN** a visitor opens the primary public roster view
- **THEN** the page uses `Rosters` wording while still showing `duo`, `trio`,
  and `quad` sections
