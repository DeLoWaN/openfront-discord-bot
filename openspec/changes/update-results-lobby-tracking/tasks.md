## 1. Implementation
- [x] 1.1 Add `results_lobby_poll_seconds` to config parsing and `config.example.yml` (default 2s).
- [x] 1.2 Extend `OpenFrontClient` with `fetch_public_lobbies` against `https://openfront.io/api` and Retry-After handling for 429s.
- [x] 1.3 Add a central DB table/model for tracked game IDs with `next_attempt_at` persistence.
- [x] 1.4 Replace the per-guild results scheduler with a global lobby tracking loop that inserts new lobby game IDs into the tracked table.
- [x] 1.5 Process due tracked game IDs from the DB, fetch each `/public/game/:gameID` once, reuse existing result parsing/posting logic across guilds, and keep `PostedGame` de-duplication per guild.
- [x] 1.6 Add admin-only `/post_game_results_test` to enqueue finished games from the last 2 hours of `/public/games` (no public output).
- [x] 1.7 Update fakes/tests for lobby tracking, persisted queue, queued fetch retries, and test command behavior.

## 2. Validation
- [x] 2.1 Run `pytest`.
