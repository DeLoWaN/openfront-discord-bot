# Add Competitive Web Leaderboards Proposal

## Why

The current guild website only exposes one win-total leaderboard, which is too
shallow for a competitive player-facing product and does not reflect the
different skills involved in Team and FFA play. The site now needs
role-aware scoring, support metrics based on exact donation events, and a
frontend/backend split so leaderboard UX can evolve without rewriting the
scoring and ingestion stack.

## What Changes

- Replace the single guild win-total leaderboard with separate `Team`, `FFA`,
  `Overall`, and `Support` leaderboard views.
- Add competitive scoring models for `Team`, `FFA`, and `Overall`, with
  `Overall` derived from normalized Team and FFA mode scores and a
  confidence-weighted `70% Team` / `30% FFA` target mix.
- Add a capped support bonus for team scoring based on exact `donate_troops`
  and `donate_gold` events from OpenFront turn data.
- Merge observed players across tracked clan-tag username variants within a
  guild, such as `[NU] Temujin` and `[UN] Temujin`, when both prefixes belong
  to tracked guild clan tags.
- Strip tracked clan-tag prefixes from public player-name display on the guild
  website so guild-scoped views do not render redundant clan tags next to
  player names.
- Persist donation totals, donation counts, attack totals, and role-oriented
  aggregates so players can be sorted by both outcomes and play style.
- Expose leaderboard data, player profile data, and scoring explanation data
  through a guild-scoped JSON API that the frontend can consume without
  duplicating score logic.
- Update the public guild site to consume the backend API and present
  leaderboard tabs, sortable columns, and a concise explanation of how scores
  are evaluated.

## Capabilities

### New Capabilities

- `guild-stats-api`: Provide stable guild-scoped JSON endpoints for leaderboard
  views, player profile stats, and score explanation data so frontend changes
  do not require backend rewrites.

### Modified Capabilities

- `guild-player-leaderboards`: Replace the single win-total leaderboard with
  multiple competitive leaderboard views, sortable support metrics, and score
  explanations that players can understand.
- `openfront-game-ingestion`: Ingest exact team-game donation events from turn
  data and maintain the richer aggregates needed for team, FFA, overall, and
  support scoring.
- `openfront-game-cache`: Persist enough OpenFront game detail to replay
  donation-aware team scoring without refetching the upstream API.
- `guild-public-sites`: Serve the public site through a backend/frontend split
  that supports leaderboard tabs, richer stat views, and score explanation UI.

## Impact

- Affects the web app, ingestion/backfill pipeline, shared MariaDB schema, and
  guild leaderboard services.
- Adds or changes JSON API contracts that the website frontend will depend on.
- Increases OpenFront detail-fetch and cache requirements for relevant team
  games because donation scoring depends on `turns=true` payloads.
- Keeps the first frontend pass intentionally functional and replaceable, with
  visual design work deferred to a later change.
