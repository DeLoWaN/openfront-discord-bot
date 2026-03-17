# openfront-game-ingestion Delta

## MODIFIED Requirements

### Requirement: Value larger Team lobbies without a hard cap at ten teams

The system SHALL infer Team difficulty from stored game data and SHALL make the
Team score increase monotonically with the number of teams in the lobby. The
difficulty model MUST also increase when the inferred players-per-team value is
smaller and when the tracked guild presence on the player's team is lower. The
team-count signal SHALL remain primary, while the smaller-team and lower-guild-
presence signals SHALL act as lighter multiplicative refinements. The
difficulty model MUST still use damped growth so a few extreme lobbies do not
dominate the entire leaderboard.

#### Scenario: Large Team lobby is ingested

- **WHEN** a guild-relevant Team game is inferred to have more than `10` teams
- **THEN** the Team contribution model applies a higher difficulty value than
  it would for a `10`-team game

#### Scenario: Smaller team format increases difficulty

- **WHEN** the system compares two Team wins with the same number of teams but
  one game has fewer players per team
- **THEN** the smaller-team game receives the higher Team difficulty value

#### Scenario: Lower tracked guild presence increases difficulty

- **WHEN** the system compares two Team wins with the same lobby size and team
  size but one player's team has fewer tracked guild-tag teammates
- **THEN** the lower-guild-presence win receives the higher Team difficulty
  value

#### Scenario: Missing players-per-team signal falls back safely

- **WHEN** the system cannot infer players per team for a Team game
- **THEN** the smaller-team and guild-presence refinements fall back to a
  neutral value instead of inventing unsupported difficulty
