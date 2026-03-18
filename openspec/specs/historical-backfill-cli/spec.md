# historical-backfill-cli Specification

## Purpose
TBD - created by archiving change add-resumable-hybrid-backfill. Update Purpose after archive.
## Requirements
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

### Requirement: Replay cached historical payloads from an external CLI

The system SHALL provide an external CLI command that reprocesses cached
historical game payloads without issuing a new upstream crawl. Replay SHALL be
the explicit operator path for rebuilding derived data over already hydrated
history, and it SHALL report unreadable cached payloads as cache-integrity
failures instead of silently fetching new data.

#### Scenario: Operator replays cached history for a run

- **WHEN** an operator requests replay for a run whose hydrated payloads are
  already cached
- **THEN** the CLI rebuilds guild-relevant observations from cached payloads

#### Scenario: Replay encounters unreadable cache

- **WHEN** replay reaches a cached game payload that is unreadable
- **THEN** the CLI reports that game as a cache-integrity replay failure and
  does not silently perform a new crawl

#### Scenario: Operator requests replay with no cached payloads

- **WHEN** an operator requests replay for a historical range or run with no
  cached game payloads
- **THEN** the CLI fails instead of silently performing a new crawl

