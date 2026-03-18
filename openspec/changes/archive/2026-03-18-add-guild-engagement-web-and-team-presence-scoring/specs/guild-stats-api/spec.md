# guild-stats-api Delta

## MODIFIED Requirements

### Requirement: Expose guild player profile API data

The system SHALL expose machine-readable guild player profile data for every
player entry that appears on a guild leaderboard. The response SHALL provide
separate Team, FFA, and Support sections when that data exists for the player,
along with linked-versus-observed state and recent-activity metadata. The
response SHALL NOT expose an `overall` profile section. The response SHALL
also expose player badge data, best partners, and combo summaries needed for
the richer guild profile experience.

#### Scenario: Client requests observed player profile data

- **WHEN** a client requests a guild player profile for an observed-only player
- **THEN** the response contains guild-scoped competitive sections and any
  earned badge or combo summary data that can be rendered without sign-in

#### Scenario: Client requests linked player profile data

- **WHEN** a client requests a guild player profile for a linked player
- **THEN** the response contains the guild-scoped competitive sections, badge
  and combo summary data, plus any linked-only sections already supported for
  that player

### Requirement: Expose scoring explanation data

The system SHALL expose machine-readable scoring explanation data for the
Team, FFA, and Support leaderboard views. The explanation SHALL describe the
major factors for each score in player-facing language and SHALL state that
Team match difficulty depends on team count, smaller players-per-team formats,
and lower tracked guild presence on the player's team. The explanation SHALL
also state that recent activity is exposed beside the score instead of being
integrated into the score itself.

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

## ADDED Requirements

### Requirement: Expose guild home API data

The system SHALL expose machine-readable guild home data for the public guild
dashboard. The response SHALL provide the data needed to render the
competitive pulse, confirmed combo podiums, pending combo teaser, recent wins
preview, and recent badge activity without browser-side business logic.

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

### Requirement: Expose player timeseries API data

The system SHALL expose machine-readable player timeseries data so public guild
player profiles can render progression and recent-form graphs without
recomputing buckets in the browser.

#### Scenario: Client requests player timeseries data

- **WHEN** a client requests timeseries data for a guild player profile
- **THEN** the response contains the backend-prepared buckets needed for
  progression and recent-form charts
