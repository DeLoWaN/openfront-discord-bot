# guild-public-sites Specification

## MODIFIED Requirements

### Requirement: Render competitive views from backend data contracts

The public website SHALL render leaderboard and player profile views from
backend-provided data contracts and SHALL NOT require the frontend to
recalculate leaderboard scores. The website SHALL render the backend scoring
explanation in two layers:

- a short inline summary
- an expandable `Exact computation` section

#### Scenario: Frontend renders leaderboard scoring help

- **WHEN** the frontend renders a guild leaderboard view
- **THEN** it shows the backend-provided summary inline and the backend-provided
  exact-computation content inside an expandable disclosure element

### Requirement: Expose competitive leaderboard navigation

The system SHALL provide public navigation from each guild site to the `Team`,
`FFA`, `Overall`, and `Support` leaderboard views, and the rendered leaderboard
tables SHALL visibly include `support_bonus` in the Team, Overall, and Support
views according to the backend contracts.

#### Scenario: Visitor switches to Overall leaderboard

- **WHEN** a visitor opens the Overall leaderboard on a guild site
- **THEN** the rendered table includes `Support Bonus` alongside the overall
  and component mode scores
