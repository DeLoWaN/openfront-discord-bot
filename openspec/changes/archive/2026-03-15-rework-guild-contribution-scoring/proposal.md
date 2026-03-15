# Rework Guild Contribution Scoring Proposal

## Why

The first recalibration proved the `UN` leaderboard needed a different product
philosophy, not just different constants. The current Team score over-penalizes
losses, treats stacked guild games as something to discount, and normalizes the
result so aggressively that long-term guild anchors can fall far below small
sample players. At the same time, the `overall` leaderboard mixes two modes
that do not represent the same kind of guild contribution.

## What Changes

- **BREAKING** Remove the public `overall` leaderboard view and the related
  `overall_score` / profile section from the guild web experience and JSON
  contracts.
- Rework the Team score into a contribution-first cumulative model:
  - every guild-relevant Team game contributes positive base points
  - wins add extra points on top of participation
  - win rate is a light multiplier, not a destructive penalty
  - support remains a visible additive bonus
- Remove recency from the Team and FFA score calculations. Recent activity
  stays visible next to the score through separate metadata such as recent-game
  counts and last-played timestamps.
- Keep a dedicated `support` leaderboard and keep `support_bonus` visible on
  Team and Support views.
- Make Team lobby difficulty increase monotonically with team count without a
  hard cap at `10`, so a win in a `60`-team game is worth more than a win in a
  `10`-team game while still using damped growth.
- Remove punitive guild-stack scoring adjustments from the main Team score so
  players are rewarded for playing with the guild rather than penalized for it.
- Recalibrate the checked-in `UN` fixture expectations to reflect the new
  contribution-first ordering.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `guild-player-leaderboards`: remove `overall`, redefine Team score as
  contribution-first, and surface recency as activity context rather than as a
  score input
- `guild-stats-api`: remove `overall` payloads and add recent-activity
  metadata beside Team, FFA, and Support score fields
- `guild-public-sites`: remove `overall` navigation and render recent activity
  beside the score instead of baking it into score meaning
- `openfront-game-ingestion`: rebuild aggregates around positive cumulative
  Team and FFA scores with light win-rate modifiers, additive support bonus,
  and no recency or stack penalty in score

## Impact

- Affects the scorer in `src/services/openfront_ingestion.py`, the guild stats
  API, the public web leaderboard and player profiles, and the associated test
  suite.
- Changes the public contract by removing `overall` and by adding explicit
  recent-activity metadata for Team, FFA, and Support views.
- Requires a full aggregate recompute from existing raw observations, but not a
  full historical backfill when the raw data is already present.
- Revises the `UN` regression anchors so that high-participation guild players
  remain meaningfully high even with middling win rates.
