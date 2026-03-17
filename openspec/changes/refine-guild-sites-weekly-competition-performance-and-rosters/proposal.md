# Proposal

## Why

The first engagement release proved the product direction, but it still has
three hard gaps in practice:

- some public pages remain slower than they should be because profile and home
  reads still derive too much history at request time
- several public surfaces are not self-explanatory yet, especially score notes,
  recent-form charts, leaderboard labels, and recent-game cards
- roster pages are currently underpopulated because the read model was not
  rebuilt from existing history, even though the underlying game data already
  contains valid `duo`, `trio`, and `quad` signals

The guild site also still lacks a weekly competition layer. That removes an
important repeat-visit loop: players can see all-time leaders, but they cannot
see who carried the current week, who climbed, or who dropped.

## What Changes

- Add derived read models for daily, weekly, and recent-game presentation so
  heavy player and home views stop recomputing guild-wide history on demand.
- Rename the public `Combos` UX to `Rosters`, keep compatibility aliases, and
  rebuild roster aggregates from existing history with a confidence-first
  policy for ambiguous same-tag games.
- Refine the home, leaderboard, player, and recent-games pages so labels,
  charts, and cards explain themselves without relying on guesswork.
- Add a weekly competition layer with current-week leaders, movers, multi-week
  trends, and a dedicated `/weekly` page.
- Update replay links for OpenFront `0.30` and add deterministic map
  thumbnails when an OpenFront map asset exists.

## Capabilities

### New Capabilities

- `guild-weekly-rankings`: guild-scoped weekly leaderboards, movers, and
  multi-week trend exposure for Team, FFA, and Support

### Modified Capabilities

- `guild-public-sites`: refine navigation and public presentation across home,
  leaderboard, player, roster, recent-games, and weekly pages
- `guild-stats-api`: extend public JSON contracts with weekly, richer profile,
  richer recent-game, and roster-compatible payloads
- `guild-player-leaderboards`: add sortable leaderboard columns, weekly views,
  richer player charts, and clearer score semantics
- `openfront-game-ingestion`: persist new derived read models and harden
  roster extraction from historical observations

## Impact

- Affects shared schema, aggregate refresh, guild stats APIs, and the public
  SPA under `src/services`, `src/data/shared`, and `src/apps/web`.
- Adds additive read-model tables for daily snapshots, daily benchmarks,
  weekly scores, and recent-game results.
- Requires a full aggregate rebuild after deployment so rosters, weekly views,
  recent games, and benchmarked player charts populate from history.
