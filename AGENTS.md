<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# Implementation Plan

## Goal & Scope
- Multi-guild Discord bot; tracks openfront.io player wins per guild and assigns Discord roles when thresholds are reached. Each guild is isolated in its own SQLite database.
- Three selectable counting modes (stored in DB, switchable via admin command):
  1) `total`: use `/public/player/:playerId` to sum public ffa/teams wins (medium difficulty).
  2) `sessions_since_link`: use `/public/player/:playerId/sessions`, counting wins where `gameStart >= linked_at` (fall back to `gameEnd` if start time is missing).
  3) `sessions_with_clan` (default): use `/public/player/:playerId/sessions`, counting wins from PUBLIC games where the session `clanTag` (or a `[TAG]` prefix parsed from username when `clanTag` is empty) matches a stored clan tag. No time bound.
- Supports multiple guilds in a single bot instance; each guild uses its own database for isolation.
- Post match results to a configured Discord channel shortly after a clan win is detected.
- Track wins for all clan tags stored in the guild database; treat them as aliases of the same guild.
- One embed per game using OpenFront game details discovered via public lobbies; per-guild settings and persistence with no cross-guild leakage.

## OpenFront API Reference
- Documentation: https://github.com/openfrontio/OpenFrontIO/blob/main/docs/API.md
- Endpoints used:
  - `GET https://api.openfront.io/public/player/:playerId`: includes overall public stats; derive wins from public ffa/teams fields. Find a example in openfront-api-examples/player_info.json
  - `GET https://api.openfront.io/public/player/:playerId/sessions`: list of sessions with username, gameEnd, win flag, game info; handle pagination if present. Find an example on openfront-api-examples/player_sessions.json
  - `GET https://api.openfront.io/public/game/<gameId>?turns=false`: game details for embeds
  - `GET https://api.openfront.io/public_lobbies`: list live lobbies used to discover game IDs
  - `GET https://api.openfront.io/public/games?start=...&end=...`: list recent games (used for results test seeding)
- Only completed/public games are counted. No API key required. Implement exponential backoff with jitter on 429/5xx.

## Configuration
- YAML file: `token`, optional `log_level`, and `central_database_path` (registry of guilds). No per-guild entries are required.
- All other settings live in per-guild DBs and are managed via commands.

## Data Model (Peewee, SQLite)
- `users(discord_user_id PK int64, player_id text, linked_at datetime UTC, last_win_count int default 0, last_role_id int64 nullable, last_username text nullable, last_openfront_username text nullable, created_at/updated_at)`.
- `roles_thresholds(id PK, wins int unique, role_id int64 unique, created_at/updated_at)`.
- `clan_tags(id PK, tag_text text uppercased, created_at/updated_at)`.
- `settings(id PK fixed 1, counting_mode text enum ['total','sessions_since_link','sessions_with_clan'], sync_interval_minutes int (legacy), backoff_until datetime nullable, last_sync_at datetime nullable, results_enabled int default 0, results_channel_id int nullable, created_at/updated_at)`; defaults: counting_mode=`sessions_with_clan`, sync_interval_minutes=1440 (24h) until migrated to hours.
- `audits(id PK, actor_discord_id int64, action text, payload json/text, created_at/updated_at)`.
- `guild_admin_roles(role_id PK int64, created_at/updated_at)`.
- `posted_games(game_id text PK, game_start datetime nullable, posted_at datetime not null, winning_tags text nullable)`.

### Migrations
- Use `PRAGMA table_info` with `ALTER TABLE` for new columns, matching existing patterns.
- Create `posted_games` if missing.

## Commands (slash)
- `/link player_id`: fetch last session username; store/replace user with `linked_at=now`; reply with username and immediate win count if fetched; audit.
- `/unlink`: delete user row; audit.
- `/status [user]`: show player_id, last_win_count, last_sync_at for self; admins can inspect others.
- `/sync [user]`: admin-only; trigger immediate sync for all users or a specific user; audit.
- `/set_mode mode`: admin-only; update settings.counting_mode; audit.
- `/get_mode`: admin-only; read current counting mode.
- `/roles_add wins role`: admin-only; insert/update threshold; audit.
- `/roles_remove [wins] [role]`: admin-only; delete threshold by wins and/or role; audit.
- `/roles`: list thresholds ordered asc.
- `/clan_tag_add tag`: admin-only; add tag (stored uppercased); audit.
- `/clan_tag_remove tag`: admin-only; remove tag; audit.
- `/clans_list`: list tags.
- `/link_override user player_id`: admin-only; override link; audit.
- `/admin_role_add role`: admin-only; add admin role override; audit.
- `/admin_role_remove role`: admin-only; remove admin role override; audit.
- `/admin_roles`: admin-only; list admin role IDs.
- `/guild_remove confirm:true|false`: admin-only; delete guild data and leave.
- `/audit [page]`: admin-only; list last 20 audit entries per page.
- `/post_game_results_start`: enable posting; if a channel is set, trigger an immediate poll.
- `/post_game_results_stop`: disable posting without clearing state.
- `/post_game_results_channel <channel>`: set channel ID; triggers immediate poll if enabled.

