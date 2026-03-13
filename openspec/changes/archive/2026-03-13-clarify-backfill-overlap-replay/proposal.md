# clarify-backfill-overlap-replay Proposal

## Why

Historical backfills currently blur three different situations into the same
operator story: in-run discovery deduplication, cross-run cache reuse, and
real hydration failures. That makes overlapping date ranges hard to reason
about and turns broken cached Team payloads into misleading `failed` counts for
games that were already known.

We need a clearer contract before changing the pipeline: normal backfills
should skip already-ingested history by default, while operators should still
have an explicit replay path when they want to rebuild derived data from cache.

## What Changes

- Change overlapping backfill behavior so ordinary `start` and `resume`
  operations do not reprocess games that were already hydrated successfully in
  earlier runs.
- Preserve replay as an explicit operator action for rebuilding derived data
  from cached payloads without performing a new crawl.
- Clarify persisted run counters and status output so skipped known games,
  cache reuse, and true failures are distinguishable in logs and CLI output.
- Define cache integrity behavior for Team payloads so truncated or otherwise
  unreadable cached payloads are treated as repairable cache problems rather
  than duplicate or replay ambiguity.
- Require durable cache storage that can retain full Team turn payloads needed
  for replay and backfill repair workflows.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-backfill-pipeline`: define default skip behavior for previously
  hydrated games, separate overlap/counter semantics from real failures, and
  specify cache-repair handling during hydration or replay.
- `historical-backfill-cli`: clarify that `start` and `resume` skip already
  known history by default while `replay` remains the explicit rebuild path,
  with operator-readable status counters.
- `openfront-game-cache`: require storage and recovery behavior that preserves
  complete Team payloads and supports repairing unreadable cached payloads.

## Impact

- Affected code will include the historical backfill CLI, run/counter models,
  pipeline orchestration, and shared cache schema.
- MariaDB additive schema work is likely needed for cached Team payload
  storage and any new persisted counters.
- Operator-visible behavior changes for overlapping backfills and status
  inspection, but replay remains available as the explicit rebuild mechanism.
