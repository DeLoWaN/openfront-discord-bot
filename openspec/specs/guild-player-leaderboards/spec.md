# guild-player-leaderboards Specification

## Purpose

Define the guild-scoped public leaderboard and player profile behavior for the
competitive web experience.

## Requirements

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

Public Team and FFA leaderboard math SHALL remain internally valid for every
published row. A row that is shown publicly SHALL NOT expose more wins than
games, SHALL NOT expose a recent-game count greater than the corresponding
mode game count, and SHALL NOT expose a win rate above `100%`.

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

#### Scenario: Visitor opens FFA leaderboard with valid public stats

- **WHEN** a visitor opens the FFA leaderboard for a guild
- **THEN** every published row shows a mathematically valid `Wins`, `Games`,
  `Ratio`, and `Win Rate`

#### Scenario: Stored aggregate row is invalid

- **WHEN** a stored guild aggregate row would expose more wins than games for a
  public leaderboard entry
- **THEN** the public leaderboard does not publish that invalid row as if it
  were valid competitive data

#### Scenario: Visitor sorts the Support leaderboard

- **WHEN** a visitor switches to the Support leaderboard and sorts by a
  supported metric such as donated troops or donated gold
- **THEN** the leaderboard reorders the same guild-scoped player rows by that
  metric and shows support-focused columns plus recent activity

### Requirement: Publish descriptive team role labels

The system SHALL expose player-facing Team role labels that describe a
player's dominant observed Team play style rather than reacting to isolated
support actions. When leaderboard or profile views show a Team role label, a
player who mostly fronts across a meaningful Team sample MUST remain
`Frontliner` even if some games include donations. Players whose Team sample is
too small or too mixed to support a stable dominant style SHALL render the
existing fallback label `Flexible`.

#### Scenario: Mostly-frontline player appears on Team leaderboard

- **WHEN** a player appears on a guild Team or Support leaderboard after mostly
  playing frontline games with occasional donations
- **THEN** the displayed role label is `Frontliner`

#### Scenario: Small-sample player appears on public profile

- **WHEN** a player's observed Team history is too small to support a stable
  role classification
- **THEN** the public leaderboard and player profile show `Flexible`

#### Scenario: Mixed-style player appears on Team leaderboard

- **WHEN** a player's observed Team history does not show a clear dominant
  frontline or backline style
- **THEN** the displayed role label is `Hybrid`

### Requirement: Expose public guild player profiles

The system SHALL expose a public player profile page within each guild site for
every player entry that appears on a guild leaderboard, including players who
have never signed in. Each profile SHALL show the player's guild-scoped Team,
FFA, and Support sections when available, SHALL omit an `overall` section,
SHALL render the public player name without tracked guild clan-tag prefixes,
and SHALL surface recent-activity metadata beside the cumulative score
sections. The profile SHALL also show explicit `Wins / Games` score-note
labels, the full badge catalog with locked badges, dated progression charts,
recent-performance charts, multi-week contribution context, best-partner
summaries, and roster summaries.

Public Team and FFA profile sections SHALL obey the same validity constraints
as leaderboard rows. A published Team or FFA section SHALL NOT show more wins
than games or a win rate above `100%`.

#### Scenario: Visitor opens observed player profile

- **WHEN** a visitor opens a guild player profile for an observed-only player
- **THEN** the system serves the public guild-scoped competitive profile with
  badge and roster summary sections and without requiring authentication

#### Scenario: Visitor opens linked player profile

- **WHEN** a visitor opens a guild player profile for a linked player
- **THEN** the system shows the guild-scoped competitive sections, badge and
  roster summary sections, plus the linked-only sections already supported for
  that player

#### Scenario: Visitor opens player profile with valid FFA section

- **WHEN** a visitor opens a public guild player profile that includes an FFA
  section
- **THEN** the profile shows mathematically valid FFA wins, games, ratio, and
  win rate values

### Requirement: Explain score composition in player-facing language

The system SHALL present a concise explanation of how Team, FFA, and Support
scores are evaluated. The Team explanation SHALL state that every guild-relevant
Team game contributes positive score, that wins add extra value, that larger
Team lobbies count more, that smaller players-per-team formats count more,
that lower tracked guild presence on the player's team counts more, that win
rate is a light modifier, and that support adds a visible bonus. The
explanation SHALL also state that recency is shown as activity context and
SHALL NOT describe recency as a direct score factor.

#### Scenario: Visitor opens Team scoring explanation

- **WHEN** a visitor opens scoring help for the Team leaderboard
- **THEN** the page explains that participation volume is primary, wins add
  bonus points, more teams increase difficulty, smaller teams increase
  difficulty, lower tracked guild presence on the player's team increases
  difficulty, and support is additive

#### Scenario: Visitor opens FFA scoring explanation

- **WHEN** a visitor opens scoring help for the FFA leaderboard
- **THEN** the page explains that FFA is scored separately from Team and does
  not use support metrics

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
