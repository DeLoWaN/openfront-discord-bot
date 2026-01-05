## ADDED Requirements

### Requirement: Poll public games for results
The system SHALL poll public games for results using `GET /public/games` with a `start/end` window and `type=Public`, paging with the `Content-Range` header until all results in the window are processed.

#### Scenario: Paginated public games window
- **WHEN** the `Content-Range` header indicates additional pages
- **THEN** the system continues requesting pages by adjusting the offset until all games in the window are retrieved

### Requirement: Resolve winners for team games
The system SHALL fetch game details using `GET /public/game/:id?turns=false` and identify winners by matching `info.winner` entries to player `clientID` values. For team games, the system SHALL derive a single winning clan tag from those winner client IDs and skip the game if there is no clan tag, multiple clan tags, or the tag is not in the guild's configured clan tags.

#### Scenario: Winner tag is not configured
- **WHEN** a team game's winner client IDs resolve to a clan tag that is not configured for the guild
- **THEN** the system skips posting the game

### Requirement: Resolve winners for Free For All games
For Free For All games, the system SHALL only display the winner client ID(s) from `info.winner` and SHALL NOT promote other players with the same clan tag to winners. The system SHALL skip the game if the winner has no clan tag or the tag is not in the guild's configured clan tags.

#### Scenario: FFA winner has no clan tag
- **WHEN** the winning client ID resolves to a player without a clan tag
- **THEN** the system skips posting the game

### Requirement: Include clan members who died early in team games
For team games, the system SHALL include all players whose `clanTag` matches the winning clan tag in the winners list. For any such player whose `clientID` is not in the `info.winner` client ID list, the display SHALL be `🎉 Name - 💀 *died early*`. The system SHALL also append `*+X other player(s)*` where `X` is the computed players-per-team minus the count of displayed winners.

#### Scenario: Clan member not in winner list
- **WHEN** a player shares the winning clan tag but is not listed in `info.winner`
- **THEN** the winners line includes `🎉 Name - 💀 *died early*`

### Requirement: Format team mode with players per team
For team games, the system SHALL compute players per team and render the mode as `N teams of M players`, appending the team size label when provided (e.g., `24 teams of 2 players (Duos)`). The system SHALL derive `N` and `M` from `config.playerTeams` and `config.maxPlayers` when needed: named sizes (Duos/Trios/Quads) map to 2/3/4 players per team, and numeric `playerTeams` represents the number of teams, so `players_per_team = maxPlayers / playerTeams`. For Free For All games, the system SHALL display the game mode label.

#### Scenario: Team size label provided
- **WHEN** a team game uses a named team size (e.g., Duos)
- **THEN** the mode line includes the label in parentheses
