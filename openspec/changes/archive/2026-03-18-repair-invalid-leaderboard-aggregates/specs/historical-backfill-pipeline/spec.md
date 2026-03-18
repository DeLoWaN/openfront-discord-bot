# Spec Delta: Historical Backfill Pipeline

## MODIFIED Requirements

### Requirement: Refresh guild aggregates from affected backfill results

The system SHALL refresh guild player aggregates only for guilds affected by
hydrated historical games, and it SHALL perform those refreshes in batches
instead of once per hydrated game.

Ordinary known-history skips SHALL also be allowed to contribute guild ids to
the affected aggregate refresh set when the system can derive those guilds from
already stored observations for the skipped game. This refresh behavior SHALL
NOT require refetching, replaying, or re-ingesting the skipped known-history
game.

#### Scenario: Skipped known-history game has stored guild observations

- **WHEN** ordinary backfill skips a known readable game and stored participant
  observations already identify one or more affected guilds for that game
- **THEN** those guilds are added to the batched aggregate refresh set without
  replaying the skipped game

#### Scenario: Skipped known-history game repairs stale aggregates

- **WHEN** an operator reruns an ordinary backfill over a date range whose
  known readable games already have stored observations
- **THEN** the run may refresh stale guild aggregates from those stored
  observations even though the underlying games remain skipped known history

### Requirement: Skip previously hydrated games during ordinary backfill runs

The system SHALL treat prior successful hydration from earlier runs as known
history during ordinary `start` and `resume` backfills. When newly discovered
work overlaps games that were already hydrated successfully in an earlier run
and the cached payload is readable, the ordinary backfill pipeline SHALL
classify those games as skipped known history before any new upstream fetch or
payload re-ingestion work is attempted. Explicit `replay` remains the only
ordinary operator action that reparses known history.

#### Scenario: Start run overlaps earlier successful readable history

- **WHEN** a new backfill run discovers a game that was already hydrated
  successfully in an earlier run and its cached payload is readable
- **THEN** ordinary backfill skips that game for fetch and re-ingest work while
  preserving any allowed aggregate refresh from already stored observations

#### Scenario: Resume run encounters earlier successful readable history

- **WHEN** a resumed backfill run encounters overlap with a game that was
  already hydrated successfully in an earlier run and its cached payload is
  readable
- **THEN** the resumed run skips that game by default without reparsing it and
  preserves replay as a separate operator action
