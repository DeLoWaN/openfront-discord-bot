# Design

## Context

The current guild site already exposes public Team, FFA, Support, badge, and
roster-adjacent data, but the first engagement version is still too expensive
on some requests and too opaque in some presentations. The main hotspots are
profile timeseries and home-style aggregate views, which still derive too much
history at read time. The main UX gaps are unlabeled score notes, weak recent
form semantics, sparse competitive pulse ranking cues, and recent-game cards
that hide too much match context.

The roster issue is not a missing-data problem. Historical observations
already contain valid `duo`, `trio`, and `quad` events, but the stored roster
read model can be empty until a refresh rebuilds it. Real data also shows
ambiguous same-tag cases where more tracked players with the same clan tag
appear in one game than the format permits. The design therefore keeps public
rankings trustworthy by only accepting exact rosters or high-confidence
filtered rosters.

## Decisions

### 1. Move heavy read paths onto additive read models

Add four stored views:

- `guild_player_daily_snapshots`
- `guild_daily_benchmarks`
- `guild_weekly_player_scores`
- `guild_recent_game_results`

These are rebuilt during aggregate refresh from `observed_games` and
`game_participants`. Public APIs then read only precomputed rows plus the
existing aggregates, instead of recalculating guild-wide history for every
profile and home request.

### 2. Keep roster rankings confidence-first

The public UX becomes `Rosters`, while backend compatibility keeps existing
`/api/combos/*` and `/combos/*` aliases. Canonical surfaces become
`/api/rosters/*` and `/rosters/*`.

Roster extraction accepts only:

- `exact`: tracked players with the same `effective_clan_tag` exactly match the
  inferred team size
- `no_spawn_filtered`: the same-tag group initially exceeds the inferred team
  size, but overflow players can be removed by a strong no-spawn heuristic

The no-spawn heuristic requires zero meaningful economy or action metrics:

- zero gold progression
- zero attacks and conquests
- zero donation/support activity
- zero meaningful unit or economy progression

If ambiguity remains after that filter, the game contributes nothing to public
roster rankings.

### 3. Make weekly competition first-class

Weekly competition uses the same formulas as all-time scoring, but scoped to a
calendar week:

- start: Monday `00:00:00` UTC
- end: Sunday `23:59:59` UTC

The home page gets a weekly module with current-week leaders and movers.
A dedicated `/weekly` page exposes:

- Team / FFA / Support tabs
- current-week top 10
- movers versus previous full week
- six-week trend matrix or sparkline-style view

Players also get weekly trend data on their profile.

### 4. Clarify every ambiguous UI element

Refinements:

- score notes render as `Wins / Games`
- badges show the full catalog, with locked badges visually muted and described
- progression chart uses dates on the x-axis and overlays player, guild median,
  and guild leader series
- recent-performance chart replaces the current binary win/loss bars with a
  dated performance view
- leaderboard tables become sortable with explicit column names and visible
  sort direction
- recent-games cards show date, result, team distribution, and winner context

### 5. Align replay links and map media with OpenFront `0.30`

Replay URLs now use the OpenFront worker-path algorithm:

- prod worker count: `20`
- route shape: `https://openfront.io/{workerPath}/game/{gameId}`

Map thumbnails are added only when a deterministic asset match exists in the
OpenFront map assets. Missing matches fall back to text-only cards.

## Risks and trade-offs

- Read-model rebuilds increase refresh cost, but substantially reduce public
  request cost and improve predictability.
- Confidence-first roster inference leaves some ambiguous games unranked, but
  avoids publishing misleading rosters.
- Weekly Team, FFA, and Support views add more UI surface, but this is the
  smallest complete scope that supports the intended return loop.

## Migration plan

1. Add additive read-model schema and models.
2. Add failing backend tests for weekly views, recent games, replay links, and
   roster inference.
3. Extend aggregate refresh to rebuild daily, weekly, recent-game, and roster
   read models from history.
4. Extend public APIs to read the new models.
5. Refine the SPA to consume the richer contracts.
6. Run a full guild aggregate rebuild after deployment.
