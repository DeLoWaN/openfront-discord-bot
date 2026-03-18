# Proposal: Increase OpenFront Throughput With Safe Parallelism

## Why

The shared OpenFront gate currently serializes all traffic to one in-flight
request with a one-second success delay, which makes historical backfill
discovery and hydration slower than necessary. We need a modest throughput
increase that still obeys upstream `Retry-After` signals strictly and makes
Cloudflare throttling visible in backfill logs.

## What Changes

- Change the shared OpenFront gate from one global in-flight request to a fixed
  two-request cap with a shorter default success delay.
- Keep upstream cooldown headers authoritative and block new requests globally
  until their cooldown expires.
- Add rate-limit event reporting in `OpenFrontClient` so callers can count and
  log real upstream throttling.
- Persist backfill run counters for upstream throttling and include them in CLI
  summaries and progress logs.
- Run team and FFA discovery concurrently, and allow team discovery to use
  bounded per-cursor concurrency.

## Capabilities

### New Capabilities

- `historical-backfill-rate-limit-observability`: Track and report upstream
  cooldown events on historical backfill runs.

### Modified Capabilities

- `openfront-upstream-resilience`: The shared gate allows a fixed small amount
  of parallelism while continuing to honor upstream cooldown headers globally.
- `historical-backfill-pipeline`: Ordinary backfill discovery uses bounded
  concurrency that matches the safer, faster OpenFront gate.
- `historical-backfill-cli`: Run summaries and logs expose upstream cooldown
  counters for historical backfill runs.

## Impact

- Affected code: `src/core/openfront.py`,
  `src/services/historical_backfill.py`, `src/apps/worker/app.py`,
  `src/apps/cli/backfill.py`, shared models/schema, and backfill/OpenFront
  tests.
- No CLI flags or config knobs are added.
- Operator-visible logs and status output will expose Cloudflare / upstream
  cooldown counts and durations.
