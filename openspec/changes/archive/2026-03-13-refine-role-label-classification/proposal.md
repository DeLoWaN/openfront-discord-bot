# Refine Role Label Classification Proposal

## Why

The current role-label heuristic is computed from lifetime aggregate donation
and attack totals. In practice, that makes `Frontliner` mean "attacked and
never donated at all", so high-sample team players drift into `Hybrid` after
even a few support actions. On the `UN` guild data, that leaves no
frontliners among the players with the largest team-game samples, which makes
the public labels misleading.

## What Changes

- Replace the aggregate "any donation means not frontliner" role heuristic with
  a sample-aware classification built from per-team-game role signals and the
  player's dominant role mix across games.
- Keep support bonus scoring unchanged so this change stays descriptive and
  does not re-rank players or penalize low-support styles.
- Reuse the existing `Flexible` label for players whose team-game sample is too
  small or too mixed to support a stable frontliner/backliner classification.
- Add regression coverage for mixed multi-game histories where a mostly
  frontline player performs occasional donations.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `openfront-game-ingestion`: Change guild aggregate role-label derivation from
  lifetime aggregate donation and attack totals to a sample-aware,
  game-mix-based classification.
- `guild-player-leaderboards`: Require player-facing role labels to remain
  descriptive for experienced frontliners who occasionally donate and to fall
  back to `Flexible` when the observed Team sample is too small or ambiguous.

## Impact

- Affects role-label computation in
  `src/services/openfront_ingestion.py` and the aggregate refresh path.
- Requires focused ingestion regression tests for mixed frontline/support play
  histories.
- Does not require new dependencies and is expected to avoid schema changes.
- Existing guild aggregates will need a refresh so stored `role_label` values
  match the new classification rules.
