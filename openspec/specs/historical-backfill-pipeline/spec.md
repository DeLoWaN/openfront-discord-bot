# historical-backfill-pipeline Specification

## Purpose

TBD - created by archiving change add-resumable-hybrid-backfill. Update
Purpose after archive.

## Requirements

### Requirement: Discover historical team games by tracked clan sessions

The system SHALL discover historical public team games for guild backfill by
querying clan sessions for each tracked guild clan tag within the requested
backfill range. The system SHALL extract unique `gameId` values from those
session rows and enqueue them for hydration without relying on a global team
game scan.

#### Scenario: Shared game id appears in multiple clan session streams

- **WHEN** session rows from two or more tracked clan tags reference the same
  `gameId`
- **THEN** the system enqueues one hydration work item for that game id

#### Scenario: Backfill range spans multiple clan-session windows

- **WHEN** a requested backfill range exceeds one discovery window
- **THEN** the system continues clan-session discovery across successive
  windows until the full range has been covered

### Requirement: Apply historical date filters by game start time

The system SHALL interpret historical backfill `start` and `end` boundaries
using game start time, not game end time. Clan-session discovery SHALL use each
row's `gameStart`, and public-games discovery SHALL use each row's `start`
timestamp.

#### Scenario: Game starts inside range and ends after range

- **WHEN** a game's start timestamp falls inside the requested backfill range
- **THEN** the system treats that game as in range even if the game ends later

#### Scenario: Game starts before range and ends inside range

- **WHEN** a game's start timestamp falls before the requested backfill range
- **THEN** the system treats that game as out of range even if the game ends
  within the requested window

### Requirement: Discover historical FFA games by public games windows

The system SHALL discover historical Free For All games by querying
`/public/games` in API-compliant time windows, paging through the full list,
and selecting only rows whose list metadata reports `mode` as `Free For All`.
The system SHALL enqueue only those FFA game ids for hydration.

#### Scenario: Team game appears in public games discovery

- **WHEN** a public games list row reports `mode` as `Team`
- **THEN** the system does not enqueue that row for the FFA hydration stream

#### Scenario: Free For All game appears in public games discovery

- **WHEN** a public games list row reports `mode` as `Free For All`
- **THEN** the system enqueues that game id for hydration

### Requirement: Persist resumable backfill progress

The system SHALL persist backfill runs and discovery cursor state so an
interrupted historical backfill can resume from the last saved position instead
of restarting from the beginning of the requested range. The persisted run
state SHALL distinguish clean completion from completion with unresolved
failures, and it SHALL expose operator-readable counters that separate ordinary
overlap skips, explicit replay work, cache-integrity failures, and other
hydration failures.

#### Scenario: Worker stops mid-backfill

- **WHEN** a historical backfill run stops after some discovery windows or
  pages have completed
- **THEN** a resumed run continues from the saved cursor state and preserves
  previously queued work

#### Scenario: Operator requests backfill status

- **WHEN** an operator inspects a historical backfill run
- **THEN** the system reports persisted lifecycle state, progress counters, and
  cursor positions for that run

#### Scenario: Run completes with unresolved failures

- **WHEN** a historical backfill finishes its pass with one or more unresolved
  cache-integrity or hydration failures
- **THEN** the persisted run outcome distinguishes that result from a clean
  fully successful completion

### Requirement: Deduplicate queued work by game id

The system SHALL deduplicate discovered historical work by OpenFront game id so
the same game is not scheduled multiple times across overlapping discovery
windows, multiple clan tags, or resumed runs.

#### Scenario: Same game discovered twice in one run

- **WHEN** two discovery steps emit the same OpenFront game id
- **THEN** the system retains one queued hydration work item for that game id

#### Scenario: Resumed run encounters an already queued game

- **WHEN** a resumed backfill step rediscovers a game id that is already
  queued or completed for that run
- **THEN** the system does not create a duplicate hydration work item

### Requirement: Hydrate discovered games with bounded concurrency

The system SHALL fetch queued game details through a bounded worker pool while
routing every discovery and hydration request through the shared OpenFront
upstream gate. Historical backfill SHALL support operator-selected OpenFront
gate settings per run, and its ordinary CLI defaults SHALL favor a smoothed
safe profile over bursty parallel fetches. The pipeline SHALL track per-item
success and failure state without aborting the entire run on one transient
error.

#### Scenario: Team and FFA discovery overlap in time

- **WHEN** ordinary historical backfill starts discovery for team and FFA
  sources
- **THEN** the pipeline may advance those discovery streams concurrently while
  still respecting the shared OpenFront gate

#### Scenario: Queued game hydration succeeds

