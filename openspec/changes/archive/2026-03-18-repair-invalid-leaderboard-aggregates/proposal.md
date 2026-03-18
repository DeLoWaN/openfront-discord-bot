# Proposal: Repair Invalid Leaderboard Aggregates

## Why

The public leaderboard can currently publish mathematically impossible values,
such as a player showing more wins than games and win rates above `100%`. This
breaks trust in one of the main public product surfaces.

The current leaderboard API renders stored `GuildPlayerAggregate` values
directly, and the aggregate rebuild path itself computes FFA and Team wins and
games in lockstep from persisted participants. Re-ingesting the same
`openfront_game_id` is idempotent in the current ingestion path, so the most
likely source of these impossible rows is stale or previously corrupted
aggregate data rather than repeated same-game ingestion.

Ordinary historical backfill reruns over the same date range also do not heal
that state today. Known readable history is skipped, and skipped games do not
cause affected guild aggregates to be rebuilt, so operators can rerun the same
window without reprocessing games while still leaving bad stored aggregates in
place.

## What Changes

- Enforce aggregate validity for published leaderboard and profile stats so
  impossible ratios such as `wins > games` are no longer exposed publicly.
- Update ordinary historical backfill behavior so skipped known-history games
  still trigger guild aggregate refresh from already stored participant data,
  without replaying or re-ingesting those games.
- Add aggregate validation around rebuild and read paths so invalid stored rows
  are detected explicitly instead of silently rendered.
- Replace impossible leaderboard test fixtures with valid data and add
  regression coverage for stale aggregate repair and rerun idempotence.
- Update the relevant OpenSpec requirements so leaderboard math validity and
  rerun refresh semantics are part of the contract.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `guild-player-leaderboards`: leaderboard rows must publish mathematically
  valid wins, games, ratios, and win rates.
- `guild-stats-api`: leaderboard and player-profile payloads must not expose
  invalid aggregate ratios.
- `historical-backfill-pipeline`: ordinary reruns over known readable history
  may refresh affected guild aggregates from stored observations without
  replaying those games.

## Impact

- Affected code: `src/services/openfront_ingestion.py`,
  `src/services/guild_stats_api.py`, `src/services/historical_backfill.py`, and
  leaderboard/backfill regression tests.
- No new external dependencies are required.
- Public HTTP routes remain unchanged, but invalid stored leaderboard rows will
  no longer be rendered as if they were valid stats.
