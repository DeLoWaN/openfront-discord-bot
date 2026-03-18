# Design: Skip Known History During Discovery

## Context

Ordinary backfill runs already recognize prior successful history, but they do
so only after discovery has queued `BackfillGame` rows and hydration starts
processing them. On heavily overlapping windows this produces large pending
sets, repeated cache-read checks during hydration, and progress logs dominated
by work that never needed to enter the hydration queue.

The change needs to preserve three existing contracts. First, `replay` remains
the only workflow that intentionally reparses known history. Second, ordinary
flows must still repair unreadable cache by letting hydration refetch upstream
detail. Third, operators still need visible counters that explain why a run saw
many games but hydrated only a subset of them.

## Goals / Non-Goals

**Goals:**

- Exclude known readable history before ordinary discovery queues hydration
  work.
- Persist and report a dedicated discovery-skip counter for that overlap.
- Keep unreadable-cache repair behavior unchanged for ordinary `start` and
  `resume`.
- Preserve replay semantics and avoid changing CLI commands.

**Non-Goals:**

- Change replay behavior or make replay depend on discovery filters.
- Redesign discovery windows, cursor semantics, or ingestion logic.
- Preserve hydration-phase skip accounting exactly as it exists today for
  overlap that can now be excluded earlier.

## Decisions

### 1. Ordinary discovery performs the prior-history skip check

Team and FFA discovery will check each candidate `gameId` before creating the
run-local `BackfillGame` row. If an earlier run already completed that game and
its cached payload is readable, discovery will exclude it immediately and
increment a dedicated skip counter instead of queuing hydration work.

This reduces queue growth and moves the expensive overlap decision to the point
where the system still has only a candidate `gameId`, not a queued hydration
row.

Alternatives considered:

- Keep the current hydration-time check: lowest risk, but it does not solve the
  queue growth and per-run scan cost.
- Create `BackfillGame` rows already marked `skipped_known`: keeps row-level
  traceability, but leaves most of the storage and query overhead in place.

### 2. Discovery skip eligibility stays strict: prior success plus readable cache

Discovery will use the same policy boundary as ordinary hydration skip:
previous run status must be `completed`, and the cached payload must be
readable. If cache lookup or deserialization fails, discovery must not exclude
the game. It should queue normal hydration so the existing repair path can
refetch and rewrite cache.

This preserves the current safety property that unreadable historical cache is
repairable during ordinary backfill rather than silently discarded.

Alternatives considered:

- Skip on prior success alone: faster lookup, but it breaks cache repair by
  preventing ordinary runs from reaching hydration.
- Skip on cache presence alone: too weak, because stale or unreadable cache is
  not enough to guarantee safe exclusion.

### 3. Operators see a separate discovery overlap counter

The run model and CLI status will gain a dedicated counter for games skipped
during discovery. Existing `discovered_count` remains the count of queued work
for the run, which keeps its meaning stable. Hydration-phase `skipped` can then
shrink naturally as ordinary overlap moves earlier in the pipeline.

This keeps operator output interpretable without forcing `discovered` to become
an ambiguous “seen versus queued” metric.

Alternatives considered:

- Reinterpret `discovered_count` as total seen games: simple model change, but
  it would silently break existing operational expectations.
- Reuse hydration `skipped_known_count` for both phases: lower schema churn,
  but it hides where the skip occurred and makes debugging harder.

### 4. Hydration keeps its existing skip guard as a fallback

`hydrate_backfill_run` should continue checking for known history before fetch
or ingest. That guard still matters for rows created before this change,
partially discovered runs resumed after deployment, and any manual or legacy
rows that enter the queue.

Alternatives considered:

- Remove the hydration-time guard after moving the filter earlier: reduces
  duplicate logic, but weakens backward compatibility and makes partial runs
  riskier across deployment boundaries.

## Risks / Trade-offs

- [Discovery now performs extra historical lookups] -> Keep the eligibility
  query narrow and keyed by `openfront_game_id`, then validate with backfill
  tests against overlap-heavy scenarios.
- [Counters shift between phases] -> Expose a dedicated discovery skip counter
  in CLI summaries and progress logs so the moved behavior is explicit.
- [Partially discovered runs may mix old and new semantics] -> Keep the
  hydration fallback skip path so resumed runs remain correct during rollout.
- [Readable-cache checks during discovery could duplicate hydration logic] ->
  Share helper functions instead of forking the policy in multiple places.

## Migration Plan

1. Add an additive persisted counter to the backfill run model and schema for
   discovery-phase known-history skips.
2. Update ordinary discovery paths to classify eligible overlap before
   `_queue_game`.
3. Update CLI summaries, status output, and progress logging to expose the new
   counter.
4. Keep hydration fallback skip behavior in place for compatibility and partial
   runs.
5. Update tests for discovery filtering, unreadable-cache repair, and CLI
   output.

Rollback can leave the additive schema in place and revert behavior to the
current hydration-only skip classification if needed.

## Open Questions

- Should the CLI label the new counter as `discovery_skipped`, `skipped_early`,
  or another shorter operator-facing name?
