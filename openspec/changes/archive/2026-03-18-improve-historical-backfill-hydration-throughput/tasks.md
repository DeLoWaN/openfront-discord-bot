# Tasks: Improve Historical Backfill Hydration Throughput

## 1. Move aggregate refresh out of the hydration hot path

- [x] 1.1 Change ordinary backfill hydration to collect affected guild ids
  across the run and refresh aggregates after queued hydration completes.
- [x] 1.2 Update run progress and completion reporting so deferred aggregate
  refresh remains operator-readable without implying the run finished early.

## 2. Reduce redundant local hydration and ingest work

- [x] 2.1 Trim avoidable ORM round-trips and per-game state saves in the
  hydration path without changing durable failure accounting.
- [x] 2.2 Reduce redundant payload and participant write work in ordinary
  backfill ingest while preserving the final observed-game and participant
  state.

## 3. Verify throughput-oriented behavior

- [x] 3.1 Add or update tests for deferred end-of-run aggregate refresh and for
  runs with no affected guilds.
- [x] 3.2 Add or update tests covering the reduced local hydration/ingest work
  and preserving existing replay, skip-known-history, and failure behavior.

## 4. Smooth OpenFront throttling and calibration behavior

- [x] 4.1 Replace hidden bursty backfill defaults with explicit CLI OpenFront
  tuning flags and safe smoothed default values for `start` and `resume`.
- [x] 4.2 Add `probe-openfront` so operators can measure bounded
  `?turns=false` fetch behavior without creating backfill runs, caches, or
  ingested observations.
- [x] 4.3 Apply a minimum fallback cooldown when a `429` omits a useful
  positive retry-after value.

## 5. Support OpenFront bypass mode

- [x] 5.1 Add config-driven OpenFront bypass header and optional `User-Agent`
  parsing.
- [x] 5.2 Apply bypass mode globally across OpenFront callers and warn
  operators when `429` still occurs with the bypass configured.
