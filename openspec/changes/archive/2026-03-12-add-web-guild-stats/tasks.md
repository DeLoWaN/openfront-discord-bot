# Add Web Guild Stats Tasks

## 1. Platform foundation

- [x] 1.1 Restructure the project around shared web, worker, bot, and data
  modules without breaking the current bot entrypoint
- [x] 1.2 Add MariaDB configuration and connection plumbing alongside the
  existing configuration loading
- [x] 1.3 Define the new shared Peewee models for guilds, guild clan tags, site
  users, players, aliases, player links, games, participants, and guild player
  aggregates
- [x] 1.4 Add schema bootstrap and migration support for the new MariaDB-backed
  multi-tenant data model

## 2. Guild site provisioning and routing

- [x] 2.1 Add manual guild provisioning support with subdomain, slug, active
  state, and optional Discord linkage
- [x] 2.2 Implement subdomain-based guild resolution and not-found handling for
  unknown or inactive guild sites
- [x] 2.3 Build the public guild home page with guild identity, tracked clan
  tags, and navigation to leaderboard and player pages

## 3. OpenFront ingestion and aggregation

- [x] 3.1 Implement shared effective-clan-tag resolution that prefers API
  `clanTag` and falls back to parsing `[TAG]` from usernames
- [x] 3.2 Build the worker flow that ingests guild-relevant OpenFront games and
  persists participant observations
- [x] 3.3 Implement per-guild player aggregate refreshes from stored
  observations for leaderboard reads
- [x] 3.4 Add historical backfill support for guild-relevant OpenFront data

## 4. Public leaderboard and player pages

- [x] 4.1 Build the public guild leaderboard using stored guild player
  aggregates only
- [x] 4.2 Implement observed player identity merging by normalized username
  within a guild, independent of tracked clan tag changes
- [x] 4.3 Add public guild player profile pages for observed and linked players
- [x] 4.4 Show linked versus observed state clearly on leaderboard entries and
  player profiles

## 5. Discord login and player linking

- [x] 5.1 Implement Discord OAuth sign-in for site users
- [x] 5.2 Add account-level linking and replacement of an OpenFront `player_id`
- [x] 5.3 Recalculate linked guild stats from `player_id` using guild clan-tag
  filters and exact alias association only
- [x] 5.4 Add a separate global OpenFront stats section to linked player
  profiles

## 6. Migration and bot compatibility

- [x] 6.1 Migrate reusable guild configuration, tracked clan tags, and any
  existing Discord-linked metadata from SQLite into the new MariaDB schema
- [x] 6.2 Keep the legacy SQLite bot flow available during initial web rollout
  while the new MariaDB pipeline is validated
- [x] 6.3 Adapt the Discord bot to consume the new shared backend model once the
  web and worker flows are stable

## 7. Verification

- [x] 7.1 Add or update tests for guild routing, clan-tag resolution, observed
  identity merging, ingestion, aggregation, and player linking
- [x] 7.2 Run the automated test suite and OpenSpec validation for the completed
  change
