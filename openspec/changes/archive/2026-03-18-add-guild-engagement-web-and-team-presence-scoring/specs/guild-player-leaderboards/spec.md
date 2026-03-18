# guild-player-leaderboards Delta

## MODIFIED Requirements

### Requirement: Expose public guild player profiles

The system SHALL expose a public player profile page within each guild site for
every player entry that appears on a guild leaderboard, including players who
have never signed in. Each profile SHALL show the player's guild-scoped Team,
FFA, and Support sections when available, SHALL omit an `overall` section, and
SHALL render the public player name without tracked guild clan-tag prefixes.
The profile SHALL also surface recent-activity metadata beside the cumulative
score sections. The profile SHALL additionally expose earned badges, best
partners, and combo summaries so the page reflects both individual and social
guild engagement.

#### Scenario: Visitor opens observed player profile

- **WHEN** a visitor opens a guild player profile for an observed-only player
- **THEN** the system serves the public guild-scoped competitive profile with
  badge and combo summary sections and without requiring authentication

#### Scenario: Visitor opens linked player profile

- **WHEN** a visitor opens a guild player profile for a linked player
- **THEN** the system shows the guild-scoped competitive sections, badge and
  combo summary sections, plus the linked-only sections already supported for
  that player

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
