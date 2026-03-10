## ADDED Requirements

### Requirement: Exclude Humans vs Nations from session-based win counts
For session-based win counting modes (`sessions_since_link` and `sessions_with_clan`), the system SHALL ignore sessions whose `playerTeams` value is exactly `Humans Vs Nations`. The system SHALL treat sessions without `playerTeams` as eligible and SHALL NOT perform extra game lookups.

#### Scenario: Humans vs Nations session
- **WHEN** a session `playerTeams` value is "Humans Vs Nations"
- **THEN** the session is not counted as a win

#### Scenario: Missing playerTeams in session
- **WHEN** a session `playerTeams` value is missing or empty
- **THEN** the session is evaluated as eligible without extra lookups

### Requirement: Total mode remains unfiltered
For `total` mode, the system SHALL continue using aggregate public stats without attempting to exclude Humans vs Nations games.

#### Scenario: Total mode wins
- **WHEN** counting mode is `total`
- **THEN** the system uses aggregate stats without filtering by `playerTeams`
