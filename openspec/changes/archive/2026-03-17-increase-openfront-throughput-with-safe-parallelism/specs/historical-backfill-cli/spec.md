# Spec Delta: Historical Backfill CLI

## MODIFIED Requirements

### Requirement: Inspect historical backfill progress from an external CLI

The system SHALL provide an external CLI command that shows the persisted
status of a historical backfill run, including run identity, lifecycle state,
progress counters, and current cursor or window position. The displayed status
SHALL distinguish clean completion, completion with failures, overlap skips,
explicit replay work, cache-integrity failures, and upstream cooldown
statistics observed during the run.

#### Scenario: Operator inspects an active run

- **WHEN** an operator requests status for a running historical backfill
- **THEN** the CLI displays the latest persisted progress, cursor state, and
  upstream cooldown counters

#### Scenario: Operator inspects a throttled run

- **WHEN** an operator requests status for a run that encountered upstream
  cooldowns
- **THEN** the CLI shows the count and duration of those cooldowns separately
  from replay work and failures

#### Scenario: Operator inspects an unknown run

- **WHEN** an operator requests status for a run id that does not exist
- **THEN** the CLI fails instead of reporting fabricated progress
