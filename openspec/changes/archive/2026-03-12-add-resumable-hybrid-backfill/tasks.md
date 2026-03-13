## 1. Shared Backfill State

- [x] 1.1 Add shared Peewee models for backfill runs, discovery cursors,
  queued game ids, and cached turn-free game payloads
- [x] 1.2 Extend shared schema bootstrap and additive migrations for the new
  backfill and cache tables, including indexes for resume and lookup paths

## 2. Discovery Pipelines

- [x] 2.1 Implement clan-session team discovery that walks tracked guild clan
  tags across the requested range and enqueues unique team game ids
- [x] 2.2 Implement global FFA discovery that pages `/public/games` in
  API-compliant windows, keeps only `Free For All` rows, applies game-start
  date semantics, and persists cursor progress

## 3. Hydration And Replay

- [x] 3.1 Implement bounded-concurrency hydration workers that fetch
  `/public/game/:id?turns=false`, populate the raw cache, and track per-item
  success or retry state
- [x] 3.2 Implement cache-backed replay ingestion so cached payloads can be
  reprocessed into guild observations without another OpenFront crawl
- [x] 3.3 Batch aggregate refreshes for affected guilds instead of refreshing
  once per hydrated game

## 4. Worker Operations

- [x] 4.1 Update the worker runtime and backfill entrypoints to create runs,
  resume interrupted work, and emit progress summaries from persisted counters
- [x] 4.2 Add operator-facing status and completion reporting for discovered,
  cached, ingested, matched, failed, and remaining work, plus periodic progress
  logs during long runs

## 5. Dedicated CLI

- [x] 5.1 Add external CLI commands to start historical backfill runs with a
  requested date range
- [x] 5.2 Add external CLI commands to inspect run status and progress using
  persisted counters and cursor state
- [x] 5.3 Add external CLI commands to resume interrupted runs and replay
  cached payloads without a new crawl

## 6. Verification

- [x] 6.1 Add tests for team discovery deduplication, FFA filtering, cursor
  resume behavior, cache reuse, game-start boundary semantics, progress
  logging, CLI orchestration, and batched aggregate refreshes
- [x] 6.2 Run the relevant test suite and OpenSpec validation for the new
  historical backfill artifacts
