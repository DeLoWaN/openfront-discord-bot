# openfront-game-ingestion Specification

## MODIFIED Requirements

### Requirement: Maintain guild player aggregates from observations

The system SHALL maintain per-guild player aggregates derived from persisted
guild-relevant observations so leaderboard and public profile pages can be
served from stored guild stats rather than recalculating from raw observations
on each request. The aggregate model SHALL maintain separate normalized outputs
for Team, FFA, Overall, and Support views while rebuilding them from raw
per-game observations.

For Team aggregates, the system SHALL:

- infer Team difficulty from stored game fields
- discount wins when more guild participants appear in the same Team game
- apply a moderate loss penalty
- use per-game recency decay instead of a one-shot last-game bonus
- compute `support_bonus` as the normalized support component of Team score

For Overall aggregates, the system SHALL:

- combine only normalized Team and FFA outputs
- apply Team-first weighting
- damp the result by mode confidence
- avoid raw single-mode fallbacks

#### Scenario: Team observation has named team size only

- **WHEN** a Team observation stores `player_teams` as `Duos`, `Trios`, or
  `Quads` and does not store `num_teams`
- **THEN** the aggregate scorer infers Team difficulty from
  `total_player_count / 2|3|4`

#### Scenario: Team observation has numeric player_teams only

- **WHEN** a Team observation stores a numeric `player_teams` value and does
  not store `num_teams`
- **THEN** the aggregate scorer treats that numeric value as the number of
  teams

#### Scenario: Multiple guild participants share one Team game

- **WHEN** a player's Team result comes from a game with multiple tracked guild
  participants
- **THEN** that Team game's win contribution is discounted and its loss
  contribution is amplified relative to a solo guild entry

#### Scenario: Player has support history but poor frontline totals

- **WHEN** a player has positive donation history and little or no attack
  volume
- **THEN** the aggregate scorer can still award a positive `support_bonus`
  without requiring frontline metrics
