## Context
Results posting currently polls `/public/games` per guild and only sees games after they finish, which delays posts. The `https://openfront.io/api/public_lobbies` endpoint only exposes the current lobby game IDs (not all active games), so we must record each new game ID as it appears and poll for results until the game finishes.

## Goals / Non-Goals
- Goals:
  - Detect ended games within ~1 minute of completion.
  - Stop using `/public/games` for normal discovery; keep it only for debug seeding.
  - Preserve existing winner parsing and embed formatting.
  - Add a configurable lobby poll interval (default 2s).
  - Persist tracked game IDs across restarts.
  - Avoid duplicate `/public/game/:gameID` requests per guild.
- Non-Goals:
  - Rework winner logic or Discord embed formatting.
  - Change unrelated sync or role behavior.

## Decisions
- Add a global lobby tracking loop that polls `https://openfront.io/api/public_lobbies` at `results_lobby_poll_seconds` (default 2s).
- Persist tracked game IDs in the central DB (e.g., `TrackedGame` with `game_id`, `next_attempt_at`, `first_seen_at`) so the queue survives restarts.
- Treat each newly observed lobby game ID as a tracked game; do not rely on lobby disappearance to infer completion.
- Process tracked games in a worker loop:
  - Fetch `/public/game/:gameID?turns=false` once per tracked ID and reuse the payload for all guilds.
  - On 404, reschedule `next_attempt_at = now + 60s` (fixed cadence, no exponential backoff).
  - On 429, honor Retry-After (and otherwise rely on existing request backoff).
  - On success, run the existing posting logic per guild and remove the game ID from the tracked list once all guilds are processed or skipped.
- Add an admin-only command `/post_game_results_test` that fetches finished games from the last 2 hours of `/public/games` and enqueues their IDs; the command responds ephemerally without posting to the results channel.

## Alternatives Considered
- Continue polling `/public/games` with narrower windows: still delayed by archival timing.
- Per-guild lobby polling: multiplies request volume and increases 429 risk.
- WebSocket/event stream: not available in the public API.

## Risks / Trade-offs
- 2s lobby polling could trigger rate limiting; the interval is configurable and 429s are respected.
- Because only current lobby IDs are visible, missed polls could skip some games; the short interval mitigates this but does not eliminate it.
- Global queue adds scheduling logic; mitigated by keeping the worker loop simple and reusing existing posting code.

## Migration Plan
- Deploy with new config default; add a central DB table for tracked games.
- Existing results settings remain, but last-poll fields are no longer used for discovery.
- Seed command is optional for testing and does not affect normal operation.

## Open Questions
- None.