- **WHEN** a queued game detail fetch succeeds
- **THEN** the system marks the work item complete and makes the payload
  available for ingestion

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
hydrated historical games, and it SHALL perform those refreshes in batches
instead of once per hydrated game.

Ordinary known-history skips SHALL also be allowed to contribute guild ids to
the affected aggregate refresh set when the system can derive those guilds from
already stored observations for the skipped game. This refresh behavior SHALL
NOT require refetching, replaying, or re-ingesting the skipped known-history
game.

#### Scenario: Hydrated game affects one guild

- **WHEN** ingestion of a hydrated historical game matches one guild
- **THEN** that guild is added to the affected refresh set for batched
  aggregate refresh

#### Scenario: Hydrated game affects multiple guilds

- **WHEN** ingestion of a hydrated historical game matches more than one guild
- **THEN** each matched guild is added to the affected refresh set for batched
  aggregate refresh

#### Scenario: Skipped known-history game has stored guild observations

- **WHEN** ordinary backfill skips a known readable game and stored participant
  observations already identify one or more affected guilds for that game
- **THEN** those guilds are added to the batched aggregate refresh set without
  replaying the skipped game

#### Scenario: Skipped known-history game repairs stale aggregates

- **WHEN** an operator reruns an ordinary backfill over a date range whose
  known readable games already have stored observations
- **THEN** the run may refresh stale guild aggregates from those stored
  observations even though the underlying games remain skipped known history

### Requirement: Emit progress logs for long historical runs

The system SHALL emit operator-readable progress logs for historical backfill
runs, including run start, periodic progress, cursor advancement, overlap skip
counts, replay counts, cache-integrity failures, retry or failure events, and
completion summaries.

#### Scenario: Historical run is in progress

- **WHEN** a long-running backfill continues across multiple windows or batches
- **THEN** the worker logs progress counters and the current cursor or window

#### Scenario: Historical run completes cleanly

- **WHEN** a historical backfill finishes without unresolved failures
- **THEN** the worker logs a final outcome that is clearly distinguishable from
  a completion with failures

#### Scenario: Historical run completes with failures

- **WHEN** a historical backfill finishes with unresolved cache-integrity or
  hydration failures
- **THEN** the worker logs the final run outcome and summary counters without
  implying a clean success

### Requirement: Skip previously hydrated games during ordinary backfill runs

The system SHALL treat prior successful hydration from earlier runs as known
history during ordinary `start` and `resume` backfills. When newly discovered
work overlaps games that were already hydrated successfully in an earlier run
and the cached payload is readable, the ordinary backfill pipeline SHALL
classify those games as skipped known history during discovery before new
hydration work is queued, fetched, or re-ingested. Explicit `replay` remains
the only ordinary operator action that reparses known history. Ordinary
hydration SHALL retain a compatibility guard that can still classify queued
rows as skipped known history before any new upstream fetch or payload
re-ingestion work is attempted.

#### Scenario: Start run overlaps earlier successful readable history

- **WHEN** a new backfill run discovers a game that was already hydrated
  successfully in an earlier run and its cached payload is readable
- **THEN** ordinary discovery excludes that game from the queued hydration set
  and records it as known history instead of refetching or re-ingesting it

#### Scenario: Resume run encounters earlier successful readable history

- **WHEN** a resumed backfill run encounters overlap with a game that was
  already hydrated successfully in an earlier run and its cached payload is
  readable
- **THEN** ordinary discovery skips that game by default before queuing new
  hydration work and preserves replay as a separate operator action

#### Scenario: Explicit replay reprocesses known history

- **WHEN** an operator explicitly requests replay for a run that references
  already hydrated games
- **THEN** the system reprocesses those games from cache instead of classifying
  them as ordinary overlap skips

### Requirement: Repair or report unreadable cached payloads by workflow

The system SHALL treat unreadable cached payloads as cache-integrity problems,
not as overlap duplicates. During ordinary `start` and `resume` flows, the
pipeline MAY repair unreadable cached payloads by invalidating that cache and
refetching upstream detail. During explicit `replay`, the pipeline SHALL
report unreadable cached payloads as replay failures without silently crawling
upstream data.

#### Scenario: Ordinary backfill encounters unreadable cached payload

- **WHEN** `start` or `resume` needs to process a queued game whose cached
  payload is unreadable
- **THEN** the system treats that cache state as repairable and may refetch the
  upstream game detail instead of classifying the game as duplicate history

#### Scenario: Replay encounters unreadable cached payload

- **WHEN** explicit replay attempts to read a cached payload that is unreadable
- **THEN** the system reports a cache-integrity replay failure and does not
  silently perform a new crawl
