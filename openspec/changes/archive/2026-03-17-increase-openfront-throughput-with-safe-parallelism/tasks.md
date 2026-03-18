# Tasks: Increase OpenFront Throughput With Safe Parallelism

## 1. Shared gate and observability

- [x] 1.1 Extend the shared OpenFront gate state for two active leases and a
  0.5 second default success cooldown.
- [x] 1.2 Add rate-limit events to `OpenFrontClient` and backfill run counters
  for upstream cooldown observability.

## 2. Backfill concurrency

- [x] 2.1 Run team and FFA discovery concurrently in worker and CLI backfill
  execution paths.
- [x] 2.2 Add bounded local concurrency for team discovery so the second shared
  gate slot is usable during discovery.

## 3. Verification

- [x] 3.1 Update OpenFront tests for the two-slot gate, success cooldown floor,
  and strict `Retry-After` handling.
- [x] 3.2 Update backfill and CLI tests for throttling counters, warning logs,
  and concurrent discovery behavior.
