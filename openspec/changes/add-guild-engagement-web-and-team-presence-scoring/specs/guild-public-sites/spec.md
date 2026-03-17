# guild-public-sites Delta

## MODIFIED Requirements

### Requirement: Expose a public guild home page

The system SHALL provide a public home page for each guild site that includes
the guild identity, tracked clan tags, and navigation to the guild leaderboard
and public player profiles. The home page SHALL also act as the main
engagement dashboard by surfacing a competitive pulse, confirmed combo
podiums, a teaser for pending combo activity, a preview of recent guild wins,
and recent badge activity.

#### Scenario: Visitor opens guild home page

- **WHEN** a visitor loads the root page of a guild subdomain
- **THEN** the page shows guild context and links to leaderboard, player, and
  engagement views

#### Scenario: Visitor sees home engagement sections

- **WHEN** a visitor opens a populated guild home page
- **THEN** the page shows the competitive pulse, confirmed combo podiums,
  recent wins preview, and recent badge activity

### Requirement: Expose competitive leaderboard navigation

The system SHALL provide public navigation from each guild site to the `Team`,
`FFA`, and `Support` leaderboard views. The site SHALL NOT expose an `Overall`
leaderboard view. The same public navigation layer SHALL also provide entry
points to combo and recent-wins views without leaving the guild scope.

#### Scenario: Visitor opens guild leaderboard navigation

- **WHEN** a visitor opens a guild site with leaderboard access
- **THEN** the site shows navigation to Team, FFA, Support, combo, and recent
  wins views

#### Scenario: Visitor switches engagement views

- **WHEN** a visitor selects a combo or recent-wins view on a guild site
- **THEN** the site serves the chosen guild-scoped view without leaving the
  guild scope

### Requirement: Render competitive views from backend data contracts

The public website SHALL render guild home, leaderboard, combo, recent-wins,
and player profile views from backend-provided data contracts and SHALL NOT
require the frontend to recalculate leaderboard scores, combo confirmation, or
badge eligibility in the browser. The public site SHALL present recent
activity beside the cumulative score so visitors can distinguish historical
guild anchors from currently active players without changing score semantics.

#### Scenario: Frontend renders combo podiums

- **WHEN** the frontend renders confirmed or pending combo views
- **THEN** it uses backend-provided combo status and metric values instead of
  recomputing combo eligibility in the browser

#### Scenario: Backend logic changes behind stable contracts

- **WHEN** the backend updates its internal ranking, scoring, or badge
  calculation without changing the API contract
- **THEN** the frontend can render the updated experience without shipping new
  business logic

## ADDED Requirements

### Requirement: Expose a public recent guild wins page

The system SHALL provide a public recent-wins page for each guild site that
shows the latest guild `Team` and `FFA` wins in reverse chronological order.
The page SHALL favor recent relevance over deep archive behavior.

#### Scenario: Visitor opens recent wins page

- **WHEN** a visitor opens the guild recent-wins page
- **THEN** the page shows the latest guild wins with match context and replay
  links

#### Scenario: Older wins are not treated as the primary product surface

- **WHEN** a guild has a large historical win history
- **THEN** the public recent-wins page still emphasizes a limited recent slice
  instead of acting like a deep archive
