# guild-stats-api Specification

## MODIFIED Requirements

### Requirement: Expose guild-scoped leaderboard API views

The system SHALL expose machine-readable guild-scoped leaderboard endpoints for
the `team`, `ffa`, `overall`, and `support` views. Each leaderboard response
SHALL include the view identifier, the default ranking field for that view, the
numeric values needed for client-side sorting, and the player identity state
needed to label entries as linked or observed. Public player-name fields in the
response SHALL omit tracked guild clan-tag prefixes. `support_bonus` SHALL be
present in Team, Overall, and Support view rows.

#### Scenario: Client requests Overall leaderboard data

- **WHEN** a client requests the `overall` leaderboard view for a guild
- **THEN** the response contains `overall_score`, `team_score`, `ffa_score`,
  `support_bonus`, and the component mode game counts for each row

### Requirement: Expose scoring explanation data

The system SHALL expose machine-readable scoring explanation data for the Team,
FFA, Overall, and Support leaderboard views. Each explanation response SHALL
include:

- `summary`: a short player-facing explanation
- `details`: exact computation content for the active view

The Team explanation SHALL state that harder lobbies and recent wins count
more, stacked guild games count less, losses subtract, and support adds a
visible bonus. The Overall explanation SHALL state that Overall combines only
normalized Team and FFA outputs with Team-first weighting and sample
confidence.

The exact computation payload SHALL include the formulas or rule lines needed
to explain:

- Team difficulty inference
- guild-stack adjustment
- recency decay
- support bonus normalization
- Overall confidence weighting

#### Scenario: Client requests Team scoring explanation

- **WHEN** a client requests scoring explanation data for the Team view
- **THEN** the response includes both a short summary and exact computation
  details for Team score and support bonus

#### Scenario: Client requests Support scoring explanation

- **WHEN** a client requests scoring explanation data for the Support view
- **THEN** the response explains that Support ranks the normalized
  `support_bonus` first while still exposing exact donation totals
