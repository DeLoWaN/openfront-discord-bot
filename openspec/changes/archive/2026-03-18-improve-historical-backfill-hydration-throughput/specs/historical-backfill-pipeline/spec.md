# Historical Backfill Pipeline Spec Delta

## MODIFIED Requirements

### Requirement: Hydrate discovered games with bounded concurrency

The system SHALL fetch queued game details through a bounded worker pool while
routing every discovery and hydration request through the shared OpenFront
upstream gate unless an explicit configured OpenFront bypass is active.
Historical backfill SHALL support operator-selected OpenFront gate settings per
run, and its ordinary CLI defaults SHALL favor a smoothed safe profile over
bursty parallel fetches. Historical backfill hydration SHALL keep fetch,
cache, and ingest work in the hot path, but it SHALL defer guild aggregate
rebuild work until queued hydration completes so local rebuild cost does not
block ordinary per-game hydration progress.

#### Scenario: Queued game hydration succeeds during ordinary backfill

- **WHEN** a queued game detail fetch succeeds during an ordinary backfill run
- **THEN** the system caches and ingests that game, records any affected guild
  ids for later refresh, and continues hydration without running guild
  aggregate rebuilds inline for that game

#### Scenario: Queued game hydration is rate limited

- **WHEN** a queued game detail fetch receives an upstream cooldown signal
- **THEN** later discovery and hydration work waits on the shared OpenFront
  gate before issuing another upstream request

#### Scenario: Queued game hydration gets a zero-second retry-after

- **WHEN** a queued game detail fetch receives a `429` with an absent or
  zero-second retry-after value
- **THEN** the pipeline applies a configured minimum cooldown before retrying
  so the next request does not immediately re-burst into the upstream limit

#### Scenario: Queued game hydration runs with configured bypass mode

- **WHEN** OpenFront bypass header configuration is present
- **THEN** historical backfill sends the configured bypass header and optional
  `User-Agent` on every OpenFront request and does not wait on the shared
  client-side gate before issuing requests

#### Scenario: Queued game hydration fails transiently

- **WHEN** a queued game detail fetch encounters a transient upstream failure
- **THEN** the system records the failure and leaves the work item eligible for
  retry according to worker policy

### Requirement: Refresh guild aggregates from affected backfill results

The system SHALL refresh guild player aggregates only for guilds affected by
hydrated historical games. During ordinary `start` and `resume` backfills, the
system SHALL defer those aggregate refreshes until queued hydration work has
finished, and it SHALL refresh each affected guild at most once before the run
is marked complete.

#### Scenario: Hydrated run affects one guild

- **WHEN** an ordinary historical backfill hydrates one or more games that
  match a single guild
- **THEN** the system refreshes that guild's aggregates after hydration
  completes and before final run completion is reported

#### Scenario: Hydrated run affects multiple guilds

- **WHEN** an ordinary historical backfill hydrates games that match multiple
  guilds
- **THEN** the system refreshes each affected guild once after hydration
  completes instead of rebuilding aggregates repeatedly during the run

#### Scenario: Hydrated run matches no guilds

- **WHEN** an ordinary historical backfill finishes hydration without matching
  any guilds
- **THEN** the system completes the run without attempting aggregate refresh
