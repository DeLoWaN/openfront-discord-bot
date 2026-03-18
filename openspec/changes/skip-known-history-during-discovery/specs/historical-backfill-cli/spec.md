# Spec Delta: Historical Backfill CLI

## MODIFIED Requirements

### Requirement: Inspect historical backfill progress from an external CLI

The system SHALL provide an external CLI command that shows the persisted
status of a historical backfill run, including run identity, lifecycle state,
progress counters, and current cursor or window position. The displayed status
SHALL distinguish clean completion, completion with failures, overlap skipped
during discovery, overlap skipped during hydration compatibility checks,
explicit replay work, and cache-integrity failures.

#### Scenario: Operator inspects an active run

- **WHEN** an operator requests status for a running historical backfill
- **THEN** the CLI displays the latest persisted progress and cursor state

#### Scenario: Operator inspects a run with skipped history

- **WHEN** an operator requests status for a run that skipped already known
  history
- **THEN** the CLI shows discovery-phase overlap skips separately from replay
  work and failures

#### Scenario: Operator inspects an unknown run

- **WHEN** an operator requests status for a run id that does not exist
- **THEN** the CLI fails instead of reporting fabricated progress
