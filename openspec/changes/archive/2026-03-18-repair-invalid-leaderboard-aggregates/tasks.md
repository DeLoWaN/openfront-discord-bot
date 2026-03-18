# Tasks: Repair Invalid Leaderboard Aggregates

## 1. Aggregate validity and API contract

- [x] 1.1 Add shared validation for stored guild aggregate math, covering at
  least Team and FFA `wins <= games`, recent-game counts not exceeding total
  mode game counts, and win rates remaining within valid bounds.
- [x] 1.2 Apply that validation in the aggregate rebuild path so newly rebuilt
  `GuildPlayerAggregate` rows cannot persist impossible competitive stats.
- [x] 1.3 Apply the same validation in the guild stats API payload shaping so
  invalid legacy rows are not published on leaderboard or player-profile
  responses.
- [x] 1.4 Replace impossible leaderboard test fixtures with valid aggregate
  data and add regression coverage for invalid-row exclusion.

## 2. Backfill rerun repair behavior

- [x] 2.1 Update skipped-known ordinary backfill handling so a known readable
  game can still contribute affected guild ids for aggregate refresh using
  existing stored participant rows.
- [x] 2.2 Keep ordinary reruns non-replaying: skipped-known games must remain
  excluded from fetch and re-ingest work.
- [x] 2.3 Add regression coverage proving that rerunning the same date window
  can repair stale aggregates from stored observations without reprocessing the
  underlying games.
- [x] 2.4 Add or update idempotence tests showing that repeated ingestion of
  the same `openfront_game_id` does not inflate wins or games.

## 3. Spec and verification

- [x] 3.1 Update the leaderboard and stats API spec deltas so public Team and
  FFA rows must always expose mathematically valid wins, games, ratios, and
  win rates.
- [x] 3.2 Update the historical backfill pipeline spec delta so ordinary
  skipped-known history may still trigger aggregate refresh from stored
  observations.
- [x] 3.3 Run the targeted automated tests covering guild stats API,
  leaderboard/profile serialization, ingestion idempotence, and historical
  backfill rerun behavior.
