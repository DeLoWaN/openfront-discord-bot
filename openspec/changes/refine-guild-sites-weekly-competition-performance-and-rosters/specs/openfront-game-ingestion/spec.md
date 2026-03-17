# openfront-game-ingestion Delta

## MODIFIED Requirements

### Requirement: Maintain guild player aggregates from observations

The system SHALL maintain per-guild player aggregates derived from persisted
guild-relevant observations so leaderboard and public profile pages can be
served from stored guild stats rather than recalculating from raw observations
on each request. Aggregate refresh SHALL also rebuild derived daily, weekly,
roster, benchmark, and recent-game read models used by the public site.

#### Scenario: Aggregate refresh rebuilds read models

- **WHEN** guild aggregates are refreshed from stored observations
- **THEN** the system also rebuilds the derived read models needed for public
  daily, weekly, roster, and recent-game views

## ADDED Requirements

### Requirement: Rebuild roster aggregates from confidence-high team inference

The system SHALL rebuild `duo`, `trio`, and `quad` roster aggregates from
guild-relevant Team observations. A roster SHALL be accepted only when the
system can infer it with high confidence through exact team-size alignment or a
strong no-spawn filter on overflow same-tag players.

#### Scenario: Exact same-tag roster matches inferred team size

- **WHEN** tracked same-tag players in a Team game exactly match the inferred
  team size
- **THEN** the system records a roster event for that exact tracked roster

#### Scenario: Overflow same-tag players can be filtered as non-spawned

- **WHEN** tracked same-tag players exceed the inferred team size but overflow
  players have zero meaningful economy and action metrics
- **THEN** the system filters those overflow players and records the remaining
  exact roster

#### Scenario: Same-tag overflow remains ambiguous

- **WHEN** tracked same-tag overflow cannot be resolved with high confidence
- **THEN** the system excludes that game from public roster rankings

### Requirement: Maintain weekly guild ranking read models

The system SHALL maintain per-guild weekly ranking read models for Team, FFA,
and Support scopes. Weekly rows SHALL be bucketed by UTC calendar week and use
the same scoring formulas as the corresponding all-time views, scoped only to
games ending inside the week.

#### Scenario: Team game contributes to current UTC week

- **WHEN** a Team game ends within a UTC calendar week
- **THEN** its Team contribution is reflected in that week's Team ranking rows

#### Scenario: Weekly scope is absent for a player in a week

- **WHEN** a player has no qualifying games in a given week and scope
- **THEN** the system does not fabricate a weekly score row for that player
