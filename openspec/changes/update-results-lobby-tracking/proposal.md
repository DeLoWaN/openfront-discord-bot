# Change: Track results via public lobbies

## Why
Polling `/public/games` only surfaces finished games, which delays result posts. The public lobbies endpoint only exposes current lobby IDs, so we must record each new game ID as it appears and poll for results until the game finishes.

## What Changes
- Replace `/public/games` polling with tracking `/api/public_lobbies` to discover new game IDs.
- Persist tracked game IDs in the central DB so restarts do not lose in-flight games.
- Fetch `/public/game/:gameID?turns=false` once per tracked game and reuse the result for all guilds; retry 404s on a fixed 60s cadence (no exponential backoff).
- Add an admin-only `/post_game_results_test` command to seed pending results with finished games from the last 2 hours of `/public/games` for fast testing (no public output).
- Add config for the lobby polling interval (default 2s), and honor Retry-After on 429 responses.

## Impact
- Affected specs: `game-results-posting`
- Affected code: `src/openfront.py`, `src/bot.py`, `src/config.py`, `config.example.yml`, `tests/*`
