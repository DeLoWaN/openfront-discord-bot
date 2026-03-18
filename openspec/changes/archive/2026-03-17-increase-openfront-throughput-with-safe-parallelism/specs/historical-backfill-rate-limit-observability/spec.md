# Spec Delta: Historical Backfill Rate Limit Observability

## ADDED Requirements

### Requirement: Persist upstream cooldown counters on historical backfill runs

The system SHALL persist historical backfill run counters for real upstream
cooldown events encountered during ordinary `start` and `resume` execution.
These counters SHALL expose how often the run was rate-limited, how often the
cooldown came from explicit upstream retry headers, and the total and maximum
cooldown durations observed.

#### Scenario: Backfill run hits upstream throttling

- **WHEN** ordinary historical backfill receives an upstream cooldown signal
- **THEN** the run increments its persisted throttling counters and retains the
  cooldown duration for operator inspection

#### Scenario: Operator reviews backfill logs after throttling

- **WHEN** a backfill run encounters HTTP 429 with upstream cooldown details
- **THEN** the logs identify the run, cooldown duration, and cooldown source so
  operators can tune throughput later
