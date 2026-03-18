# Design: Repair Invalid Leaderboard Aggregates

## Context

The public leaderboard can currently display impossible competitive stats such
as more wins than games and win rates above `100%`. The rendering layer is not
inventing these values: the leaderboard API serializes stored
`GuildPlayerAggregate` rows directly, including `ffa_win_count`,
`ffa_game_count`, and the derived ratio and win rate.

The current aggregate rebuild path already derives Team and FFA wins and games
from persisted `GameParticipant` rows in a mathematically coherent way. In that
path, FFA wins and FFA games are incremented together from the same observed
participant rows, and repeated ingestion of the same `openfront_game_id`
remains idempotent because the game row is upserted and its participants are
replaced before aggregates are rebuilt.

That points to a different failure mode: stale or previously corrupted
aggregate rows can remain visible even after later backfill reruns over the
same dates. Ordinary backfill currently skips known readable history and does
not add those skipped games' guilds to the affected aggregate refresh set, so
a rerun can preserve bad stored aggregate rows without reprocessing the games
that originally produced the correct participant history.

## Goals / Non-Goals

**Goals:**

- Ensure public leaderboard and player-profile payloads never publish invalid
  wins, games, or win rates.
- Make ordinary backfill reruns over known readable history repair stale guild
  aggregates from already stored participant data without replaying known
  games.
- Keep aggregate rebuild logic centralized in the existing participant-derived
  refresh path.
- Add regression coverage for invalid aggregate detection and rerun-based
  aggregate repair.

**Non-Goals:**

- Change Team or FFA scoring formulas.
- Rework OpenFront game ingestion identity rules or backfill discovery windows.
- Turn ordinary reruns into replay; known history should still be skipped for
  fetch and re-ingest purposes.
- Introduce a new public HTTP contract or new operator commands.

## Decisions

### Keep `refresh_guild_player_aggregates` as the only aggregate source of truth

The aggregate rebuild path in `openfront_ingestion` already recomputes player
rows from persisted `GameParticipant` observations and mode-specific rules.
That path should remain the only place that derives stored wins, games, recent
activity, and score inputs.

Alternative considered:

- Patch invalid counts directly in `GuildPlayerAggregate`. Rejected because it
  would hide the source-of-truth boundary and risks drifting from participant
  data.

### Add explicit aggregate validity checks at rebuild and read boundaries

Public leaderboard math should obey a small set of invariants:
`wins <= games`, recent game counts must not exceed mode game counts, and
derived win rates must stay within `0..1`. These checks should exist in two
places:

- at aggregate rebuild time, to catch impossible rows before they are
  persisted
- at API serialization time, to avoid publishing invalid legacy or stale rows
  that may already exist in the database

Alternative considered:

- Trust aggregate rows blindly and only fix historical data once. Rejected
  because one stale or manually corrupted row would still leak impossible stats
  publicly.

### Treat skipped known-history games as refresh-relevant during ordinary backfill

Ordinary backfill should continue skipping known readable history for fetch and
re-ingestion, but those skipped games can still prove which guilds need an
aggregate rebuild. When a queued `BackfillGame` is classified as known history,
the worker should inspect already persisted participant rows for the matching
`ObservedGame` and add the corresponding guild ids to the affected refresh set.

This preserves the existing no-replay contract while allowing reruns over the
same date range to repair stale aggregate rows from stored observations.

Alternatives considered:

- Leave skipped-known games out of the refresh set. Rejected because it keeps
  bad aggregates sticky across reruns.
- Re-ingest skipped-known games from cache to force a rebuild. Rejected because
  it blurs the distinction between ordinary rerun and explicit replay.

### Exclude invalid rows from public payloads instead of clamping them silently

If a stored aggregate row fails validation at API read time, the public API
should not invent repaired numbers by clamping wins down to games. The safer
behavior is to log the invalid row and exclude it from leaderboard/profile
output until the aggregate refresh path repairs it.

Alternative considered:

- Clamp wins and recompute win rate on the fly. Rejected because it would hide
  data corruption and make public output disagree with stored data.

## Risks / Trade-offs

- [Skipped-known refresh could rebuild more guilds than before] -> Mitigate by
  deriving guild ids only from persisted participants tied to the skipped game.
- [Validation could hide rows until repair runs] -> Mitigate by making
  ordinary backfill reruns repair affected guilds without replaying the known
  games.
- [Legacy invalid fixtures or assumptions may fail tests] -> Mitigate by
  replacing impossible seeded rows with valid fixtures and adding explicit
  invalid-row regression tests.

## Migration Plan

1. Add shared aggregate validation helpers around rebuild and API read paths.
2. Update ordinary backfill skipped-known handling so affected guilds from
   stored participants are queued for aggregate refresh.
3. Replace invalid leaderboard fixtures and add regression tests for rerun
   repair and idempotence.
4. Update the relevant OpenSpec requirements so public leaderboard math
   validity and ordinary-rerun aggregate refresh are part of the contract.

Rollback can revert the validation and skipped-known refresh behavior without a
schema migration because the change relies on existing stored observations and
aggregate tables.

## Open Questions

None. The desired behavior follows directly from the existing no-replay
backfill contract and the need to stop publishing impossible public stats.
