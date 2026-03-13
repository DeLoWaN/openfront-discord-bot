# Add Resumable Hybrid Backfill Design

## Context

The current backfill flow was added as a simple extension of the ingestion
worker. It requests a historical `/public/games` window, fetches every game
detail serially, ingests matching games, and returns one summary at the end.
That shape is acceptable for short ranges but it breaks down for month-scale
history because it has three structural problems:

- Team and Free For All discovery are both sourced from the global public games
  feed, even though team discovery can be scoped much more tightly by clan tag.
- Progress is in-memory only, so interruption forces the operator to restart
  from the beginning.
- Raw game payloads are discarded after ingestion, so widening match rules or
  fixing downstream logic requires another crawl of the upstream API.

The current schema already separates guild-relevant observed data from other
domain records. That separation should be preserved. Historical crawling needs
its own durable operational state and its own raw game cache rather than
overloading `ObservedGame` with every fetched payload.

## Goals / Non-Goals

**Goals:**

- Support month-scale historical backfills for guild stats.
- Preserve historical team and Free For All coverage.
- Avoid repeating slow OpenFront crawls when ingestion logic changes or an
  operator needs to replay history.
- Make backfill runs resumable, observable, and safe to stop and restart.
- Provide a dedicated operator CLI for launching and monitoring historical
  backfill work.
- Keep schema changes additive and compatible with the current worker/service
  layering.

**Non-Goals:**

- Store OpenFront turn data.
- Introduce an external queue system or new infrastructure dependency.
- Change the public website or leaderboard semantics directly.
- Make the live results-posting path depend on the historical cache.

## Decisions

### 1. Split discovery by source: clan sessions for team, public games for FFA

Historical team discovery will use `/public/clan/:tag/sessions` for every
tracked guild clan tag. Each session row contributes a `gameId`, which is
deduplicated before hydration. Historical Free For All discovery will keep
using `/public/games`, but only as a discovery surface. The worker will page
through API-compliant windows, inspect the list metadata, and enqueue only
rows whose `mode` is `Free For All`.

This keeps exact team coverage without paying for a global team-game scan and
limits expensive game-detail fetches to the FFA portion of the global feed.
Backfill range semantics will follow upstream behavior: filtering is based on
game start time, using `gameStart` for clan-session rows and `start` for public
games rows.

Alternatives considered:

- Global public games for both team and FFA: simplest code path, but too much
  wasted discovery and detail hydration.
- Clan sessions only: fast for guild history, but misses historical FFA games.

### 2. Separate raw cache storage from guild-relevant observed games

The system will introduce a dedicated raw game cache table keyed by
`openfront_game_id`. It stores the turn-free payload, fetch metadata, and
enough summary fields to support operational queries. `ObservedGame` remains
the guild-relevant domain record and is only written when ingestion determines
that a cached payload matches one or more tracked guild tags.

This preserves the current meaning of observed data while allowing the worker
to retain irrelevant but potentially useful historical payloads for replay.

Alternatives considered:

- Reuse `ObservedGame.raw_payload` for every fetched game: mixes operational
  cache state with guild-domain state and bloats guild-scoped tables with
  irrelevant games.
- File-based cache outside the database: simpler writes, but worse portability,
  weaker queryability, and harder resume semantics.

### 3. Model backfill as a durable discovery-and-hydration pipeline

Backfill will be split into durable stages:

1. Discovery streams advance cursors and enqueue unique game ids.
2. Hydration workers fetch or reuse cached payloads.
3. Ingestion consumes cached payloads and records affected guild ids.
4. Aggregate refresh runs in batches after hydration progress checkpoints.

The shared schema will add run-state tables for backfill runs, discovery
cursors, and pending game ids. This allows operators to resume interrupted
runs, inspect progress, and retry failures without rediscovering or refetching
already completed work.

Queued work will be deduplicated by `openfront_game_id` at persistence time so
overlapping clan-session windows, repeated FFA pages, or resumed runs do not
create duplicate hydration work for the same game.

Alternatives considered:

- Single coroutine with an on-disk checkpoint file: lower implementation cost,
  but weaker operational visibility and harder coordination with shared DB
  state.
