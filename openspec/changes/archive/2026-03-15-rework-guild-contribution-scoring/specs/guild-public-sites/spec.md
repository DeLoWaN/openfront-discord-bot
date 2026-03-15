# guild-public-sites Delta

## MODIFIED Requirements

### Requirement: Expose competitive leaderboard navigation

The system SHALL provide public navigation from each guild site to the `Team`,
`FFA`, and `Support` leaderboard views. The site SHALL NOT expose an `Overall`
leaderboard view.

#### Scenario: Visitor opens guild leaderboard navigation

- **WHEN** a visitor opens a guild site with leaderboard access
- **THEN** the site shows navigation to Team, FFA, and Support views

#### Scenario: Visitor switches leaderboard views

- **WHEN** a visitor selects a different leaderboard view on a guild site
- **THEN** the site serves the chosen guild-scoped leaderboard view without
  leaving the guild scope

### Requirement: Render competitive views from backend data contracts

The public website SHALL render leaderboard and player profile views from
backend-provided data contracts and SHALL NOT require the frontend to
recalculate leaderboard scores. The public site SHALL present recent activity
beside the cumulative score so visitors can distinguish historical guild
anchors from currently active players without changing score semantics.

#### Scenario: Frontend renders leaderboard rows

- **WHEN** the frontend renders a guild leaderboard view
- **THEN** it uses the score and metric values returned by the backend rather
  than recomputing them in the browser

#### Scenario: Backend scoring logic changes behind a stable contract

- **WHEN** the backend updates its internal scoring calculation without
  changing the API contract
- **THEN** the frontend can render the updated scores without shipping a new
  score formula

## ADDED Requirements

### Requirement: Surface recent activity as context instead of score decay

The public website SHALL display recent-activity context for Team, FFA, and
Support views without expressing that context as score decay. The site MAY use
fields such as `Games 30d`, `Last Team Game`, or an `Active` badge, but it
MUST keep the cumulative score meaning separate from recent activity.

#### Scenario: Visitor views Team leaderboard row

- **WHEN** the Team leaderboard renders a player row
- **THEN** the site shows recent activity beside the Team score instead of
  implying that inactivity directly reduced the score

#### Scenario: Visitor views player profile

- **WHEN** a player profile is rendered
- **THEN** the site shows recent Team and FFA activity alongside the
  cumulative score sections
