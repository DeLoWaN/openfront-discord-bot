# Design: Improve Historical Backfill Hydration Throughput

## Context

Historical backfill now avoids much of the old overlap waste, but real runs
still spend minutes hydrating the first hundred games even when the upstream
gate reports no rate limiting. The hot path is local: each hydrated game
re-reads backfill rows, serializes large payloads, upserts observed games,
deletes and recreates participants, and eventually triggers full guild
aggregate rebuilds. Those rebuilds reread the full participant history for each
affected guild, so the cost grows with dataset size and shows up as long pauses
late in hydration.

The user wants faster historical imports, and has explicitly chosen to allow
guild aggregates to stay stale until the run finishes. That lets this design
optimize for throughput instead of mid-run freshness. Later live runs also
showed that hidden bursty backfill settings can hit upstream `429` cooldowns,
and the operator now has an upstream-approved bypass key that should disable
client-side rate limiting entirely when configured correctly.

## Goals / Non-Goals

**Goals:**

- Remove aggregate rebuild work from the per-game hydration hot path.
- Preserve current backfill correctness, replay behavior, skip-known-history
  behavior, and durable progress reporting.
- Reduce redundant local writes and ORM round-trips during hydration and ingest
  so higher concurrency can translate into real throughput gains.
- Replace hidden bursty OpenFront defaults with explicit operator-visible
  tuning and safer smoothed defaults for ordinary backfill commands.
- Add a bounded calibration command that measures OpenFront fetch behavior
  without creating backfill runs or ingesting data.
- Support an explicit global OpenFront bypass mode that applies to bot, worker,
  website, and CLI requests when configured.

**Non-Goals:**

- Redesign the historical discovery model or replay workflow.
- Introduce approximate aggregates or partially updated derived views during a
  running backfill.
- Add broad adaptive throttling logic that continuously tunes itself at
  runtime.

## Decisions

### 1. Ordinary backfill refreshes guild aggregates after hydration completes

Hydration will accumulate the set of affected guild ids across the run and
refresh those aggregates only after queued game processing finishes. The hot
path will no longer call aggregate rebuilds every `refresh_batch_size`
successful games.

This gives the largest predictable speedup because aggregate rebuild cost grows
with historical data volume, while the user has already said mid-run freshness
is unnecessary.

Alternatives considered:

- Keep the current batched rebuilds: easiest to preserve progress visibility,
  but it leaves the main `O(history)` cost inside the hydration loop.
- Make aggregate refresh frequency configurable: useful later, but it adds an
  operator policy decision before proving the simpler end-only strategy.

### 2. Hydration keeps one correctness boundary for fetch/cache/ingest

Each hydrated game will still be fully fetched, cached, and ingested before it
is marked complete, but ingest will avoid unnecessary repeated work where the
stored result already represents the same payload. The change will target
redundant row fetches, repeated serialization, and avoidable delete/reinsert
cycles without changing the durable run model.

Alternatives considered:

- Aggressively split fetch from ingest into separate queues: higher potential
  throughput, but materially more moving parts and failure-state complexity.
- Leave ingest unchanged and only raise OpenFront parallelism: simpler, but it
  does not address the observed local bottleneck.

### 3. Progress logs remain operator-readable without promising fresh derived data

Run progress will continue to report hydration counts during the run and final
aggregate refresh totals after hydration drains. The design keeps the run
summary truthful: hydration can be complete before aggregate rebuild begins, but
the run itself is not marked complete until the final refresh phase finishes.

Alternatives considered:

- Introduce a new explicit persisted run phase: more precise, but unnecessary
  unless the simpler summary shape proves ambiguous in practice.

### 4. Backfill uses explicit smooth OpenFront defaults and a bounded probe tool

The backfill CLI will expose OpenFront tuning flags directly on `start` and
`resume` and will default them to a safe smoothed profile instead of keeping a
hidden aggressive burst profile in the launcher script. A dedicated
`probe-openfront` command will discover candidate public game ids, sample a
bounded subset, fetch `?turns=false`, and report latency, throughput, and
rate-limit metrics without creating backfill state or ingestion side effects.

This keeps backfill tuning visible to operators and provides a cheap way to
evaluate a candidate profile before running a multi-hour import.

Alternatives considered:

- Keep hidden launcher defaults and rely on log inspection later: rejected
  because it obscures the active profile and makes operator tuning guessy.
- Reuse ordinary `start` for calibration: rejected because it creates durable
  run state and mixes measurement with ingestion side effects.

### 5. Zero-second retry-after values must still cool down

The shared OpenFront client will apply a configured minimum cooldown whenever a
`429` arrives without a usable positive retry-after value. This prevents the
next request from immediately re-bursting into the same upstream minute window
just because the header omitted a helpful delay.

Alternatives considered:

- Retry immediately on `Retry-After: 0`: rejected because live runs showed this
  can produce repeated bursts of useless `429` responses.

### 6. Configured bypass mode disables client-side throttling globally

When the operator configures an OpenFront bypass header and value, every
OpenFront request path will send that header and an optional configured
`User-Agent`. In that mode the client will skip the shared gate and cooldown
logic entirely, because upstream is expected to exempt those requests from the
public rate limit. If OpenFront still returns `429`, the logs will warn the
operator that the bypass key may be wrong.

Alternatives considered:

- Keep the shared gate active even with a bypass key: rejected because the
  point of the key is to remove public throttling and avoid artificial local
  slowdowns.
- Limit bypass mode to historical backfill only: rejected because the key
  applies to every OpenFront request, not one caller.

## Risks / Trade-offs

- [Guild sites remain stale during long backfills] -> This is intentional for
  ordinary history imports, and the run is not marked complete until final
  aggregate refresh finishes.
- [A single final aggregate refresh could be a large tail step] -> It still
  removes the much more damaging repeated rebuilds from the hydration hot path.
- [Reducing redundant ingest writes may miss a corner case] -> Scope the change
  to equivalence-safe cases only and cover them with backfill/ingestion tests.
- [OpenFront gate changes can obscure local wins] -> Treat gate tuning as
  secondary and verify throughput improvements with no-rate-limit test fixtures
  where possible.
- [Bypass mode could hide a wrong operator configuration] -> Emit an explicit
  warning when a bypassed request still receives `429` so the operator can
  verify the bypass key and `User-Agent`.

## Migration Plan

1. Change ordinary hydration so it records affected guild ids and defers
   aggregate refresh until after queued game processing completes.
2. Reduce redundant hydration/ingest work inside the same run without changing
   persisted run semantics.
3. Expose explicit safe OpenFront tuning on the CLI and add the bounded probe
   command.
4. Teach the shared OpenFront client to enforce a minimum cooldown on zero
   retry-after `429` responses and to support the optional global bypass mode.
5. Update progress and completion tests to reflect end-of-run aggregate
   refresh and the new OpenFront behavior.
6. Verify that ordinary backfill still produces the same final aggregates and
   preserves failure/skip counters.

## Open Questions

None.
