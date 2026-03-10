## ADDED Requirements

### Requirement: Exclude Humans vs Nations games from results posting
The system SHALL skip posting results when a game's `playerTeams` value is exactly `Humans Vs Nations`. If `playerTeams` is missing or not a string, the game remains eligible for posting.

#### Scenario: Humans vs Nations game detected
- **WHEN** the game `playerTeams` value is "Humans Vs Nations"
- **THEN** the system skips posting the game results

#### Scenario: Missing playerTeams
- **WHEN** the game `playerTeams` value is missing or empty
- **THEN** the system evaluates the game normally
