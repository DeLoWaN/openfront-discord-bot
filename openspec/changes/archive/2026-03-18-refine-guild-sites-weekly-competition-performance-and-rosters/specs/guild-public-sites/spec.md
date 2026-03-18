# guild-public-sites Delta

## MODIFIED Requirements

### Requirement: Expose a public guild home page

The system SHALL provide a public home page for each guild site that includes
the guild identity, tracked clan tags, and navigation to the guild leaderboard
and public player profiles. The home page SHALL also surface ranked
competitive-pulse entries, recent guild games, roster activity, recent badges,
and a weekly competition module.

#### Scenario: Visitor opens guild home page

- **WHEN** a visitor loads the root page of a guild subdomain
- **THEN** the page shows guild context plus ranked pulse, recent games,
  roster, and weekly modules

### Requirement: Expose competitive leaderboard navigation

The system SHALL provide public navigation from each guild site to the `Team`,
`FFA`, and `Support` leaderboard views. The same navigation layer SHALL also
provide entry points to `Rosters`, `Recent Games`, and `Weekly` views without
leaving the guild scope.

#### Scenario: Visitor opens public guild navigation

- **WHEN** a visitor opens a guild site
- **THEN** the site shows entry points for leaderboard, players, rosters,
  recent games, and weekly views

## ADDED Requirements

### Requirement: Expose a public weekly competition page

The system SHALL provide a public weekly page for each guild site. The page
SHALL expose current-week Team, FFA, and Support leaders, movers versus the
previous full week, and six-week trend context.

#### Scenario: Visitor opens weekly page

- **WHEN** a visitor opens the guild weekly page
- **THEN** the page shows current-week leaders and rank movement for the
  selected scope

### Requirement: Expose a public recent-games page

The system SHALL provide a public recent-games page for each guild site that
shows recent guild-relevant games, not only wins. The page SHALL support
result filtering and card/list presentation without leaving the guild scope.

#### Scenario: Visitor opens recent games

- **WHEN** a visitor opens the recent-games page
- **THEN** the page shows recent guild games with result, date, map, format,
  and replay context
