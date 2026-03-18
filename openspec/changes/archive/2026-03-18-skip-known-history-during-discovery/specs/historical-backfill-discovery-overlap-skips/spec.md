# Spec Delta: Historical Backfill Discovery Overlap Skips

## ADDED Requirements

### Requirement: Track known-history overlap excluded during discovery

The system SHALL classify known readable history during ordinary `start` and
`resume` discovery before creating run-local hydration work. When discovery
encounters a game that an earlier run already hydrated successfully and whose
cached payload is readable, the system SHALL exclude that game from the current
run queue and persist a dedicated discovery-skip counter for the run.

#### Scenario: Discovery excludes prior successful readable history

- **WHEN** ordinary discovery encounters a game id that an earlier run already
  completed and its cached payload is readable
- **THEN** the system does not create a new queued hydration row for the
  current run and increments the run's discovery overlap skip counter

#### Scenario: Discovery sees unreadable prior cache

- **WHEN** ordinary discovery encounters a game id from an earlier completed
  run but the cached payload cannot be read
- **THEN** the system does not classify that game as a discovery overlap skip
  and leaves it eligible for normal hydration work
