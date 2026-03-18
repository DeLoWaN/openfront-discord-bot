# Improve Historical Backfill Hydration Throughput

## Why

Historical backfill hydration is still much slower than expected even when
OpenFront is not rate limiting requests. Real runs spend minutes per hundred
games with `openfront_rate_limits=0`, which indicates the main bottleneck is
local hydration, ingest, and aggregate-refresh work rather than upstream
cooldowns. Later operator runs also showed that bursty backfill settings can
trip upstream `429` cooldowns, so the final shipped behavior needs both a
faster local hydration path and a smoother, more explicit OpenFront request
profile.

## What Changes

- Change historical backfill so affected guild aggregates are refreshed after
  hydration completes instead of repeatedly during the hot hydration loop.
- Reduce redundant local hydration work by cutting repeated ORM round-trips and
  unnecessary per-game payload persistence during ingest and cache updates.
- Replace hidden bursty backfill OpenFront defaults with explicit CLI tuning
  flags and safe non-bursty defaults.
- Add a bounded `probe-openfront` CLI command that measures OpenFront fetch
  behavior over a historical sample without creating backfill runs or ingesting
  data.
- Apply a minimum cooldown when OpenFront returns `429` with an absent or
  zero-second retry-after value so retries do not immediately re-burst into the
  same upstream limit.
- Support a config-driven OpenFront bypass header and `User-Agent` that apply
  to every OpenFront request. When that bypass is configured, client-side
  gating and cooldown waits are disabled globally, and suspicious `429`
  responses are logged with an operator hint.
- Preserve durable run tracking, replay behavior, overlap skipping, and
  operator-readable progress and failure reporting.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `historical-backfill-cli`: ordinary backfill defaults and operator tooling
  will change so OpenFront fetches use a safe smoothed profile by default and
  operators can probe a candidate profile without ingesting data.
- `historical-backfill-pipeline`: hydration and aggregate refresh behavior will
  change so ordinary backfill spends less time in local ingest/rebuild work,
  performs guild aggregate refresh at the end of the run, and avoids immediate
  retry bursts when upstream rate limiting omits a useful cooldown.
- `openfront-upstream-resilience`: shared OpenFront request handling will
  support an optional configured bypass mode that sends a custom header and
  `User-Agent` on every request and disables local rate limiting when the
  operator has an upstream-approved bypass key.

## Impact

- Affected code: `src/services/historical_backfill.py`,
  `src/services/openfront_ingestion.py`, `src/apps/cli/backfill.py`,
  `src/core/openfront.py`, `src/core/config.py`, app entrypoints that build
  `OpenFrontClient`, `config.example.yml`, and backfill/OpenFront tests.
- Adds one new public CLI command, `historical-backfill probe-openfront`, and
  explicit OpenFront tuning flags on `start` and `resume`.
- Progress logs and final run summaries may show fewer mid-run aggregate
  refreshes because refresh work shifts out of the hydration hot path, and
  OpenFront logs may now expose safer default profiles, calibration metrics,
  and suspicious bypass-key failures.
