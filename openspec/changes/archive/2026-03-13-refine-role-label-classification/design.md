# Refine Role Label Classification Design

## Context

The current aggregate refresh flow sums donation and attack metrics across all
observed Team games, then calls a single heuristic to set `role_label`. That
works for pure one-game examples but breaks down for real players who mostly
attack and occasionally donate. On live `UN` data, players with the largest
Team samples collapse into `Hybrid` because the current heuristic treats any
observed donation as enough to disqualify `Frontliner`.

This change needs to keep role labels descriptive for the public website while
leaving Team score behavior unchanged. The current support bonus already avoids
penalizing low-donation players, so the problem is the label derivation, not
the score model.

## Goals / Non-Goals

**Goals:**

- Make persisted `role_label` values reflect a player's dominant observed Team
  play style instead of lifetime contamination from isolated support actions.
- Keep labels stable for players with meaningful Team samples and degrade to
  `Flexible` when the sample is too small or too mixed.
- Reuse the current aggregate refresh pipeline and existing stored
  `role_label` field so existing API and web surfaces keep working.
- Add regression coverage for mixed multi-game play histories.

**Non-Goals:**

- Redesign Team score, support bonus, or leaderboard sorting.
- Introduce a new public label taxonomy beyond the existing
  `Frontliner` / `Hybrid` / `Backliner` / `Flexible` set.
- Reconstruct territory ownership history or add new upstream API
  dependencies.
- Add new database tables or columns unless implementation proves the existing
  aggregate refresh path cannot support the calculation.

## Decisions

### 1. Compute dominant role from per-game role signals

Aggregate refresh will classify each Team game for a player using the existing
stored donation and attack metrics for that game, then roll those game-level
signals into a dominant role for the player.

This avoids the current lifetime contamination problem. A player who fronts in
most games but donates sometimes will keep a frontline label because the role
decision is based on the mix of Team games, not on whether any donation ever
occurred.

Alternatives considered:

- Tune the aggregate thresholds only: smaller change, but it still uses
  lifetime totals and overcorrects toward `Frontliner` in low-sample cases.
- Remove role labels entirely: honest but weaker for the website product.

### 2. Use a sample gate before assigning a stable role label

Players with fewer than five observed Team games will keep the existing
`Flexible` label. For players at or above that sample, the aggregate label
will be assigned from active role games (`Frontliner`, `Hybrid`,
`Backliner`) only:

- `Frontliner` when frontline games are at least `55%` of active role games
- `Backliner` when backline games are at least `55%` of active role games
- `Hybrid` otherwise

These thresholds are intentionally conservative. They preserve clearly dominant
styles while keeping mixed histories in `Hybrid`.

Alternatives considered:

- Pure plurality winner: too unstable for players whose role mix is close.
- No minimum sample: preserves the current low-sample noise problem.
- Higher dominance threshold: leaves too many established players as `Hybrid`.

### 3. Keep implementation inside aggregate refresh and reuse existing fields

The change will be implemented inside
`refresh_guild_player_aggregates()` and related helpers. No schema change is
required if the game-level role counts are derived while iterating
participants and used immediately to set the stored `role_label`.

This keeps the migration small and lets existing leaderboard and profile
responses continue exposing the same field.

Alternatives considered:

- Persist per-role counters in the aggregate table: useful for future UI, but
  unnecessary for the first correction.
- Recompute role labels on every request: simpler storage-wise, but contrary
  to the stored-aggregate model used elsewhere in the project.

## Risks / Trade-offs

- Thresholds may still need calibration for other guilds
  → Start with the `UN`-validated values and keep the helper structure simple
  so threshold adjustment is a follow-up, not a refactor.
- A single label still compresses mixed play styles
  → Keep `Hybrid` as the fallback for players without a clear dominant style
  and continue exposing raw support metrics on the site.
- Existing stored labels will remain stale until aggregates are refreshed
  → Include a refresh step in rollout and note that replay/backfill can rebuild
  labels from stored participant data.
- Per-game classification adds logic to aggregate refresh
  → Reuse existing participant iteration so the cost stays linear in already
  loaded Team observations.

## Migration Plan

1. Update the aggregate role-label helper to use per-game role signals and the
   sample-aware dominance rules.
2. Add focused ingestion tests for mostly-frontline, mostly-backline, mixed,
   and low-sample cases.
3. Refresh guild player aggregates for existing guilds so stored labels match
   the new rules.
4. If rollback is needed, restore the previous helper and refresh aggregates
   again from persisted participant data.

## Open Questions

- Whether gold-only donation behavior should stay aligned with the current
  donation-action heuristic or receive its own follow-up calibration once the
  main frontline bias is fixed.
