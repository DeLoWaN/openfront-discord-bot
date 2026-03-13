# guild-public-sites Specification

## ADDED Requirements

### Requirement: Expose competitive leaderboard navigation

The system SHALL provide public navigation from each guild site to the `Team`,
`FFA`, `Overall`, and `Support` leaderboard views.

#### Scenario: Visitor opens guild leaderboard navigation

- **WHEN** a visitor opens a guild site with leaderboard access
- **THEN** the site shows navigation to Team, FFA, Overall, and Support views

#### Scenario: Visitor switches leaderboard views

- **WHEN** a visitor selects a different leaderboard view on a guild site
- **THEN** the site serves the chosen guild-scoped leaderboard view without
  leaving the guild scope

### Requirement: Render competitive views from backend data contracts

The public website SHALL render leaderboard and player profile views from
backend-provided data contracts and SHALL NOT require the frontend to
recalculate leaderboard scores.

#### Scenario: Frontend renders leaderboard rows

- **WHEN** the frontend renders a guild leaderboard view
- **THEN** it uses the score and metric values returned by the backend rather
  than recomputing them in the browser

#### Scenario: Backend scoring logic changes behind a stable contract

- **WHEN** the backend updates its internal scoring calculation without
  changing the API contract
- **THEN** the frontend can render the updated scores without shipping a new
  score formula

### Requirement: Hide tracked clan tags in public player-name rendering

The public website SHALL render player names for guild leaderboard and player
profile views without tracked guild clan-tag prefixes.

#### Scenario: Leaderboard renders tracked-tag variant

- **WHEN** the backend returns a public player name for an observed player
  whose raw username included a tracked guild clan-tag prefix
- **THEN** the leaderboard renders the stripped public player name without the
  tracked clan tag

#### Scenario: Player profile renders tracked-tag variant

- **WHEN** the backend returns a public player name for a guild player profile
- **THEN** the profile renders that stripped public player name and does not
  append the tracked clan tag next to it
