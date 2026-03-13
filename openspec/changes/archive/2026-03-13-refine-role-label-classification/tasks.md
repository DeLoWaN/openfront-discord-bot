# Refine Role Label Classification Tasks

## 1. Update aggregate role-label derivation

- [x] 1.1 Add or extract helpers that classify a player's role for a single
      observed Team game from stored donation and attack metrics.
- [x] 1.2 Update `refresh_guild_player_aggregates()` to accumulate Team
      role-mix counts and assign the persisted `role_label` from the
      sample-aware dominance rules while preserving the existing
      `Flexible` fallback.

## 2. Add regression coverage and rollout support

- [x] 2.1 Extend ingestion tests with mixed multi-game histories that cover a
      mostly-frontline player who donates occasionally, a strongly backline
      player, and a low-sample or ambiguous player.
- [x] 2.2 Verify the stored aggregate and leaderboard-facing payloads keep
      exposing the expected label values and document the need to refresh
      existing guild aggregates after deployment.
