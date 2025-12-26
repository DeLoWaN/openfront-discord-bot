# Implementation Plan

## Goal & Scope
- Multi-guild Discord bot; tracks openfront.io player wins per guild and assigns Discord roles when thresholds are reached. Each guild is isolated in its own SQLite database.
- Three selectable counting modes (stored in DB, switchable via admin command):
  1) `total`: use `/public/player/:playerId` to sum public ffa/teams wins (medium difficulty).
  2) `sessions_since_link`: use `/public/player/:playerId/sessions`, counting wins where `gameEnd >= linked_at`.
  3) `sessions_with_clan` (default): use `/public/player/:playerId/sessions`, counting wins where username contains any stored clan tag (case-insensitive substring), no time bound.
- Supports multiple guilds in a single bot instance; each guild uses its own database for isolation.

## OpenFront API Reference
- Documentation: https://github.com/openfrontio/OpenFrontIO/blob/main/docs/API.md
- Endpoints used:
  - `GET https://api.openfront.io/public/player/:playerId`: includes overall public stats; derive wins from public ffa/teams fields. Find a example in openfront-api-examples/player_info.json
  - `GET https://api.openfront.io/public/player/:playerId/sessions`: list of sessions with username, gameEnd, win flag, game info; handle pagination if present. Find an example on openfront-api-examples/player_sessions.json
- Only completed/public games are counted. No API key required. Implement exponential backoff with jitter on 429/5xx.

## Configuration
- YAML file: `token`, optional `log_level`, and `central_database_path` (registry of guilds). No per-guild entries are required.
- All other settings live in per-guild DBs and are managed via commands.

## Data Model (Peewee, SQLite)
- `users(discord_user_id PK int64, player_id text, linked_at datetime UTC, last_win_count int default 0, last_role_id int64 nullable, created_at/updated_at)`.
- `roles_thresholds(id PK, wins int, role_id int64, role_name text, created_at)`.
- `clan_tags(id PK, tag_text text uppercased, created_at)`.
- `settings(id PK fixed 1, counting_mode text enum ['total','sessions_since_link','sessions_with_clan'], sync_interval_minutes int, backoff_until datetime nullable, last_sync_at datetime nullable, created_at/updated_at)`; defaults: counting_mode=`sessions_with_clan`, sync_interval_minutes=60.
- `audits(id PK, actor_discord_id int64, action text, payload json/text, created_at)`.

## Commands (slash)
- `/link player_id`: fetch last session username (via sessions endpoint); store/replace user with `linked_at=now`; reply with username; audit.
- `/unlink`: delete user row; audit.
- `/status [user]`: show player_id, last_win_count, last_sync_at for self; admins can inspect others.
- `/recompute [user]`: admin-only; recompute now for user or all; audit.
- `/sync`: admin-only; trigger immediate sync; audit.
- `/set_mode mode`: admin-only; update settings.counting_mode; audit.
- `/set_interval minutes`: admin-only; update settings.sync_interval_minutes (clamped bounds); audit.
- `/add_role wins role_id role_name`: admin-only; insert/update threshold; audit.
- `/remove_role wins|role_id`: admin-only; delete threshold; audit.
- `/list_roles`: list thresholds ordered asc.
- `/set_clan tag`: admin-only; add case-insensitive tag; audit.
- `/remove_clan tag`: admin-only; remove tag; audit.
- `/list_clans`: list tags.
- `/link_override user player_id`: admin-only; override link; audit.
- `/audit [page]`: admin-only; list last 20 audit entries per page.

## Win Calculation Logic
- `total`: derive wins from `/public/player` public ffa/teams fields.
- `sessions_since_link`: filter sessions with `gameEnd >= linked_at`; count wins flag.
- `sessions_with_clan`: include sessions whose username (uppercased) contains any stored clan tag (uppercased); no time filter.
- Last session username: choose most recent session by gameEnd for `/link` confirmation.

## Role Assignment Logic
- Load thresholds sorted asc; pick highest wins <= user win_count.
- Assign that role; remove any other threshold roles the member holds.
- Store last_role_id; skip Discord calls if already correct to reduce rate-limit usage.

## Sync Engine
- Background asyncio loop sleeping `settings.sync_interval_minutes`; manual `/sync` triggers immediate run; guard with lock to prevent overlap.
- Each run: load settings/thresholds/clan tags; fetch linked users; for each, compute wins per mode; update user row; apply roles idempotently; record `last_sync_at`.
- Per-user errors logged; do not abort run. Apply global backoff using `settings.backoff_until` on repeated OpenFront failures.

## Clan Matching Rules
- Store tags uppercased; match if tag is substring of `session.username.lower()`.
- No max tag limit.

## Startup/Bootstrap
- Load YAML config; validate admin roles list.
- Init DB/tables; create settings row if missing; prepopulate `roles_thresholds` with provided list (update role_id values to actual guild role IDs).
- On ready: fetch target guild, cache roles, warn if any configured role_ids missing.

## Error Handling & Resilience
- OpenFront: exponential backoff with jitter on 429/5xx; paginate sessions if needed; treat missing sessions as zero wins.
- Discord: enforce admin role check; respect rate limits (discord.py built-in); retry critical role updates on transient failures.
- Validation: non-empty player_id; sensible sync interval (e.g., 5–1440 minutes).

## Logging & Auditing
- Structured logs to stdout: user_id, player_id, mode, wins, role changes, errors.
- Audit records for all admin commands and link/unlink/recompute/sync triggers; `/audit` paginated view.

## Testing Plan
- Unit tests (mock OpenFront) for each counting mode and clan matching.
- Role resolution tests: threshold ordering, idempotency, removal of lower tiers.
- Command handler tests with fake DB.
- Integration smoke in a test guild: `/link`, `/sync`, verify role assignment; change mode and rerun.

## Deployment Plan
- Fill `config.yml` with the bot token and optional `central_database_path` and `log_level`.
- Create bot in Discord; invite with role management permission to target guild; ensure role IDs in DB match guild roles after seeding.
- Run bot process (systemd/docker/container); monitor logs for missing roles and sync outcomes.
- Adjust sync interval via `/set_interval` if rate limits hit; switch modes via `/set_mode` as needed.
