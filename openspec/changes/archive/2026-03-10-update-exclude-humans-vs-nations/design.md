## Context
Humans vs Nations games should be excluded from win analysis and results posting. The current code uses session payloads for win counting and game config payloads for results.

## Goals / Non-Goals
- Goals:
  - Exclude Humans vs Nations from session-based win counting and results posting.
  - Avoid extra OpenFront API calls when `playerTeams` is missing.
  - Keep `total` mode unchanged due to aggregate stats limitations.
- Non-Goals:
  - Changing database schema or command behavior.
  - Reworking results embed formatting beyond the exclusion.

## Decisions
- Identify Humans vs Nations via a normalized `playerTeams` string match (case/whitespace-insensitive).
- Skip results posting when `playerTeams` matches Humans vs Nations.
- Skip session-based wins when `playerTeams` matches Humans vs Nations.
- Treat missing `playerTeams` as eligible and do not fetch `/public/game/:id` for verification.

## Risks / Trade-offs
- Some Humans vs Nations sessions may be included if `playerTeams` is missing.
- `total` mode remains unfiltered by design.

## Migration Plan
- No schema changes; deploy logic changes and new tests.

## Open Questions
- None.
