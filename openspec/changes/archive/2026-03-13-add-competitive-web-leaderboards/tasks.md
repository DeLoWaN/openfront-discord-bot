# Add Competitive Web Leaderboards Tasks

## 1. Schema and cache foundation

- [x] 1.1 Add additive shared-schema storage for Team, FFA, Overall, and
  Support aggregate fields plus any per-game support metric records needed for
  refreshes
- [x] 1.2 Extend hydration and cache handling so guild-relevant Team games can
  retain turn-level detail while other games continue to reuse turn-free detail
- [x] 1.3 Add replay or backfill support that rebuilds the richer competitive
  aggregates from cached game payloads

## 2. Ingestion and scoring services

- [x] 2.1 Derive donor-centric donation totals, donation action counts, and
  attack totals from Team game turn data during ingestion
- [x] 2.2 Compute stored Team, FFA, Overall, and Support leaderboard metrics,
  including the capped Team support bonus and role-oriented labels
- [x] 2.3 Add a backend scoring explanation service that returns concise
  player-facing explanations for Team, FFA, and Overall views
- [x] 2.4 Merge observed players across tracked clan-tag username variants
  within a guild and keep tracked clan tags out of public player-name display
- [x] 2.5 Rework Overall scoring so Team and FFA are normalized separately and
  weighted by sample confidence rather than mixed as a raw weighted sum

## 3. Guild stats API

- [x] 3.1 Add guild-scoped JSON endpoints for `team`, `ffa`, `overall`, and
  `support` leaderboard datasets
- [x] 3.2 Add guild player profile JSON endpoints that expose Team, FFA,
  Overall, and Support sections plus linked-versus-observed state
- [x] 3.3 Add a guild-scoped scoring explanation endpoint that the frontend can
  consume without embedding score logic

## 4. Public site integration

- [x] 4.1 Replace the current single leaderboard page flow with functional
  Team, FFA, Overall, and Support navigation backed by the new API
- [x] 4.2 Implement sortable leaderboard tables that use backend-provided score
  and metric values directly
- [x] 4.3 Update guild player profile pages and leaderboard help UI to show the
  new score sections and concise scoring explanations without treating this
  change as the final visual redesign
- [x] 4.4 Remove tracked clan-tag prefixes from public player-name rendering on
  leaderboard and profile pages
