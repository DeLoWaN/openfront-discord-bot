## ADDED Requirements

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
