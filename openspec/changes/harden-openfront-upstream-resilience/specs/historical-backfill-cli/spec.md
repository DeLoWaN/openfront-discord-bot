# Historical Backfill CLI Delta

## MODIFIED Requirements

### Requirement: Start historical backfill runs from an external CLI

The system SHALL provide an external CLI command that starts a historical
backfill run by accepting the requested date range and creating a durable run
record for the hybrid discovery-and-hydration pipeline. Ordinary `start`
behavior SHALL skip games that were already hydrated successfully in earlier
runs when their cached payloads remain readable, and it SHALL reserve all
reparsing of known history for explicit replay.

#### Scenario: Operator starts a new historical backfill

- **WHEN** an operator runs the start command with a valid historical date
  range
- **THEN** the CLI creates a backfill run and returns enough information to
  monitor or resume that run

#### Scenario: Start range overlaps known readable history

- **WHEN** an operator starts a backfill whose discovered games overlap prior
  successfully hydrated history with readable cached payloads
- **THEN** the CLI reports those games as skipped known history instead of
  replaying or reparsing them implicitly

#### Scenario: Operator provides an invalid date range

- **WHEN** an operator provides a backfill range whose end precedes its start
- **THEN** the CLI fails instead of creating a run

### Requirement: Resume interrupted historical backfill runs from an external CLI

The system SHALL provide an external CLI command that resumes an interrupted or
paused historical backfill run from its persisted state instead of restarting
from the beginning. Ordinary `resume` behavior SHALL skip overlap with games
that were already hydrated successfully in earlier runs when their cached
payloads remain readable, and it SHALL reserve full reprocessing for explicit
replay.

#### Scenario: Operator resumes an interrupted run

- **WHEN** an operator resumes a backfill run that has incomplete persisted
  work
- **THEN** the CLI continues that run from its saved queues and cursors

#### Scenario: Resume overlaps earlier successful readable history

- **WHEN** an operator resumes a run whose discovered games overlap prior
  successfully hydrated history from earlier runs and those cached payloads are
  readable
- **THEN** the CLI reports those games as skipped known history by default
  without reparsing them

#### Scenario: Operator resumes a completed run

- **WHEN** an operator attempts to resume a historical backfill run that is
  already complete and has no resumable work
- **THEN** the CLI reports that no resumable work remains
