# game-results-posting Specification

## Purpose
TBD - created by archiving change update-exclude-humans-vs-nations. Update Purpose after archive.
## Requirements
### Requirement: Exclude Humans vs Nations games from results posting
The system SHALL skip posting results when a game's `playerTeams` value is exactly `Humans Vs Nations`. If `playerTeams` is missing or not a string, the game remains eligible for posting.

#### Scenario: Humans vs Nations game detected
- **WHEN** the game `playerTeams` value is "Humans Vs Nations"
- **THEN** the system skips posting the game results

#### Scenario: Missing playerTeams
- **WHEN** the game `playerTeams` value is missing or empty
- **THEN** the system evaluates the game normally

### Requirement: Poll public games for results
The system SHALL poll public games for results using `GET /public/games` with a `start/end` window and `type=Public`, paging with the `Content-Range` header until all results in the window are processed.

#### Scenario: Paginated public games window
- **WHEN** the `Content-Range` header indicates additional pages
- **THEN** the system continues requesting pages by adjusting the offset until all games in the window are retrieved

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

### Requirement: Format team mode with players per team
For team games, the system SHALL compute players per team and render the mode as `N teams of M players`, appending the team size label when provided (e.g., `24 teams of 2 players (Duos)`). The system SHALL derive `N` and `M` from `config.playerTeams` and `config.maxPlayers` when needed: named sizes (Duos/Trios/Quads) map to 2/3/4 players per team, and numeric `playerTeams` represents the number of teams, so `players_per_team = maxPlayers / playerTeams`. For Free For All games, the system SHALL display the game mode label.

#### Scenario: Team size label provided
- **WHEN** a team game uses a named team size (e.g., Duos)
- **THEN** the mode line includes the label in parentheses

### Requirement: Configure lobby polling interval
The system SHALL read `results_lobby_poll_seconds` from config (default 2 seconds) and use it to schedule public lobby polling.

#### Scenario: Custom lobby interval
- **WHEN** `results_lobby_poll_seconds` is set to 5
- **THEN** the lobby polling loop runs on a 5-second cadence

### Requirement: Discover lobby game IDs
The system SHALL poll `https://openfront.io/api/public_lobbies` and persist any newly observed lobby `gameID` values for results fetching.

#### Scenario: New lobby game ID observed
- **WHEN** a lobby `gameID` is seen that is not already tracked
- **THEN** the system records it for results fetching

### Requirement: Persist tracked games
The system SHALL persist tracked game IDs and their next-attempt timestamps so pending results survive restarts.

#### Scenario: Restart preserves pending games
- **WHEN** the bot restarts
- **THEN** previously tracked game IDs remain queued for results fetching

### Requirement: Fetch results with fixed 404 retry
The system SHALL fetch `/public/game/:gameID?turns=false` once per tracked game ID and reuse the payload for all guilds. If the response is 404, the system SHALL retry the same game ID 60 seconds later without exponential backoff.

#### Scenario: Game results not yet available
- **WHEN** fetching `/public/game/:gameID?turns=false` returns 404
- **THEN** the system schedules another attempt 60 seconds later

#### Scenario: Multiple guilds match a game
- **WHEN** multiple guilds have results enabled for the same game
- **THEN** the system uses the same fetched game payload for all guilds

### Requirement: Honor Retry-After for lobby rate limits
The system SHALL respect the `Retry-After` header when the public lobby endpoint responds with HTTP 429.

#### Scenario: Lobby poll rate limited
- **WHEN** `https://openfront.io/api/public_lobbies` responds with 429 and a Retry-After value
- **THEN** the next lobby poll is delayed by that duration

### Requirement: Seed latest finished games for testing
The system SHALL provide an admin-only `/post_game_results_test` command that fetches finished games from the last 2 hours of `/public/games`, enqueues their game IDs for processing, and does not post to the results channel.

#### Scenario: Admin seeds latest games
- **WHEN** an admin runs `/post_game_results_test`
- **THEN** game IDs from the last 2 hours are enqueued and no public results message is posted

