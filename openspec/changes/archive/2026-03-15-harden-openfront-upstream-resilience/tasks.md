# Harden OpenFront Upstream Resilience Tasks

## 1. OpenSpec and test scaffolding

- [x] 1.1 Finalize the proposal, design, and delta specs for upstream
  resilience, backfill behavior, results posting, and cache reuse
- [x] 1.2 Add failing tests for retry header parsing, shared request gating, and
  strict cooldown precedence in the OpenFront client
- [x] 1.3 Add failing tests for ordinary backfill skip-known behavior and
  shared-database disconnect resilience

## 2. Shared OpenFront coordination

- [x] 2.1 Add the shared OpenFront rate-limit model and schema migration for
  lease and cooldown state
- [x] 2.2 Implement the shared OpenFront gate, cooldown parsing, and strict
  retry behavior in the OpenFront client for all endpoints
- [x] 2.3 Remove endpoint-specific 429 bypass behavior and ensure results
  polling, sync, worker, and backfill callers all use the same gate

## 3. MariaDB resilience and backfill hardening

- [x] 3.1 Replace the shared bare MariaDB connection with reconnecting pooled
  bootstrap behavior and compatible test stubs
- [x] 3.2 Harden historical backfill failure recording so database issues do not
  mask the original OpenFront failure
- [x] 3.3 Keep ordinary start and resume flows from refetching or reparsing
  readable previously hydrated history

## 4. Documentation and verification

- [x] 4.1 Update README operational notes to describe the fixed conservative
  OpenFront policy and replay-only reparse behavior
- [x] 4.2 Mark the OpenSpec tasks complete as implementation lands
- [x] 4.3 Run targeted pytest coverage and Markdown lint for the changed files
