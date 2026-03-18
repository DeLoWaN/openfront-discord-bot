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
and public player profiles. The home page SHALL act as the main engagement
dashboard by surfacing ranked competitive-pulse entries, confirmed roster
podiums, a teaser for pending roster activity, a preview of recent guild wins,
recent badges, and a weekly competition module.

#### Scenario: Visitor opens guild home page

- **WHEN** a visitor loads the root page of a guild subdomain
- **THEN** the page shows guild context plus ranked pulse, roster, recent
  wins, badge, and weekly modules

#### Scenario: Visitor sees home engagement sections

- **WHEN** a visitor opens a populated guild home page
- **THEN** the page shows the competitive pulse, confirmed roster podiums,
  recent wins preview, and recent badge activity

### Requirement: Expose competitive leaderboard navigation

The system SHALL provide public navigation from each guild site to the `Team`,
`FFA`, and `Support` leaderboard views. The same navigation layer SHALL also
provide entry points to `Rosters`, `Recent Wins`, `Recent Games`, and
`Weekly` views without leaving the guild scope.

#### Scenario: Visitor opens public guild navigation

- **WHEN** a visitor opens a guild site
- **THEN** the site shows entry points for leaderboard, players, rosters,
  recent wins, recent games, and weekly views

### Requirement: Render competitive views from backend data contracts

The public website SHALL render guild home, leaderboard, roster, recent-wins,
recent-games, weekly, and player profile views from backend-provided data
contracts and SHALL NOT require the frontend to recalculate leaderboard
scores, roster confirmation, or badge eligibility in the browser. The public
site SHALL present recent activity beside the cumulative score so visitors can
distinguish historical guild anchors from currently active players without
changing score semantics.

#### Scenario: Frontend renders leaderboard rows

- **WHEN** the frontend renders a guild leaderboard view
- **THEN** it uses the score and metric values returned by the backend rather
  than recomputing them in the browser

#### Scenario: Frontend renders roster rows

- **WHEN** the frontend renders confirmed or pending roster views
- **THEN** it uses backend-provided roster status and metric values instead of
  recomputing roster eligibility in the browser

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

### Requirement: Expose a public weekly competition page

The system SHALL provide a public weekly page for each guild site. The page
SHALL expose current-week Team, FFA, and Support leaders, movers versus the
previous full week, and six-week trend context.

#### Scenario: Visitor opens weekly page

- **WHEN** a visitor opens the guild weekly page
- **THEN** the page shows current-week leaders and rank movement for the
  selected scope

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

### Requirement: Expose a public recent-games page

The system SHALL provide a public recent-games page for each guild site that
shows recent guild-relevant games, not only wins. The page SHALL support
result filtering and card/list presentation without leaving the guild scope.

#### Scenario: Visitor opens recent games

- **WHEN** a visitor opens the recent-games page
- **THEN** the page shows recent guild games with result, date, map, format,
  and replay context

### Requirement: Keep public leaderboard views usable on narrow screens

The public website SHALL keep leaderboard pages usable on narrow viewports
without causing page-level horizontal overflow. If the active leaderboard table
requires more width than the viewport, the overflow MUST be contained within
the leaderboard content region rather than expanding the full document width.

#### Scenario: Visitor opens leaderboard on a narrow screen

- **WHEN** a visitor opens a guild leaderboard view on a narrow viewport
- **THEN** the page remains bounded to the viewport and any extra horizontal
  width is contained within the leaderboard region
