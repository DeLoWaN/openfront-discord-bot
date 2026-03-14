# Recalibrate Competitive Scoring With UN Fixture Proposal

## Why

The current competitive scorer does not fit the larger `UN` guild sample well
enough to be credible. On the March 14, 2026 local MariaDB snapshot, players
such as `Temujin` can exceed `13,000` Team score while carrying only a
`35`-point support bonus, which makes support look nearly irrelevant at the top
of the board. The same sample also exposed two structural issues in the
existing implementation:

- Team difficulty weighting currently depends on `observed_games.num_teams`,
  but that field is usually null in the stored data, so Team score behaves much
  closer to raw win counting than the site explains.
- Overall mixes normalized dual-mode players with raw single-mode fallbacks, so
  specialists can dominate the leaderboard for scale reasons instead of
  competitive reasons.

The project also needs a durable regression dataset. The current `UN` sample
exists only in the local MariaDB container. If that container is destroyed, the
team loses the best calibration and regression input for the scorer unless the
data is checked into the repo in a restorable form.

## What Changes

- Rework Team, FFA, and Overall scoring into one normalized `0..1000` model
  calibrated against the local `UN` guild sample.
- Keep `support_bonus` visible as a first-class per-player metric on
  leaderboard rows and player profiles, but redefine it as a meaningful
  normalized secondary bonus inside Team score.
- Infer Team difficulty from stored game data by using `num_teams` when
  present, numeric `player_teams` as the number of teams, and `Duos` /
  `Trios` / `Quads` plus `total_player_count` when named team sizes are stored.
- Add a guild-stack adjustment so wins with many guildmates in the same Team
  game are discounted and losses in stacked guild games hurt more.
- Replace the current one-shot recency bonus with per-game recency decay.
- Remove raw single-mode Overall fallbacks and compute Overall only from
  normalized Team and FFA outputs with confidence damping.
- Add a checked-in SQL dump of the `UN` guild raw source data plus a restore
  workflow so regression tests can rebuild the scorer even after the current
  MariaDB container is gone.
- Expand the public scoring explanation into two layers:
  - a short user-facing summary
  - an expandable exact-computation section with formulas, constants, and
    inference rules

## Capabilities

### Modified Capabilities

- `guild-player-leaderboards`: recalibrate Team, FFA, Overall, and Support
  scoring while keeping support bonus visible in leaderboard views
- `guild-stats-api`: expose the recalibrated score fields plus summary and
  exact-computation explanation data
- `guild-public-sites`: render short scoring explanations inline and the exact
  computation in an expandable section
- `openfront-game-ingestion`: infer Team difficulty from stored game fields and
  rebuild normalized guild aggregates from raw observations

## Impact

- Affects the scorer in `src/services/openfront_ingestion.py`, the guild stats
  API, and the public web leaderboard rendering.
- Adds repo-tracked fixture data under `tests/fixtures/` together with a
  restore helper for MariaDB and test-time loading.
- Updates OpenSpec specs and tasks so the scoring overhaul and the fixture
  workflow are documented together.
