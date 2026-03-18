# Proposal: Skip Known History During Discovery

## Why

Ordinary historical backfills currently rediscover large amounts of known
history and only classify that overlap as skipped during hydration. This keeps
routine runs correct, but it inflates per-run work, expands the queued
hydration set, and makes long overlapping windows slower than necessary.

## What Changes

- Change ordinary `start` and `resume` discovery so known readable history is
  excluded before hydration work is queued.
- Add a persisted counter for games skipped during discovery because earlier
  runs already hydrated them successfully and the cached payload remains
  readable.
- Keep unreadable cache behavior conservative: discovery must not exclude games
  whose prior cache cannot be read, so ordinary hydration can still repair that
  cache through upstream refetch.
- Update CLI status and progress reporting so operators can distinguish queued
  discoveries from overlap skipped during discovery.
- Preserve explicit `replay` as the only workflow that intentionally reparses
  known history from cache.

## Capabilities

### New Capabilities

- `historical-backfill-discovery-overlap-skips`: Track and report known-history
  overlap that is excluded during discovery before hydration is queued.

### Modified Capabilities

- `historical-backfill-pipeline`: Ordinary discovery skips known readable
  history earlier and records those exclusions separately from hydration work.
- `historical-backfill-cli`: Run summaries and status output report discovery
  skip counts alongside existing historical backfill counters.

## Impact

- Affected code: `src/services/historical_backfill.py`,
  `src/apps/cli/backfill.py`, shared backfill models/schema, and historical
  backfill tests.
- No new external dependencies or public command changes are required.
- Operator-visible status output will gain a separate discovery-skip counter,
  and skip counts may shift away from hydration-phase totals for overlapping
  runs.
