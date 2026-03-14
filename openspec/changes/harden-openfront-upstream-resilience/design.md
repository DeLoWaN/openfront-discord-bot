# Harden OpenFront Upstream Resilience Design

## Context

The `website` branch now depends on OpenFront for multiple independent flows:
website-linked player lookups, Discord sync, results polling, worker helpers,
and the `historical-backfill` CLI. Today those call sites share one client
module but not one global request policy. Discovery loops issue the next window
immediately, `fetch_game()` and lobby polling bypass 429 retries, and
`Retry-After` parsing only handles numeric values. In practice this allows one
process to back off while another keeps calling the API, which is the opposite
of the conservative posture needed for Cloudflare-protected public endpoints.

At the same time, the shared MariaDB layer uses a bare `MySQLDatabase`
connection behind `DatabaseProxy`. Long-running tasks such as historical
backfill can outlive that connection and then fail while trying to record the
real upstream error, leaving operators with a database stack trace instead of
the OpenFront rate-limit failure that actually caused the retry path.

## Goals / Non-Goals

**Goals:**

- Serialize all OpenFront requests across bot, website, worker, and CLI
  processes through one shared gate.
- Strictly honor server cooldown signals before issuing more OpenFront traffic.
- Keep ordinary `historical-backfill start` and `resume` flows from reparsing
  already hydrated readable history.
- Make shared MariaDB resilient enough that transient disconnects do not abort
  recovery logic or hide the original failure.

**Non-Goals:**

- Add operator-tunable rate-limit knobs or a new config surface.
- Rework unrelated bot scheduling or Discord-side rate-limit behavior.
- Change replay semantics beyond preserving it as the explicit reparse path.

## Decisions

### 1. Use MariaDB as the source of truth for the OpenFront gate

Add a singleton shared model, `OpenFrontRateLimitState`, with lease ownership,
lease expiry, cooldown deadline, and cooldown reason. Every OpenFront request
must acquire the lease, wait out any persisted cooldown, perform exactly one
HTTP request, then persist the next cooldown before releasing the lease.

This keeps the protection global across separate bot, website, and CLI
processes, which a per-process `asyncio.Lock` cannot do.

Alternatives considered:

- Per-process locks only: rejected because separate processes would still race
  each other into Cloudflare limits.
- External Redis or another coordinator: rejected because MariaDB is already
  required for the website/shared backend flows and keeps the design smaller.

### 2. Fix the policy instead of exposing tuning

The new gate uses a fixed conservative posture: one global in-flight request
and a one-second minimum spacing after success. Upstream-provided cooldowns
override the success spacing and extend the pause when present.

This removes the operator footgun that caused the backfill run to burst
requests in the first place.

Alternatives considered:

- Add CLI or YAML knobs for rate and concurrency: rejected because the request
  is to stop accidental Cloudflare bans, not to create more tuning surfaces.
- Keep bounded hydration concurrency and let the gate absorb it: accepted only
  as an implementation detail. Worker pools may remain, but the shared gate is
  the real upstream bound.

### 3. Treat readable successful cache as authoritative for ordinary history

Ordinary `start` and `resume` flows should classify prior successful readable
cache as known history before any fetch or ingestion work is attempted. If the
payload is readable, ordinary backfill skips it outright. If the cached payload
is unreadable, ordinary backfill may still repair it by refetching, while
explicit `replay` remains cache-only.

This keeps replay as the only deliberate reparse mechanism while preserving the
existing repair path for broken cache.

Alternatives considered:

- Always re-ingest cached payloads on start/resume: rejected because it defeats
  the skip-known contract and does unnecessary work.
- Never repair unreadable cache in ordinary runs: rejected because it would
  turn recoverable corruption into manual-only cleanup.

### 4. Replace the shared bare connection with reconnecting pooled MariaDB

Wrap the shared MariaDB bootstrap in Peewee `playhouse` reconnect and pooling
support so long-lived processes transparently recover from stale or dropped
connections. Failure-recording paths in historical backfill should log the
original OpenFront exception first and then persist failure state best-effort,
without performing extra reads that can fail before the write even begins.

Alternatives considered:

- Keep the single bare connection and add local reconnect calls everywhere:
  rejected because it scatters resilience logic across call sites.
- Handle disconnects only in the CLI: rejected because the bot and website
  share the same database bootstrap risk.

## Risks / Trade-offs

- [Global serialization slows high-volume ingestion] -> Accept the slower
  throughput to prioritize upstream safety and predictable operator behavior.
- [MariaDB becomes part of the OpenFront request path] -> Keep the gate state
  small and resilient, and fall back to conservative local waits only when the
  shared backend is unavailable in environments that do not configure MariaDB.
- [Lease state can become stale after crashes] -> Use short lease expiries and
  lease refresh/replacement rules so a dead process cannot block traffic
  indefinitely.
- [Changing shared DB bootstrap touches multiple surfaces] -> Cover the
  reconnect behavior with dedicated tests and keep the public API unchanged.

## Migration Plan

1. Add the shared rate-limit model to the shared schema and bootstrap
   migrations.
2. Ship the new OpenFront client coordination logic together with the new
   shared model so callers do not observe a partial rollout.
3. Update Markdown specs and README operational notes to describe the fixed
   conservative policy and replay-only reparse path.
4. Rollback by removing callers from the new gate only if the shared schema and
   reconnecting bootstrap prove incompatible; no user data migration is
   required beyond the added coordination row.

## Open Questions

None.
