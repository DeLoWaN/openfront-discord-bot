# historical-backfill-cli Specification

## Purpose
TBD - created by archiving change add-resumable-hybrid-backfill. Update Purpose after archive.
## Requirements
### Requirement: Start historical backfill runs from an external CLI

The system SHALL provide an external CLI command that starts a historical
backfill run by accepting the requested date range and creating a durable run
record for the hybrid discovery-and-hydration pipeline.

#### Scenario: Operator starts a new historical backfill

- **WHEN** an operator runs the start command with a valid historical date
  range
- **THEN** the CLI creates a backfill run and returns enough information to
  monitor or resume that run

#### Scenario: Operator provides an invalid date range

- **WHEN** an operator provides a backfill range whose end precedes its start
- **THEN** the CLI fails instead of creating a run

### Requirement: Inspect historical backfill progress from an external CLI

The system SHALL provide an external CLI command that shows the persisted
status of a historical backfill run, including run identity, lifecycle state,
progress counters, and current cursor or window position.

#### Scenario: Operator inspects an active run

- **WHEN** an operator requests status for a running historical backfill
- **THEN** the CLI displays the latest persisted progress and cursor state

#### Scenario: Operator inspects an unknown run

- **WHEN** an operator requests status for a run id that does not exist
- **THEN** the CLI fails instead of reporting fabricated progress

### Requirement: Resume interrupted historical backfill runs from an external CLI

The system SHALL provide an external CLI command that resumes an interrupted or
paused historical backfill run from its persisted state instead of restarting
from the beginning.

#### Scenario: Operator resumes an interrupted run

- **WHEN** an operator resumes a backfill run that has incomplete persisted
  work
- **THEN** the CLI continues that run from its saved queues and cursors

#### Scenario: Operator resumes a completed run

- **WHEN** an operator attempts to resume a historical backfill run that is
  already complete
- **THEN** the CLI reports that no resumable work remains

### Requirement: Replay cached historical payloads from an external CLI

The system SHALL provide an external CLI command that reprocesses cached
historical game payloads without issuing a new upstream crawl.

#### Scenario: Operator replays cached history for a run

- **WHEN** an operator requests replay for a run whose hydrated payloads are
  already cached
- **THEN** the CLI rebuilds guild-relevant observations from cached payloads

#### Scenario: Operator requests replay with no cached payloads

- **WHEN** an operator requests replay for a historical range or run with no
  cached game payloads
- **THEN** the CLI fails instead of silently performing a new crawl

