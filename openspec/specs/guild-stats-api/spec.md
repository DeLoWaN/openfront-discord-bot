# guild-stats-api Specification

## Purpose

Define the guild-scoped JSON contracts used by the public guild website.

## Requirements

### Requirement: Expose guild-scoped leaderboard API views

The system SHALL expose machine-readable guild-scoped leaderboard endpoints for
the `team`, `ffa`, and `support` views. Each leaderboard response SHALL
include sortable column metadata, explicit sort state, `ratio`, `win_rate`,
and recent-activity fields suitable for fully sortable public tables.

#### Scenario: Client requests Team leaderboard data

- **WHEN** a client requests the `team` leaderboard view for a guild
- **THEN** the response contains Team rows, explicit column metadata, and the
  values required for ascending or descending client-side sorting

### Requirement: Expose guild player profile API data

The system SHALL expose machine-readable guild player profile data for every
player entry that appears on a guild leaderboard. The response SHALL provide
separate Team, FFA, and Support sections when that data exists for the player,
along with linked-versus-observed state, public profile identity data,
explicit score-note semantics, recent-activity metadata, the full badge
catalog state, lightweight weekly summary data, best-partner summaries, and
roster summaries suitable for the public profile. The response SHALL NOT
expose an `overall` profile section.

#### Scenario: Client requests observed player profile data

- **WHEN** a client requests a guild player profile for an observed-only player
- **THEN** the response contains guild-scoped competitive sections, badge and
  roster summary data, weekly summary data, and public profile identity data

#### Scenario: Client requests linked player profile data

- **WHEN** a client requests a guild player profile for a linked player
- **THEN** the response contains the guild-scoped competitive sections, full
  badge state, partner and roster summary data, plus any linked-only sections
  already supported for that player

### Requirement: Expose scoring explanation data

The system SHALL expose machine-readable scoring explanation data for the Team,
FFA, and Support leaderboard views. The explanation SHALL describe the major
factors for each score in player-facing language and SHALL state that Team
match difficulty depends on team count with no hard cap at `10`, smaller
players-per-team formats, and lower tracked guild presence on the player's
team. The explanation SHALL also state that recent activity is exposed beside
the score instead of being integrated into the score itself.

#### Scenario: Client requests Team scoring explanation

- **WHEN** a client requests scoring explanation data for the Team view
- **THEN** the response states that all Team games contribute positively, wins
  add bonus value, more teams increase difficulty, smaller teams increase
  difficulty, fewer tracked guild teammates on the player's team increase
  difficulty, and support adds a visible bonus

#### Scenario: Client requests FFA scoring explanation

- **WHEN** a client requests scoring explanation data for the FFA view
- **THEN** the response states that FFA is scored separately and does not use
  support metrics

### Requirement: Expose guild-scoped public player names without tracked tags

The system SHALL expose player-name fields for public guild views using the
guild-aware public display name rather than the raw observed username.

#### Scenario: Client requests leaderboard row for tracked-tag variant

- **WHEN** a leaderboard row represents an observed player whose raw username
  includes a tracked guild clan-tag prefix
- **THEN** the API response exposes the stripped public player name instead of
  the raw tagged username

### Requirement: Expose recent-activity metadata beside cumulative scores

The system SHALL expose recent-activity fields separately from the score values
for Team, FFA, and Support views. These fields SHALL allow clients to show who
is currently active without altering the cumulative score ordering.

#### Scenario: Client requests Team leaderboard row

- **WHEN** a Team leaderboard row is returned
- **THEN** the row includes recent-activity fields such as `last_team_game_at`
  and a 30-day Team game count beside the cumulative Team score

#### Scenario: Client requests FFA leaderboard row

- **WHEN** an FFA leaderboard row is returned
- **THEN** the row includes recent-activity fields such as `last_ffa_game_at`
  and a 30-day FFA game count beside the cumulative FFA score

### Requirement: Expose guild home API data

The system SHALL expose machine-readable guild home data for the public guild
dashboard. The response SHALL provide the data needed to render the
competitive pulse, confirmed roster podiums, pending roster teaser, recent
wins preview, and recent badge activity without browser-side business logic.

#### Scenario: Client requests guild home data

- **WHEN** a client requests guild home data
- **THEN** the response includes the engagement sections required to render the
  guild dashboard

### Requirement: Expose recent guild wins API data

The system SHALL expose machine-readable recent guild wins data for public
guild views. The recent wins response SHALL support `Team` and `FFA` wins,
include match context such as map, mode, duration, and replay link, and be
ordered from newest to oldest.

#### Scenario: Client requests recent wins feed

- **WHEN** a client requests recent guild wins data
- **THEN** the response contains the latest guild `Team` and `FFA` wins in
  reverse chronological order

### Requirement: Expose weekly guild rankings API data

The system SHALL expose machine-readable weekly guild rankings data for Team,
FFA, and Support scopes. The response SHALL include current-week rows, movers
versus the previous full week, and a bounded multi-week history window.

#### Scenario: Client requests weekly Team rankings

- **WHEN** a client requests weekly rankings with `scope=team`
- **THEN** the response contains the current UTC week leaderboard, mover
  information, and recent weekly trend data

### Requirement: Expose refined recent-games API data

The system SHALL expose machine-readable recent guild games data. The response
SHALL include result, team distribution, replay link, winning-side player
context when available, guild-side tracked players, and optional thumbnail
URLs.

#### Scenario: Client requests recent games

- **WHEN** a client requests recent guild games data
- **THEN** the response contains recent guild games ordered from newest to
  oldest with replay and result context

### Requirement: Expose read-model-backed player timeseries API data

The system SHALL expose machine-readable player timeseries data backed by
stored daily and weekly read models. The response SHALL include daily
progression, daily benchmarks, recent performance, and weekly scores without
guild-wide recalculation at read time so public guild player profiles can
render progression and recent-form charts directly.

#### Scenario: Client requests player timeseries

- **WHEN** a client requests timeseries data for a guild player
- **THEN** the response contains read-model-backed daily and weekly series
  ready for chart rendering
