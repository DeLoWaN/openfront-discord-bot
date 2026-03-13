# guild-player-leaderboards Specification

## MODIFIED Requirements

### Requirement: Explain score composition in player-facing language

The system SHALL present a concise explanation of how the active leaderboard
view is evaluated. The Team explanation SHALL state that wins matter most,
recent matches matter more, matches with more teams count more, and donations
add a limited bonus. The Overall explanation SHALL state that it combines Team
and FFA after separate normalization, that it remains Team-first, and that a
mode with only a small sample size has reduced influence. The Overall weighting
guidance SHALL appear only when the visitor is viewing the `Overall`
leaderboard and SHALL NOT appear on `Team`, `FFA`, or `Support` leaderboard
views.

#### Scenario: Visitor opens Team scoring explanation

- **WHEN** a visitor opens scoring help for the Team leaderboard
- **THEN** the page explains the Team score factors without requiring the full
  internal formula to be shown

#### Scenario: Visitor opens Overall scoring explanation

- **WHEN** a visitor opens scoring help for the Overall leaderboard
- **THEN** the page states that Overall is a Team-first weighted combination of
  separately normalized Team and FFA performance, with reduced influence from
  modes where the player has only a small sample

#### Scenario: Visitor opens a non-Overall leaderboard

- **WHEN** a visitor opens the Team, FFA, or Support leaderboard
- **THEN** the page does not render the Overall weighting explanation about the
  `70% Team` / `30% FFA` target mix
