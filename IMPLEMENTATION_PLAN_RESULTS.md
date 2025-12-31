# Implementation Plan: Game Results Posting

## Goal & Scope
- Post match results to a configured Discord channel shortly after a clan win is detected.
- Track wins for all clan tags stored in the guild database; treat them as aliases of the same guild.
- One embed per game. Use OpenFront clan sessions and game details to build the message.
- Per-guild settings and persistence; no cross-guild leakage.

## Requirements
### Functional
- Poll clan sessions for all stored clan tags.
- Use `start/end` filters based on `gameStart`.
- For each `hasWon=true` session, fetch game details using:
  - `GET /public/game/<gameId>?turns=false`
- Identify winners as players whose `clanTag` is in the winning tag set for that game.
- Opponents: group other `clanTag` values and count players (no names listed).
- Post an embed with:
  - Map name
  - Start date (embed timestamp)
  - Replay link `https://openfront.io/#join=<GAMEID>`
  - Game mode string: `X teams (Trios)` for named modes; `X teams (12 players per team)` for numeric values
- Mentions: if a winner username matches exactly one `users.last_openfront_username` (case-sensitive), mention that Discord user. If zero or multiple matches, keep plain username.
- Commands:
  - `/post_game_results_start`
  - `/post_game_results_stop`
  - `/post_game_results_channel`
  - `/post_game_results_interval`
- Extend `/status` to show last known OpenFront username.

### Timing
- Poll interval default: 60 seconds (configurable by command).
- Each poll should query the last 2 hours of sessions.
- On first enable, backfill the last 24 hours.

### Non-functional
- Use existing OpenFront backoff handling; add separate backoff for results polling.
- Dedupe posts via DB so the same game is never posted twice.
- Keep per-guild isolation and bounded concurrency.

## Data Model (Peewee, SQLite)
### New/Updated Columns
- `users`:
  - `last_openfront_username` TEXT NULL
- `settings`:
  - `results_enabled` INTEGER default 0
  - `results_channel_id` INTEGER NULL
  - `results_interval_seconds` INTEGER default 60
  - `results_last_poll_at` DATETIME NULL
  - `results_backoff_until` DATETIME NULL

### New Table
- `posted_games`:
  - `game_id` TEXT PRIMARY KEY
  - `game_start` DATETIME NULL
  - `posted_at` DATETIME NOT NULL
  - `winning_tags` TEXT NULL (optional JSON for debugging)

### Migrations
- Use `PRAGMA table_info` with `ALTER TABLE` for new columns, matching existing patterns.
- Create `posted_games` if missing.

## OpenFront API Integration
- Clan sessions:
  - `GET https://api.openfront.io/public/clan/<CLAN_TAG>/sessions?start=...&end=...`
- Game details:
  - `GET https://api.openfront.io/public/game/<gameId>?turns=false`

## Results Poller Architecture
- Add a results scheduler loop similar to the existing sync scheduler.
- Maintain a results queue with worker tasks (bounded concurrency).
- Per guild job:
  1) Validate `results_enabled` and `results_channel_id`.
  2) Respect `results_backoff_until`.
  3) Compute poll window:
     - First enable: `now - 24h` to `now`.
     - Otherwise: `now - 2h` to `now`.
  4) Fetch sessions for each clan tag; collect winning game IDs and winning tags.
  5) Skip any game ID present in `posted_games`.
  6) Fetch game details; build winners/opponents and embed.
  7) Post embed; record in `posted_games`.
  8) Update `results_last_poll_at = now`.

## Embed Format
- Title: celebratory (emoji encouraged).
- Fields:
  - Winners: list of mentions or usernames (one per line).
  - Opponents: `TAG: count` (one per line).
  - Game Info: map name, mode string, replay link.
- Timestamp: game start time.

## Commands
- `/post_game_results_start`
  - Enable posting, set `results_last_poll_at = now - 24h`.
- `/post_game_results_stop`
  - Disable posting without clearing state.
- `/post_game_results_channel <channel>`
  - Set channel ID for results posts.
- `/post_game_results_interval <seconds>`
  - Update interval (validate min 60).

## Username Tracking
- Store OpenFront username in `last_openfront_username`.
- Update on `/link` from `last_session_username`.
- Update during session-based win computations from most recent session (no extra API call).

## Cleanup
- Prune `posted_games` entries older than 7 days (daily cleanup loop).

## Testing Plan
- Unit tests for:
  - Dedupe by `posted_games`.
  - Winner/opponent aggregation.
  - Mention mapping (0/1/many matches).
  - Mode formatting (named vs numeric).
  - Commands start/stop/channel/interval.
  - `/status` includes `last_openfront_username`.

## Implementation Phases
1) DB changes + migrations.
2) OpenFront client methods for clan sessions and game details.
3) Results scheduler/worker + embed builder.
4) Slash commands + `/status` update.
5) Tests and cleanup logic.