## Win Calculation Logic
- `total`: derive wins from `/public/player` public ffa/teams fields.
- `sessions_since_link`: filter sessions with `gameStart >= linked_at` (fall back to `gameEnd` if start is missing); count wins flag.
- `sessions_with_clan`: include PUBLIC sessions whose `clanTag` matches a stored tag (uppercase). If `clanTag` is empty, parse `[TAG]` from username and match against stored tags. Skip sessions without a tag match; no time filter.
- Last session username: choose most recent session by gameEnd for `/link` confirmation.
- Store OpenFront usernames in `users.last_openfront_username` (updated on `/link` and during session-based win computation from most recent session).

## Role Assignment Logic
- Load thresholds sorted asc; pick highest wins <= user win_count.
- Assign that role; remove any other threshold roles the member holds.
- Store last_role_id; skip Discord calls if already correct to reduce rate-limit usage.

## Sync Engine
- Background scheduler enqueues guild syncs on a jittered cadence derived from `config.sync_interval_hours`; manual `/sync` triggers immediate run; guard with lock to prevent overlap.
- Each run: load settings/thresholds/clan tags; fetch linked users; for each, compute wins per mode; update user row (win_count, last_role_id, last_username); apply roles idempotently; record `last_sync_at`.
- Per-user errors logged; do not abort run. Apply global backoff using `settings.backoff_until` (currently +5 minutes) on repeated OpenFront failures.

## Clan Matching Rules
- Store tags uppercased; match against `session.clanTag` (uppercased) or a `[TAG]` prefix parsed from username when `clanTag` is absent. Only PUBLIC games count. No max tag limit.

## Startup/Bootstrap
- Load YAML config; validate admin roles list.
- Init DB/tables; create settings row if missing; seed admin roles from guild roles that have Administrator or Manage Guild permissions; warn if any configured threshold roles are missing in the guild. Thresholds are not pre-seeded.
- On ready: fetch target guild, cache roles, warn if any configured role_ids missing.

## Error Handling & Resilience
- OpenFront: exponential backoff with jitter on 429/5xx; paginate sessions if needed; treat missing sessions as zero wins. Results posting retries per game with rescheduled attempts and a failure limit.
- Discord: enforce admin role check; respect rate limits (discord.py built-in); retry critical role updates on transient failures.
- Validation: non-empty player_id; sensible sync interval (1–24 hours at config level).

## Logging & Auditing
- Structured logs to stdout: user_id, player_id, mode, wins, role changes, errors.
- Audit records for all admin commands and link/unlink/sync triggers; `/audit` paginated view.

## Testing Plan
- Unit tests (mock OpenFront) for each counting mode and clan matching.
- Role resolution tests: threshold ordering, idempotency, removal of lower tiers.
- Command handler tests with fake DB.
- Integration smoke in a test guild: `/link`, `/sync`, verify role assignment; change mode and rerun.
- Unit tests for results posting: dedupe via `posted_games`, winner/opponent aggregation, mention mapping (0/1/many), mode formatting (named vs numeric), team size inference, commands start/stop/channel, `/status` includes `last_openfront_username`.

## Deployment Plan
- Fill `config.yml` with the bot token and optional `central_database_path`, `log_level`, and global `sync_interval_hours`.
- Create bot in Discord; invite with role management permission to target guild; ensure role IDs in DB match guild roles after seeding.
- Run bot process (systemd/docker/container); monitor logs for missing roles and sync outcomes.
- Adjust sync interval via config if rate limits hit; switch modes via `/set_mode` as needed.

## Results Posting Requirements
### Functional
- Track public lobbies via `/public_lobbies` to discover active game IDs and store them in the central DB for later processing.
- For each due tracked game, fetch `/public/game/<gameId>?turns=false`, resolve winning clan tags from winner client IDs, and post results only when configured clan tags intersect the winners.
- Post one embed per game to the configured results channel; record `posted_games` to dedupe.
- Opponents: group other `clanTag` values, include player count and player list.
- Mentions: if a username matches exactly one `users.last_openfront_username` (case-sensitive), mention that Discord user; otherwise keep plain username (applies to winners and opponents).
- If team size is known and fewer tagged winners are present, append `+N other player(s)` to the winners field.
- Extend `/status` to show last known OpenFront username.

### Timing
- Public lobby polling interval: `config.results_lobby_poll_seconds` (min 1 second).
- Tracked games are retried after `RESULTS_GAME_RETRY_SECONDS` when incomplete or transiently failing; processing runs as soon as games are due (no per-guild poll interval).

### Results Poller Architecture
- `results_lobby_loop` polls public lobbies, extracts game IDs, and calls `track_game` with a `next_attempt_at`.
- `results_worker` pulls due tracked games in batches; for each game, fetch details, reschedule on retryable failures, and drop after exceeding the unexpected failure limit.
- For each guild with results enabled and a configured channel, post embeds for matching winning tags and store a `posted_games` record to avoid duplicates.

### Embed Format
- Title: `🏆 Victory for <TAG1 / TAG2>` (winning tags joined with `/`).
- Description includes map name, mode string, finished time + duration, replay link.
- Fields:
  - Winners: one per line, with `🎉` prefix.
  - Opponents: `TAG: count players (name list)` (one per line).
- Team mode formatting:
  - Named values: `X teams (Trios)` for duos/trios/quads.
  - Numeric values: `X teams (12 players per team)` and use `totalPlayerCount/numTeams` when `playerTeams == numTeams`.
- No embed timestamp is set (finished time is shown in the description).

### Cleanup
- Prune `posted_games` entries older than 7 days (daily cleanup loop).
