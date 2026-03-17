# Proposal

## Why

The current guild website exposes the data as a thin leaderboard and text
profile experience, which is not strong enough to drive repeat visits,
comparison, or long-term collection behavior. At the same time, the Team score
still treats lobby difficulty too narrowly: it values number of teams, but it
does not reward players extra when they play in smaller-team formats or when
their team contains fewer tracked guild teammates and therefore less organized
guild support.

## What Changes

- Replace the minimal public guild site with an engagement-focused web
  experience built around a richer home page, combo rankings, recent wins, and
  player badges.
- Add public combo views for confirmed and pending `Duos`, `Trios`, and
  `Quads`, ranked by raw win rate with a minimum confirmed sample threshold.
- Add a public recent-wins feed that shows the latest guild `Team` and `FFA`
  wins with replay-oriented match context.
- Extend public player profiles with badge, partner, and timeseries data.
- Keep Team score cumulative and contribution-first, but refine its difficulty
  weighting so harder Team contexts score higher when:
  - the lobby has more teams
  - the team format has fewer players per team
  - the player's team contains fewer tracked guild-tag teammates
- Keep leaderboard and profile scoring explanations aligned with the revised
  Team difficulty model.
- Materialize combo and badge read models while continuing to build recent wins
  and timeseries views directly from observed game data.
- Add an integrated SPA frontend in the repo for the public guild site while
  preserving the existing public route surface.

## Capabilities

### New Capabilities

- `guild-combo-rankings`: public confirmed and pending duo/trio/quad rankings,
  combo detail views, and combo profile surfaces
- `guild-player-badges`: badge catalog, badge award exposure, and recent badge
  presentation for guild players

### Modified Capabilities

- `guild-public-sites`: replace the minimal web presentation with the richer
  engagement home, combo navigation, recent wins page, and richer player pages
- `guild-stats-api`: extend the public JSON contracts with home, combo, recent
  wins, badge, and player-timeseries data
- `guild-player-leaderboards`: extend player-facing leaderboard/profile
  behavior with combo and badge surfaces while keeping Team/FFA/Support views
- `openfront-game-ingestion`: refine Team difficulty to account for team count,
  smaller players-per-team formats, and lower tracked guild presence on a team

## Impact

- Affects the web app, service-layer read models, aggregate recomputation, and
  scoring logic below `src/apps/web` and `src/services`.
- Adds a frontend toolchain and runtime surface for the public guild site.
- Changes public JSON contracts by adding home, combo, recent wins, badge, and
  timeseries endpoints plus richer player payloads.
- Requires additive schema work for combo aggregates, combo members, and player
  badge awards, plus aggregate recomputes from existing observed data.
