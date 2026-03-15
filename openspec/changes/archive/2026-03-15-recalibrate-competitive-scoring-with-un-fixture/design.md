# Recalibrate Competitive Scoring With UN Fixture Design

## Context

The first competitive leaderboard rollout deliberately favored a simple
result-first model. That was enough to ship Team, FFA, Overall, and Support
views quickly, but the larger `UN` guild sample showed that the current score
shape is too coarse:

- support caps in the tens while Team score grows into the tens of thousands
- Team losses barely matter
- Team difficulty weighting is often inert because `num_teams` is missing in
  stored observations
- Overall does not use one shared scale for Team-only, FFA-only, and dual-mode
  players

The `UN` snapshot also gives the project a better regression source than the
small synthetic unit fixtures already in the repo. The new design uses that raw
guild-scoped sample both to calibrate the formula and to keep it from regressing.

## Goals

- Make Team score primarily about winning hard games, not raw win totals alone.
- Make `support_bonus` strong enough to matter for established Team players
  without turning Team into a support-only board.
- Keep support additive only. Frontliners should not lose points just for not
  donating.
- Put Team, FFA, and Overall on one comparable normalized scale.
- Explain the rules to players at two depths: a short summary and an exact
  computation view.
- Preserve a restorable raw `UN` test fixture so regressions can be validated
  without depending on a live MariaDB container.

## Non-Goals

- Rework role-label classification in this change.
- Introduce pair-specific support attribution.
- Require live MariaDB access for ordinary tests.

## Scoring Model

### 1. Shared helpers

- `days_since_game = max(0, (now_utc - game_time).total_seconds() / 86400)`
- `recency_weight = 0.4 + 0.6 * 0.5 ** (days_since_game / 45)`
- `team_confidence = min(1.0, team_game_count / 25.0)`
- `ffa_confidence = min(1.0, ffa_game_count / 25.0)`

The recency curve is intentionally smooth. Very recent games count more, but
older games still contribute instead of dropping into a few hard-coded bands.

### 2. Team difficulty inference

For Team games:

1. use `observed_games.num_teams` when present and greater than `1`
2. otherwise, if `player_teams` is numeric, treat it as the number of teams
3. otherwise, if `player_teams` is `Duos`, `Trios`, or `Quads`, infer
   `num_teams = total_player_count / 2|3|4`
4. otherwise, fall back to `1`

Then compute:

- `team_difficulty = sqrt(max(1, inferred_num_teams - 1))`

This matches the project’s stored data semantics: numeric `player_teams`
already means number of teams, while named team labels encode players per team.

### 3. Guild-stack adjustment

For each Team observation, count how many tracked guild participants appear in
the same Team game:

- `guild_stack = max(1, count_of_guild_participants_in_game)`

Result weighting uses that stack size asymmetrically:

- wins are discounted by `1 / sqrt(guild_stack)`
- losses are amplified by `sqrt(guild_stack)`

This keeps stacked clan wins from dominating the leaderboard unfairly while
still rewarding legitimate hard wins.

### 4. Team raw components

Per Team game:

- on win:
  - `team_result_raw += team_difficulty * recency_weight / sqrt(guild_stack)`
- on loss:
  - `team_result_raw += -0.4 * team_difficulty * recency_weight * sqrt(guild_stack)`

Support is donor-centric and remains additive:

- `support_share = donated_troops / (donated_troops + attack_troops)` when the
  denominator is positive
- `support_share = 1.0` when support activity exists but attack volume is zero
- `support_share = 0.0` otherwise

Per Team game:

- `support_volume = log1p(donated_troops_total / 1_000_000)`
- `support_volume += 0.5 * log1p(donated_gold_total / 1_000_000)`
- `support_volume += 0.5 * log1p(donation_action_count)`
- `team_support_raw += recency_weight * support_volume * (0.5 + 0.5 * support_share)`

Aggregate Team scoring:

- `team_result_index = rank_normalize(team_result_raw, 0..1000)` across players
  with Team games
- `support_bonus = rank_normalize(team_support_raw, 0..1000)` across players
  with positive support raw
- `team_score = 0.75 * team_result_index + 0.25 * support_bonus`

Players with no support raw keep `support_bonus = 0`.

### 5. FFA raw component

Per FFA game:

- `ffa_difficulty = sqrt(max(1, total_player_count - 1))`
- on win:
  - `ffa_result_raw += ffa_difficulty * recency_weight`
- on loss:
  - `ffa_result_raw += -0.25 * ffa_difficulty * recency_weight`

Aggregate FFA scoring:

- `ffa_score = rank_normalize(ffa_result_raw, 0..1000)` across players with FFA
  games

### 6. Overall score

Overall uses normalized Team and FFA outputs only.

- base mode weights are Team `0.7` and FFA `0.3`
- drop weights for modes with zero games, then renormalize over the remaining
  modes
- `blended_mode_score = weighted_average(team_score, ffa_score, mode_weights)`
- `overall_confidence = weighted_average(team_confidence, ffa_confidence, mode_weights)`
- `overall_score = blended_mode_score * overall_confidence`

This removes the old raw single-mode fallbacks and keeps every mode on the same
display scale.

## Explanation UX

The API will return two explanation layers for each view:

- `summary`: short plain-language explanation for casual readers
- `details`: structured exact-computation content for interested players

`details` will include:

- the formulas and constants used for the active view
- Team difficulty inference rules
- guild-stack adjustment rules
- normalization and confidence notes where relevant

The website will render:

- the summary inline near the leaderboard title
- the exact computation inside a `<details>` disclosure element titled
  `Exact computation`

## UN Fixture Strategy

The fixture will be guild-scoped raw source data, not precomputed aggregates.

Tracked fixture tables:

- `guilds`
- `guild_clan_tags`
- `observed_games`
- `game_participants`

The repo will store:

- `tests/fixtures/un_guild_fixture.sql.gz`: compressed SQL inserts that can be
  imported into SQLite-backed tests and restored into MariaDB
- `tests/fixtures/un_guild_snapshot.json`: a compact expected snapshot used by
  regression tests for key leaderboard anchors

The restore helper will:

- bootstrap an empty database with the shared schema
- load the compressed SQL rows
- leave aggregate recomputation to the tests or the operator’s follow-up
  commands

## Calibration Anchors

The initial calibration will be checked against the March 14, 2026 local `UN`
snapshot:

- `Temujin` should remain a top Team player after normalization
- support-heavy players such as `Tobberr`, `CENTCOM`, and `Support1` should
  keep stronger `support_bonus` values than clearly lower-support frontliners
- Team-only or FFA-only players should no longer dominate Overall purely
  because of raw score scale leakage

## Risks

- The checked-in SQL fixture will be materially larger than the current test
  data. Compression and narrow table scope keep this manageable.
- Rank normalization is easy to reason about but makes exact score values
  relative to the guild population. The exact-computation section should state
  this explicitly.
- The new Team loss penalty and guild-stack discount will move player order
  substantially. That is intended, but the UN regression should verify the
  headline outcomes before rollout.
