# Rework Guild Contribution Scoring Tasks

## 1. Revise the scoring contracts

- [x] 1.1 Update proposal, design, and spec deltas to remove `overall` and
  define Team / FFA / Support as the only public leaderboard views
- [x] 1.2 Define the new Team and FFA scoring formulas, recent-activity
  metadata, and support-bonus behavior in the capability specs

## 2. Rework aggregate computation

- [x] 2.1 Replace the Team score calculation with the positive cumulative
  contribution model: participation points, win bonus, light win-rate
  multiplier, and additive support bonus
- [x] 2.2 Remove `overall` aggregate computation and remove recency decay from
  Team and FFA scores while persisting recent-activity metadata separately
- [x] 2.3 Ensure Team difficulty weighting increases monotonically for large
  team counts, including games with far more than `10` teams

## 3. Update the API and public site

- [x] 3.1 Remove `overall` from leaderboard, profile, and scoring-explanation
  API responses
- [x] 3.2 Add recent-activity fields beside Team, FFA, and Support score data
- [x] 3.3 Update the public site navigation, tables, player profiles, and
  scoring copy to match the Team / FFA / Support-only model

## 4. Recalibrate and verify against UN

- [x] 4.1 Update unit tests for the new positive cumulative scoring rules and
  recent-activity metadata
- [x] 4.2 Refresh the `UN` regression expectations so high-participation guild
  players remain near the top while tiny high-win-rate samples do not dominate
- [x] 4.3 Run focused scorer/API/web tests, `pytest -q`, and `openspec validate`
