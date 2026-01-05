## MODIFIED Requirements

### Requirement: Resolve winners for team games
The system SHALL fetch game details using `GET /public/game/:id?turns=false` and identify winners by matching `info.winner` entries to player `clientID` values. For team games, the system SHALL derive the set of winning clan tags from those winner client IDs and consider the game a guild win when at least one of those tags is configured for the guild. The system SHALL skip the game if no winner client IDs map to a configured clan tag.

#### Scenario: Winner list includes a configured tag
- **WHEN** a team game's winner client IDs include at least one clan tag configured for the guild
- **THEN** the system posts the game as a guild win

#### Scenario: Winner list has no configured tags
- **WHEN** a team game's winner client IDs resolve to clan tags that are not configured for the guild
- **THEN** the system skips posting the game

### Requirement: Resolve winners for Free For All games
For Free For All games, the system SHALL only display the winner client ID(s) from `info.winner` and SHALL NOT promote other players with the same clan tag to winners. The system SHALL post the game if any winner client ID maps to a clan tag configured for the guild, and SHALL skip the game otherwise.

#### Scenario: FFA winner has a configured clan tag
- **WHEN** a winner client ID resolves to a player with a clan tag configured for the guild
- **THEN** the system posts the game

#### Scenario: FFA winner has no configured clan tag
- **WHEN** the winning client ID resolves to a player without a configured clan tag
- **THEN** the system skips posting the game

### Requirement: Include clan members who died early in team games
For team games, the system SHALL include all players whose `clanTag` matches any winning clan tag configured for the guild in the winners list. For any such player whose `clientID` is not in the `info.winner` client ID list, the display SHALL be `🎉 Name - 💀 *died early*`. The system SHALL also append `*+X other player(s)*` where `X` is the computed players-per-team minus the count of displayed winners.

#### Scenario: Clan member not in winner list
- **WHEN** a player shares a winning clan tag configured for the guild but is not listed in `info.winner`
- **THEN** the winners line includes `🎉 Name - 💀 *died early*`
