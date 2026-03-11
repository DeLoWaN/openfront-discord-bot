# Web-First Guild Stats Design

## Summary

This project should evolve from a Discord-bot-first tool into a web-first
OpenFront stats product. The primary product becomes a public website with one
subdomain per guild, while the Discord bot remains an optional secondary
integration.

## Product Direction

- The public website is the primary user-facing product.
- Each guild is provisioned manually.
- Each guild is served from its own subdomain.
- Discord integration is optional for a guild and optional for end users.
- End users may sign in with Discord to link an OpenFront `player_id`.

## Data Scope

- Guild leaderboards only include games relevant to that guild.
- A game is relevant when at least one configured guild clan tag appears in the
  observed game data.
- Data outside the guild's tracked clan tags is ignored for leaderboard purposes.

## Identity Model

- Observed players exist even if they never sign in.
- Observed identity is based on `(guild_id, normalized_username)`.
- The same username appearing under multiple tracked clan tags for the same
  guild is treated as one observed player.
- No fuzzy matching is performed between similar usernames.
- If two different people use the exact same username inside one guild scope,
  they may be merged until a stronger identity signal exists.

## Clan Tag Resolution

For each observed player/session/game participant:

- Use `clanTag` from the API when present.
- If `clanTag` is missing or null, parse the first `[TAG]` found anywhere in
  the username.
- Store both the raw values and the resolved `effective_clan_tag`.
- Record whether the tag came from the API or username parsing.

This preserves support for historical OpenFront data where clan tags were
embedded in usernames instead of exposed in a dedicated field.

## Statistics Model

Guild leaderboard stats and public guild profiles use two levels of confidence:

1. Observed stats
   - Derived from observed guild-relevant games and participants.
   - Useful for all players.
   - Approximate when usernames change.

2. Linked stats
   - Available when a signed-in user links an OpenFront `player_id`.
   - Used to recalculate that player's guild stats more reliably.
   - Can also display separate global OpenFront stats outside the guild
     leaderboard.

The guild leaderboard remains guild-scoped. Linked global OpenFront stats are
shown separately on player profiles and do not replace the guild leaderboard
basis.

## Storage Direction

- Replace per-guild SQLite databases with a single MariaDB database.
- Keep the current ORM to reduce migration risk.
- Use logical multi-tenancy via `guild_id` instead of one database file per
  guild.

## Target Architecture

- `apps/web`: public website, guild pages, player profiles, Discord login
- `apps/worker`: OpenFront ingestion, backfill, aggregation, recalculation
- `apps/bot`: optional Discord integration
- shared core/data packages or modules for business logic and persistence

The worker is responsible for collecting OpenFront data and persisting
aggregates. The web app should read precomputed aggregates instead of
recalculating leaderboards on request.

## Target Data Model

Core entities:

- `guilds`
- `guild_clan_tags`
- `site_users`
- `players`
- `player_aliases`
- `player_links`
- `games`
- `game_participants`
- `guild_player_stats`

Key rules:

- `guilds` support manual provisioning and per-guild subdomains.
- `players` can exist without a linked `player_id`.
- `player_aliases` track observed usernames and clan tags over time.
- `games` and `game_participants` are the raw observation layer.
- `guild_player_stats` is the read-optimized aggregate layer.

## Migration Strategy

Recommended order:

1. Introduce MariaDB configuration and new Peewee models.
2. Migrate configuration data that still matters from the SQLite setup.
3. Build a game-first OpenFront ingestion pipeline.
4. Backfill guild-relevant data into raw and aggregate tables.
5. Launch a minimal public web app.
6. Add Discord login and `player_id` linking.
7. Adapt the Discord bot to use the new shared backend later.

The important point is to avoid treating current SQLite aggregates such as
`last_win_count` as the long-term source of truth for the website.

## UX Notes

- Public leaderboard should clearly distinguish `Linked` players from unlinked
  observed players.
- Avoid words like `Verified`, which imply stronger ownership guarantees than
  Discord login actually provides.
- Player pages should show:
  - guild-specific stats
  - separate OpenFront global stats when the player linked a `player_id`

## Recommendation

Proceed with a single-repo migration toward a web-first product, keep the
existing ORM, move persistence to MariaDB, and build the website on top of a
new game-first ingestion and aggregation model.
