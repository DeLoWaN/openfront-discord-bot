# Design: Increase OpenFront Throughput With Safe Parallelism

## Context

The current shared OpenFront coordination model intentionally serializes all
requests through one lease and a one-second post-success cooldown. That is safe
but expensive for long historical backfills because discovery and hydration
spend most of their time waiting on the gate rather than local work. The new
behavior needs to stay conservative around Cloudflare by respecting upstream
cooldowns immediately and by keeping global parallelism low and fixed.

Historical backfill is also the primary operator surface for this change, so
the run model and logs need to show how often the CDN actually slowed the run
down and by how much.

## Goals / Non-Goals

**Goals:**

- Increase effective OpenFront throughput with a fixed global cap of two
  in-flight requests.
- Reduce the default success spacing to 0.5 seconds when the upstream does not
  provide a cooldown.
- Preserve strict global handling of `Retry-After` and reset-style cooldown
  headers.
- Add run-local counters and warnings for real upstream throttling.
- Exploit the extra gate slot in historical backfill discovery.

**Non-Goals:**

- Add operator tuning knobs or environment configuration for the new limits.
- Change replay semantics or unrelated ingestion logic.
- Turn the shared gate into an unbounded worker queue.

## Decisions

### 1. Use a shared active-lease counter with one global cooldown deadline

The gate keeps one singleton state row with:

- `active_leases`
- `lease_expires_at`
- `cooldown_until`
- `cooldown_reason`

Acquisition succeeds when `cooldown_until` has passed and `active_leases < 2`.
Each acquire extends the shared lease expiry, and expired lease state resets
the active count. Release decrements the active count and extends the cooldown
deadline if needed.

This is simpler than managing per-owner slot rows while still keeping crash
recovery bounded by lease expiry.

### 2. Rate-limit events are emitted only for real upstream stops

`OpenFrontClient` will emit an `OpenFrontRateLimitEvent` only when an upstream
response or retry path produces an actual cooldown, not on ordinary successful
responses. The event carries status, cooldown seconds, and source
(`retry-after`, `retry-after-ms`, reset header, or fallback) so callers can
count true Cloudflare / upstream stops.

### 3. Backfill owns the operator counters

Historical backfill runs persist the following counters:

- `openfront_rate_limit_hit_count`
- `openfront_retry_after_count`
- `openfront_cooldown_seconds_total`
- `openfront_cooldown_seconds_max`

The backfill service attaches a temporary observer to the client during
`start` / `resume`, increments those counters as events arrive, and logs a
warning for each `429`.

### 4. Discovery uses bounded concurrency, hydration keeps its local pool

Worker and CLI backfill entrypoints run team and FFA discovery concurrently
with `asyncio.gather`. Team discovery additionally uses a small local semaphore
of two cursor tasks so the second shared gate slot gets used during overlap-
heavy backfills. Hydration keeps its existing local concurrency control and
benefits automatically from the new shared gate.

## Risks / Trade-offs

- [A looser gate could trigger more throttling] -> Keep the global cap fixed at
  two and keep upstream cooldown headers authoritative.
- [Lease expiry can briefly over-admit after a crash] -> Use a short shared
  lease expiry and reset stale state on acquire.
- [Concurrent discovery can make logs noisier] -> Keep existing per-window log
  shape and add only rate-limit counters, not extra debug chatter.
- [Run counters update more often] -> Persist them only when an event occurs and
  when normal run save points already happen.

## Migration Plan

1. Add additive schema columns for the new gate and backfill counters.
2. Update the OpenFront client and its tests for the two-slot gate and event
   reporting.
3. Update historical backfill discovery and run summaries to use the new gate
   and counters.
4. Update OpenSpec tasks and tests, then archive when complete.

## Open Questions

None.
