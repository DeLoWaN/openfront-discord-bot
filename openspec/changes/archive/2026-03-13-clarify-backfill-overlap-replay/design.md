# clarify-backfill-overlap-replay Design

## Context

The current historical backfill pipeline is optimized for replayability, but
its operator semantics are unclear when a requested range overlaps history that
was already hydrated successfully in earlier runs. A normal `start` or `resume`
can currently consume prior cached payloads, so cross-run overlap looks similar
to in-run deduplication and real hydration failures in logs and counters.

That ambiguity becomes more damaging for Team games because cached turn payloads
can exceed the current storage size. Once a cached Team payload becomes
unreadable, later overlap or replay attempts surface as `failed`, even though
the underlying game was already known. We need a design that keeps replay
available as a deliberate repair/rebuild workflow while making ordinary
backfills conservative and operator-readable.

## Goals / Non-Goals

**Goals:**

- Make ordinary backfill `start` and `resume` skip games that were already
  hydrated successfully in earlier runs.
- Keep `replay` as the explicit operator path for reprocessing cached payloads.
- Separate overlap outcomes, replay outcomes, cache integrity problems, and
  true fetch or ingest failures in persisted counters and status output.
- Ensure cached Team payload storage can retain complete replay data without
  truncation.
- Define how unreadable cached payloads are repaired or reported.

**Non-Goals:**

- Change discovery window sizing, date-boundary rules, or Team/FFA discovery
  sources.
- Remove replay support or require replay to make network calls.
- Redesign the guild aggregate computation model itself.

## Decisions

### 1. Ordinary backfill skips prior successful history; replay stays explicit

`start` and `resume` will treat cross-run overlap as known history by default.
If a game has already been hydrated successfully in an earlier run, ordinary
backfill will not re-ingest it again. `replay` remains the explicit rebuild
mode when an operator wants to reprocess cached payloads on purpose.

This keeps routine backfills predictable and matches the user's chosen policy:
overlap should be conservative unless the operator explicitly asks for replay.

Alternatives considered:

- Always replay known history: preserves current flexibility but keeps operator
  counters noisy and makes overlap look like work rather than reuse.
- Always skip everywhere: simpler, but breaks legitimate rebuild and repair
  workflows that depend on cached payload replay.

### 2. Distinguish overlap, replay, cache, and failure outcomes in persisted status

Run status will report overlap outcomes separately from real failures. The
proposal does not lock exact field names, but the persisted and displayed model
must distinguish at least:

- games skipped because they were already hydrated successfully
- games replayed explicitly from cache
- cache integrity failures
- fetch or ingest failures
- aggregate refresh activity

The lifecycle outcome should also distinguish a clean completion from a pass
that ended with unresolved failures so operators do not misread
`completed + failed > 0` as a clean run.

Alternatives considered:

- Keep existing counters and document them better: lowest code churn, but it
  does not solve misleading operator output.
- Derive all overlap semantics from per-game rows only: avoids new counters,
  but makes CLI status and logs expensive and harder to read during long runs.

### 3. Replay remains crawl-free; ordinary backfill may repair unreadable cache

`replay` exists specifically to rebuild from cached payloads without a new
crawl, so it must not silently refetch upstream data when cache is unreadable.
Instead, replay will report cache-integrity failures explicitly.

Ordinary `start` and `resume` already allow upstream fetches. If they
encounter an unreadable cached payload for work that still needs hydration,
they may treat it as repairable cache state: invalidate the unreadable cache
entry, refetch upstream detail, and replace the cache.

This preserves the no-crawl contract of replay while allowing routine backfill
operations to recover from bad cache state.

Alternatives considered:

- Let replay silently refetch: repairs more automatically, but breaks the
  replay contract and makes it impossible to know whether a rebuild was truly
  cache-backed.
- Never refetch unreadable cache anywhere: simpler behavior, but forces manual
  cleanup for recoverable runs.

### 4. Cache storage must be widened for Team replay payloads

Team turn payloads need durable storage that can hold full JSON without
truncation. The migration should widen the existing payload storage in a
forward-safe way and treat already-truncated payloads as invalid historical
cache that cannot be trusted for replay.

Alternatives considered:

- Keep current text-sized storage and compress payloads in place: possible, but
  adds encoding complexity while still needing migration logic.
- Move Team payloads to external files: avoids DB limits, but adds operational
  complexity and diverges from the current shared-schema design.

## Risks / Trade-offs

- [New counters increase model and CLI surface area] -> Keep the semantic split
  small and operator-focused rather than exposing every internal transition.
- [Previously truncated Team cache rows cannot be repaired locally] -> Mark
  them invalid and let ordinary backfill repair them through refetch, while
  replay reports them explicitly.
- [Lifecycle changes may affect existing operator expectations] -> Document the
  new status meanings in CLI output and tests, and preserve replay as the
  intentional rebuild escape hatch.
- [Widening cache columns requires DB migration work] -> Use a one-way safe
  widening migration and verify both fresh bootstrap and additive migration
  paths.

## Migration Plan

1. Add or widen shared-cache storage so Team turn payloads are no longer
   truncated.
2. Introduce persisted overlap and cache-status counters plus any revised run
   lifecycle states.
3. Update `start`, `resume`, and `replay` flow semantics to follow the new
   policy.
4. Detect previously unreadable cached payloads and classify them as invalid
   cache for replay status.
5. Update CLI status output, logs, and tests to match the new counter and
   outcome contract.

Rollback would preserve existing cached data and schema widening where
possible, but behavioral rollback would mostly mean restoring the earlier
always-replay semantics in code.

## Open Questions

- Should the run model expose a dedicated `completed_with_failures` state, or
  should it keep `completed` and add an explicit outcome field?
- Should in-run discovery deduplication get its own operator counter, or is it
  enough to report only cross-run skips and explicit replays?
- Should ordinary backfill skip based on prior successful run history, valid
  cache presence, or both?
