# Rework Guild Contribution Scoring Design

## Context

The previous scoring change optimized for competitive neatness: normalized
scores, explicit loss penalties, and stronger difficulty adjustments. The `UN`
guild sample showed that this is the wrong shape for the product goal. The
guild Team leaderboard is not meant to behave like a pure skill ladder. It is
meant to highlight players who participate heavily with the guild, while still
rewarding wins and visible support.

Two product truths now drive the design:

- `overall` is not meaningful enough to justify mixing Team and FFA
- recency must not destroy the guild's hall-of-fame history

## Goals / Non-Goals

**Goals:**

- Make Team score primarily cumulative and participation-first
- Keep wins materially better than losses without allowing losses to drive the
  score deeply negative
- Keep `support_bonus` visible and meaningful as an additive modifier
- Remove `overall` from the public contracts and pages
- Keep recent activity visible as context without baking it into score decay
- Let larger Team lobbies remain more valuable than smaller ones, including
  games with far more than `10` teams

**Non-Goals:**

- Building a seasonal or monthly leaderboard in this change
- Reworking role-label classification
- Changing the raw observation tables or requiring a fresh historical backfill
- Hiding all-time guild contribution in favor of activity-only ranking

## Decisions

### 1. Remove `overall` entirely

`overall` mixes two fundamentally different modes and adds conceptual
complexity without providing useful guild insight. Team and FFA will remain as
separate leaderboards, with Support retained as a dedicated view.

Rejected alternative:

- keep `overall` with different weights
  - rejected because the product issue is conceptual, not just numerical

### 2. Make Team score fully positive and cumulative

Losses will no longer subtract cumulative points. Instead, every Team game adds
participation value, wins add extra value, and win rate lightly adjusts the
total. This preserves the desired ordering where large participation stays
important and small high-efficiency samples do not dominate.

Proposed Team formula:

```text
difficulty_weight = 1 + 0.25 * log2(max(2, inferred_num_teams))
presence_points_per_game = 10 * difficulty_weight
win_bonus_points_per_win = 6 * difficulty_weight

presence_score = sum(presence_points_per_game over Team games)
result_score = sum(win_bonus_points_per_win over Team wins)
win_rate_multiplier = 0.85 + 0.30 * team_win_rate

core_team_score = (presence_score + result_score) * win_rate_multiplier
```

Key properties:

- every Team game contributes positive points
- a win gives more than a loss
- players with hundreds of guild games stay high even with average win rates
- large lobbies are worth more than small lobbies with no hard cap at `10`

Rejected alternatives:

- negative loss deltas
  - rejected because they collapse high-volume players too far down
- pure rank normalization
  - rejected because it makes displayed scores hard to interpret and too
    sensitive to guild population shape

### 3. Remove guild-stack penalties from Team score

The product goal is to value players who play with the guild. Punishing stacked
guild play contradicts that goal. The revised model will not discount the main
Team score based on guild stack size.

Rejected alternative:

- keep a mild stack discount
  - rejected for the first revision because the dominant product need is to
    reward guild participation, not normalize it away

### 4. Keep support as a visible additive bonus

Support remains separate and visible. It should help reorder players with
similar contribution levels, but it should not outweigh the core Team score.

Proposed support formula:

```text
support_raw =
  log1p(donated_troops_total / 100000)
  + 0.7 * log1p(donated_gold_total / 100000)
  + 0.5 * log1p(donation_action_count)

support_share =
  donated_troops_total / (donated_troops_total + attack_troops_total)

support_scaled = 25 * support_raw * (0.6 + 0.4 * support_share)
support_bonus = min(core_team_score * 0.20, support_scaled)

team_score = core_team_score + support_bonus
```

Rejected alternative:

- support as a separate rank-normalized scale
  - rejected because it disconnects the bonus from the main Team score and
    makes the value harder to reason about

### 5. Remove recency from score and surface it as metadata

The main Team and FFA scores will not decay over time. Instead, recent activity
will be stored and displayed beside the score through fields such as:

- `last_game_at`
- `last_team_game_at`
- `last_ffa_game_at`
- `team_recent_game_count_30d`
- `ffa_recent_game_count_30d`

This preserves hall-of-fame value while still letting the UI show who is
currently active.

Rejected alternatives:

- strong recency decay in score
  - rejected because it causes former guild pillars to disappear from the
    leaderboard
- no recency metadata at all
  - rejected because visitors still need current-activity context

### 6. Keep FFA separate and simpler

FFA will remain a separate cumulative score with the same broad philosophy:
positive game participation, extra reward for wins, no support bonus, and no
`overall` blending.

Proposed FFA formula:

```text
ffa_difficulty_weight = 1 + 0.20 * log2(max(2, total_player_count))
ffa_presence_points = 10 * ffa_difficulty_weight
ffa_win_bonus_points = 6 * ffa_difficulty_weight

ffa_core_score =
  (sum(ffa_presence_points over FFA games)
   + sum(ffa_win_bonus_points over FFA wins))
  * (0.85 + 0.30 * ffa_win_rate)
```

## Risks / Trade-offs

- [Risk] Volume dominates too much and locks in all-time veterans
  → Mitigation: show recent-activity metadata prominently and leave room for a
  future seasonal leaderboard if needed
- [Risk] Large lobby weighting may still overvalue a few rare games
  → Mitigation: use damped logarithmic growth rather than a steep uncapped
  multiplier
- [Risk] Removing `overall` is a breaking contract for existing consumers
  → Mitigation: update the site, API docs, tests, and explanation copy in the
  same change
- [Risk] Support may again feel too weak if the scaling is too conservative
  → Mitigation: calibrate against the `UN` sample and assert expected support
  anchors in regression tests

## Migration Plan

1. Update the specs and API/site contracts to remove `overall`
2. Rework aggregate recomputation to use the new cumulative Team and FFA
   formulas plus recent-activity metadata
3. Recompute guild aggregates from the existing raw observations
4. Refresh the `UN` regression snapshot and verify the expected ordering
5. Roll back by restoring the previous aggregate computation if the new
   ordering still fails the `UN` anchors

## Open Questions

- Whether the public leaderboard should show both `Games 30d` and `Last Game`,
  or only one of them, can be finalized during UI implementation
- Whether FFA should use the exact same participation-first constants as Team,
  or a slightly more result-oriented tuning, can be calibrated during
  implementation without changing the core philosophy
