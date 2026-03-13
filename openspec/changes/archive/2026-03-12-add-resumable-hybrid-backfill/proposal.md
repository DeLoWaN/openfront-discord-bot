# Add Resumable Hybrid Backfill Proposal

## Why

The current historical backfill path is not viable beyond short ranges because
it scans the global public games feed, fetches every matching game detail
serially, and provides no resumable state or progress visibility. We need a
backfill design that can cover months of OpenFront history, include both team
and Free For All matches, and avoid re-crawling the network when an operator
discovers missing downstream data.

## What Changes

- Add a durable historical backfill pipeline that splits discovery by source:
  clan sessions for team games and public games windows for Free For All
  discovery.
- Add persistent backfill run and cursor state so long backfills can pause,
  resume, and report progress instead of restarting from the beginning.
- Add bounded-concurrency game hydration so discovered game ids are fetched
  faster than the current one-request-at-a-time loop.
- Deduplicate discovered work by OpenFront game id so overlapping discovery
  streams or resume operations do not schedule the same game repeatedly.
- Add local storage for raw OpenFront game details without turns so fetched
  payloads can be reprocessed later without another API crawl.
- Add operator-visible progress logging and failure reporting for long-running
  historical backfills.
- Add a dedicated operator CLI to start, resume, inspect, and replay
  historical backfill runs.
- Define historical backfill date filtering in terms of game start time so
  range semantics match the upstream API behavior.

## Capabilities

### New Capabilities

- `historical-backfill-pipeline`: Discover, resume, and hydrate historical
  OpenFront game history using hybrid team and FFA sources with durable
  progress tracking.
- `historical-backfill-cli`: Provide an external CLI for operators to manage
  historical backfill runs and inspect progress.
- `openfront-game-cache`: Persist raw game detail payloads locally so
  historical game data can be reprocessed without refetching from OpenFront.

### Modified Capabilities

None.

## Impact

- Affects the worker runtime, external CLI surface, shared database schema,
  and OpenFront ingestion services.
- Introduces new persistence for backfill runs, cursors, queued game ids,
  and cached raw game payloads.
- Changes historical backfill operations from an in-memory serial loop to a
  resumable pipeline with bounded concurrency and progress reporting.
- Increases local storage usage in exchange for lower repeat API cost and
  safer recovery from partial backfills.
