# openfront-game-ingestion Specification

## MODIFIED Requirements

### Requirement: Derive role-oriented metrics without territory reconstruction

The system SHALL derive support and frontline signals from stored donation and
attack metrics and SHALL NOT require reconstructing full territory ownership
history in order to score support behavior. For Team players, the system SHALL
derive role-oriented signals from each observed Team game and SHALL compute the
persisted aggregate `role_label` from the dominant role mix across observed
Team games rather than from lifetime donation presence alone. Occasional
support actions MUST NOT by themselves prevent a mostly-frontline player from
being labeled `Frontliner`. When a player's observed Team sample is too small
or too mixed to support a stable dominant role, the system SHALL persist the
existing fallback label `Flexible`.

#### Scenario: Territory history is unavailable

- **WHEN** the system computes support and role-oriented metrics for a Team
  player
- **THEN** the calculation succeeds from stored donation and attack data
  without replaying territory state

#### Scenario: Mostly-frontline player occasionally donates

- **WHEN** a Team player has a meaningful observed Team sample where most games
  show frontline behavior but some games include support actions
- **THEN** the persisted aggregate `role_label` remains `Frontliner`

#### Scenario: Team sample is too small or ambiguous

- **WHEN** a Team player's observed games do not provide a stable dominant role
- **THEN** the persisted aggregate `role_label` is `Flexible` or `Hybrid`
  instead of forcing a frontline or backline label from isolated events

#### Scenario: Team player has no donation events

- **WHEN** the system computes support and role-oriented metrics for a Team
  player with no donation events
- **THEN** the calculation still produces non-support metrics without requiring
  territory-derived substitutes
