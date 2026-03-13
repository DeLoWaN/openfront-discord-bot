# clarify-backfill-overlap-replay Tasks

## 1. Persist cache and run-state semantics

- [x] 1.1 Widen shared cached payload storage so Team turn payloads can be
  stored without truncation and add migration coverage for existing databases.
- [x] 1.2 Extend persisted backfill run and per-game state so overlap skips,
  explicit replay work, cache-integrity failures, and terminal outcomes can be
  reported separately.

## 2. Update backfill and replay behavior

- [x] 2.1 Change ordinary `start` and `resume` flows to skip games that were
  already hydrated successfully in earlier runs instead of replaying them by
  default.
- [x] 2.2 Keep `replay` as the explicit cache-only rebuild path and report
  unreadable cached payloads as cache-integrity failures without silently
  crawling upstream data.
- [x] 2.3 Allow ordinary hydration flows to invalidate unreadable cache and
  refetch upstream detail when repairable work still needs hydration.

## 3. Surface operator-readable progress

- [x] 3.1 Update CLI status and logging summaries to distinguish clean
  completion, completion with failures, skipped known history, explicit replay
  work, cache-integrity failures, and aggregate refresh activity.
- [x] 3.2 Document or rename the refresh counter semantics so operators can
  tell it measures aggregate refresh executions rather than hydrated games.

## 4. Verify overlap and cache-repair behavior

- [x] 4.1 Add regression tests for overlapping backfills that skip previously
  hydrated games during ordinary `start` and `resume` flows.
- [x] 4.2 Add regression tests for explicit replay with unreadable cached
  payloads and for ordinary hydration repairing invalid cache via refetch.
- [x] 4.3 Add regression coverage for status and log output so the new counters
  and run outcomes remain operator-readable.
