# guild-player-badges Delta

## ADDED Requirements

### Requirement: Award code-defined guild player badges

The system SHALL award guild player badges from a code-defined catalog with
absolute thresholds. The badge model SHALL support milestone badges with
levels and single-unlock badges for performance, role, combo, and map
achievements. Each persisted badge award SHALL include the time the player
first qualified for that badge or badge level.

#### Scenario: Player reaches a milestone level

- **WHEN** a player's observed history first reaches the next threshold for a
  leveled guild badge
- **THEN** the system persists that badge level with the first qualifying
  timestamp

#### Scenario: Player unlocks a single-award badge

- **WHEN** a player's observed history first satisfies a single-unlock badge
  rule
- **THEN** the system persists that badge with the first qualifying timestamp

### Requirement: Expose badges on public guild player surfaces

The system SHALL expose earned badges on public guild player profiles and
other player-facing guild surfaces that summarize achievement progress.

#### Scenario: Visitor opens guild player profile

- **WHEN** a visitor opens a guild player profile for a player with earned
  badges
- **THEN** the profile includes the player's earned guild badge data

#### Scenario: Visitor opens guild player profile with no badges yet

- **WHEN** a visitor opens a guild player profile for a player with no earned
  badges
- **THEN** the profile renders an empty-state badge section instead of
  implying hidden badge data

### Requirement: Expose recent guild badge awards

The system SHALL expose recent guild badge awards so the guild home experience
can highlight newly earned badges. The recent badge feed SHALL be ordered by
the persisted award timestamp rather than by recompute time.

#### Scenario: Historical recompute preserves award ordering

- **WHEN** badge awards are recomputed from older observed game history
- **THEN** the recent badge feed continues to order results by first
  qualifying award time

#### Scenario: Home page shows recent badge awards

- **WHEN** the guild home page renders recent badge activity
- **THEN** it can show the newest earned guild badges without recalculating
  badge rules in the browser
