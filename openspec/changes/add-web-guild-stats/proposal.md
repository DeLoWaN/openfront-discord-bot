# Add Web Guild Stats Proposal

## Why

The project is currently centered on a Discord bot with per-guild SQLite
databases, which makes it hard to publish public guild statistics and evolve
the product beyond Discord. A web-first architecture is needed now so the main
product can become a public guild stats site, with Discord kept as an optional
secondary integration.

## What Changes

- Add a public website with one manually provisioned subdomain per guild.
- Add public guild leaderboard and player profile pages backed by guild-scoped
  OpenFront data.
- Add game-first ingestion and aggregation for guild-relevant OpenFront games
  and participants.
- Add optional Discord sign-in so players can link an OpenFront `player_id`
  and get more reliable guild stats plus separate global OpenFront stats.
- Add historical clan-tag resolution that prefers API `clanTag` and falls back
  to parsing `[TAG]` from usernames when the API value is missing.
- **BREAKING** Replace the current per-guild SQLite storage model with a single
  multi-tenant MariaDB database keyed by `guild_id`.
- **BREAKING** Reposition the Discord bot as an optional secondary integration
  instead of the primary product surface.

## Capabilities

### New Capabilities

- `guild-public-sites`: Serve a public website for each manually provisioned
  guild on its own subdomain.
- `guild-player-leaderboards`: Build guild-scoped leaderboards from observed
  OpenFront games that include one of the guild's tracked clan tags.
- `player-profile-linking`: Let players sign in with Discord, link an OpenFront
  `player_id`, and display linked guild stats plus separate global stats.
- `openfront-game-ingestion`: Ingest guild-relevant public games, resolve
  effective clan tags, persist observed participants, and maintain aggregates.

### Modified Capabilities

None.

## Impact

- Adds a web application, background ingestion worker, Discord OAuth flow, and
  MariaDB-backed shared data model.
- Replaces the current per-guild SQLite isolation model with logical
  multi-tenancy via `guild_id`.
- Requires new persistence, migration, and aggregation code while keeping the
  existing ORM.
- Leaves existing Discord bot behavior in place short term, but future bot work
  will need to consume the new shared backend model.
