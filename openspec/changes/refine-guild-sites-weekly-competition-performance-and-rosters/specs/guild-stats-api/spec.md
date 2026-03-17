# guild-stats-api Delta

## MODIFIED Requirements

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
player entry that appears on a guild leaderboard. The response SHALL include
the full badge catalog state, lightweight weekly summary data, and explicit
score-note semantics suitable for the public profile.

#### Scenario: Client requests a guild player profile

- **WHEN** a client requests profile data for a guild player
- **THEN** the response contains competitive sections, full badge state,
  weekly summary data, and public profile identity data

## ADDED Requirements

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
guild-wide recalculation at read time.

#### Scenario: Client requests player timeseries

- **WHEN** a client requests timeseries data for a guild player
- **THEN** the response contains read-model-backed daily and weekly series
  ready for chart rendering
