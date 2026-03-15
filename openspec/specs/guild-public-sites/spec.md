# guild-public-sites Specification

## Purpose

Define the public guild site routing and presentation behavior.
## Requirements
### Requirement: Manually provisioned guild sites

The system SHALL support manually provisioned guild sites, each with a unique
subdomain, public identity, and active/inactive state. A guild site SHALL NOT
require a linked Discord server in order to exist or be served publicly.

#### Scenario: Active guild without Discord linkage

- **WHEN** a guild has been provisioned with an active subdomain and no Discord
  server linkage
- **THEN** the system serves the public guild site normally

#### Scenario: Inactive guild site

- **WHEN** a guild subdomain exists but the guild is inactive
- **THEN** the system does not serve the public guild site

### Requirement: Resolve guild sites by subdomain

The system SHALL resolve incoming website requests to a guild using the
requested subdomain and SHALL serve only the content for that guild scope.

#### Scenario: Known guild subdomain

- **WHEN** a visitor requests a provisioned guild subdomain
- **THEN** the system serves pages scoped to that guild

#### Scenario: Unknown guild subdomain

- **WHEN** a visitor requests a subdomain that is not provisioned
- **THEN** the system returns a not-found response instead of another guild's
  content

### Requirement: Expose a public guild home page

The system SHALL provide a public home page for each guild site that includes
the guild identity, tracked clan tags, and navigation to the guild leaderboard
and public player profiles.

#### Scenario: Visitor opens guild home page

- **WHEN** a visitor loads the root page of a guild subdomain
- **THEN** the page shows guild context and links to its leaderboard and player
  views

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
