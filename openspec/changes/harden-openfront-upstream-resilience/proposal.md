# Harden OpenFront Upstream Resilience Proposal

## Why

OpenFront backfill and results traffic currently makes independent requests
with uneven retry behavior, which is aggressive enough to trigger Cloudflare
protection and can leave the bot or CLI failing at exactly the moment it
should be backing off. The shared MariaDB backend is also using a bare
long-lived connection, so transient disconnects can terminate a run while
masking the original upstream failure.

## What Changes

- Add a shared upstream-resilience capability that serializes all OpenFront API
  traffic through one MariaDB-backed global lease and cooldown state.
- Enforce a fixed conservative policy: one in-flight OpenFront request
  globally, a one-second minimum spacing after successful responses, and
  server-directed waits from `Retry-After`, `RateLimit-Reset`, or equivalent
  headers taking precedence over local retry timing.
- Apply the shared policy to every OpenFront call path, including player,
  sessions, clan sessions, public games, public game details, and public
  lobbies.
- Preserve ordinary `historical-backfill start` and `resume` behavior that
  skips already hydrated readable history without reparsing it, and keep
  `replay` as the only explicit reprocessing path.
- Harden the shared MariaDB layer with reconnecting pooled connections and
  best-effort failure recording so database disconnects do not mask the real
  OpenFront error.

## Capabilities

### New Capabilities

- `openfront-upstream-resilience`: coordinate all OpenFront requests through a
  shared cross-process gate and strict upstream cooldown handling

### Modified Capabilities

- `historical-backfill-cli`: clarify that ordinary start and resume flows skip
  previously hydrated readable history without reparsing it
- `historical-backfill-pipeline`: require shared upstream gating for discovery
  and hydration, and keep readable known history out of ordinary reprocessing
- `game-results-posting`: require results polling and fetches to respect the
  shared OpenFront cooldown behavior
- `openfront-game-cache`: require ordinary backfill flows to treat readable
  cached payloads from prior successful hydration as authoritative reusable
  history

## Impact

- Affects `src/core/openfront.py`, the historical backfill service and CLI, the
  results poller, and shared MariaDB bootstrap code.
- Adds a shared persistence model and migration for OpenFront rate-limit state.
- Introduces reconnecting pooled MariaDB behavior via Peewee `playhouse`
  helpers while preserving the existing no-peewee test fallback.
- Does not add new operator-facing config or CLI tuning knobs.
