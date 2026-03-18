# guild-weekly-rankings Specification

## Purpose
TBD - created by archiving change refine-guild-sites-weekly-competition-performance-and-rosters. Update Purpose after archive.
## Requirements
### Requirement: Publish weekly guild rankings by scope

The system SHALL publish weekly guild rankings for `team`, `ffa`, and
`support` scopes. Rankings SHALL be grouped by UTC calendar week and expose the
current week plus a bounded recent history window.

#### Scenario: Client requests weekly FFA rankings

- **WHEN** weekly rankings are requested with `scope=ffa`
- **THEN** the system returns the current UTC week FFA leaderboard plus recent
  weekly history for that scope

### Requirement: Expose mover deltas versus the previous full week

The system SHALL expose mover information by comparing the current full week
rank to the previous full week rank within the same scope. If a player had no
previous-week row, the system SHALL expose the player as `new` instead of
inventing a numeric delta.

#### Scenario: Player climbs from the previous week

- **WHEN** a player is ranked in both the current and previous Team week
- **THEN** the weekly response includes the signed rank delta for that player

#### Scenario: Player is absent from the previous week

- **WHEN** a player appears in the current week but not the previous week
- **THEN** the weekly response marks that player as `new`