- Fully synchronous queue draining: easier to reason about, but too slow for
  month-scale history.

### 4. Use bounded concurrency for detail hydration

Game detail hydration will use a small async worker pool with a semaphore
limit, rather than one request at a time. Discovery remains mostly sequential
per source stream so cursor state is simple, but hydration can progress across
queued game ids concurrently. Transient fetch failures are recorded per queued
item and retried according to the existing OpenFront client retry behavior plus
run-level retry accounting.

This improves throughput without turning the worker into an unbounded API
hammer.

Alternatives considered:

- Keep serial hydration: lowest complexity, but too slow for the required
  history ranges.
- High parallelism with no durable queue: faster in ideal conditions, but too
  fragile under rate limits or process restarts.

### 5. Log progress from durable counters, not ad hoc prints

The worker will report progress using run-level counters such as discovered,
cached, ingested, matched, failed, and refreshed. Logging will happen at run
start, on periodic progress intervals, on cursor advancement, and on run
completion/failure. Because progress is persisted, status can also be exposed
through CLI output or later operational commands without parsing logs.

The log lines should include the run id, source stream, current cursor/window,
and enough counters to tell whether the worker is moving forward during a long
historical run.

Alternatives considered:

- Only add `print()` statements: helps local runs, but does not solve resume or
  status inspection.
- Build a UI first: out of scope for this change.

### 6. Provide a dedicated backfill CLI instead of reusing existing commands

The system will expose dedicated external CLI commands for historical backfill
operations, separate from the existing guild-site management CLI. The CLI will
act as the operator control plane for this feature: creating runs, resuming
interrupted runs, inspecting run status and progress, and replaying cached
history without a new crawl.

This keeps operational workflows explicit and avoids mixing long-running data
maintenance commands into unrelated guild provisioning surfaces.

Alternatives considered:

- Extend the guild-site CLI: would blur two unrelated operator domains and
  make the command surface harder to discover.
- Expose worker-only Python entrypoints: workable for development, but weak for
  repeatable operations and status inspection.

## Risks / Trade-offs

- [FFA discovery still depends on the global public games feed] → Restrict the
  expensive detail hydration phase to `mode == "Free For All"` rows and make
  the work resumable.
- [Date filtering could drift from upstream semantics] → Treat backfill ranges
  as game-start-time filters everywhere and test both included and excluded
  boundary cases.
- [Raw cache grows large over months of history] → Store turn-free payloads
  only, keep cache rows separate from observed stats tables, and make retention
  policy a later operational decision.
- [More schema and state complexity] → Keep the tables single-purpose and
  additive, and reuse existing service-layer ingestion logic where possible.
- [CLI surface may drift from worker behavior] → Make the CLI a thin wrapper
  around persisted run services rather than duplicating orchestration logic.
- [Concurrent hydration may trigger rate limits] → Use bounded concurrency and
  rely on the existing OpenFront client retry behavior for transient errors.
- [Replay could diverge from the original crawl] → Cache the exact turn-free
  payload used for ingestion and prefer replay from cache over refetching.

## Migration Plan

1. Add new shared models and additive schema bootstrap for backfill runs,
   cursors, queued game ids, and cached game payloads.
2. Add discovery services for clan-session team history and global FFA history.
3. Add hydration workers that reuse cache entries before making detail calls.
4. Add replay ingestion from cached payloads and batch aggregate refreshes.
5. Add the dedicated backfill CLI for run creation, resume, status, and replay.
6. Add worker logging and operator-facing summary/status output.
7. Run the new backfill path on a bounded historical range first, then expand
   to longer windows once throughput and resume behavior are verified.

Rollback strategy:

- Leave the current observed-game schema intact.
- Treat the new backfill state tables as additive.
- If the new worker path fails, stop the run and keep existing observed data;
  the cache and run-state rows can remain for later retry or cleanup.

## Open Questions

- Should replay be scoped by time range, by run id, or both?
- What default concurrency limit is safe enough for the OpenFront API in
  production?
- Should cache retention be indefinite initially, or should the first version
  include an operator-controlled cleanup command?
