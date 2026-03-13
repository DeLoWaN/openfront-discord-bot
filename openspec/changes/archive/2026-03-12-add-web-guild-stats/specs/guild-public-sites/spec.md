# Guild Public Sites Specification

## ADDED Requirements

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
