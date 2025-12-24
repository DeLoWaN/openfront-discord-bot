# Implementation Plan

## Goal & Scope
- Single-guild Discord bot that tracks openfront.io player wins and assigns Discord roles when thresholds are reached.
- Three selectable counting modes (stored in DB, switchable via admin command):
  1) `total`: use `/public/player/:playerId` to sum public ffa/teams wins.
  2) `sessions_since_link`: use `/public/player/:playerId/sessions`, counting wins where `endTime >= linked_at`.
  3) `sessions_with_clan` (default): use `/public/player/:playerId/sessions`, counting wins where username contains any stored clan tag (case-insensitive substring), no time bound.
- Single guild only; multiple guilds require separate bot instances and databases.

## OpenFront API Reference
- Documentation: https://github.com/openfrontio/OpenFrontIO/blob/main/docs/API.md
- Note: Example responses are obtained by querying the API; they are not embedded directly in the docs.
- Endpoints used:
  - `GET https://api.openfront.io/public/player/:playerId`: includes overall public stats; derive wins from public ffa/teams fields.
  - `GET https://api.openfront.io/public/player/:playerId/sessions`: list of sessions with username, endTime, win flag, game info; handle pagination if present.
- Only completed/public games are counted. No API key required. Implement exponential backoff with jitter on 429/5xx.

## Discord Role Thresholds (prepopulate DB; role_name exact)
- 2:  `UN Recruit | Basic | 2 wins`
- 5:  `UN Trainee | Novice | 5 wins`
- 10: `UN Novice | Beginner | 10 wins`
- 15: `UN Cadet | Junior Apprentice | 15 wins`
- 20: `UN Operator | Apprentice | 20 wins`
- 25: `UN Specialist | Junior | 25 wins`
- 40: `UN Agent | Intermediate | 40 wins`
- 60: `UN Elite Agent | Skilled | 60 wins`
- 100: `UN Veteran | Advanced | 100 wins`
- 150: `UN Warborn | Combat Specialist | 150 wins`
- 200: `UN Bloodhound | Combat Expert | 200 wins`
- 250: `UN Ace | Pro | 250 wins`
- 350: `UN Champion | Heroic | 350 wins`
- 500: `UN Legend | Expert | 500 wins`
- 600: `UN Warden | Elite Council | 600 wins`
- 700: `UN Champion | Supreme Strategist | 700 wins`

## Configuration
- YAML file (only): `token`, `admin_role_ids` (list of role IDs allowed to run admin commands), optional `database_path`.
- All other settings live in DB and are managed via commands.

## Data Model (Peewee, SQLite)
- `users(discord_user_id PK int64, player_id text, linked_at datetime UTC, last_win_count int default 0, last_role_id int64 nullable, created_at/updated_at)`.
- `roles_thresholds(id PK, wins int, role_id int64, role_name text, created_at)`.
- `clan_tags(id PK, tag_text text lowercased, created_at)`.
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
- `sessions_since_link`: filter sessions with `endTime >= linked_at`; count wins flag.
- `sessions_with_clan`: include sessions whose username (lowercased) contains any stored clan tag (lowercased); no time filter.
- Last session username: choose most recent session by endTime for `/link` confirmation.

## Role Assignment Logic
- Load thresholds sorted asc; pick highest wins <= user win_count.
- Assign that role; remove any other threshold roles the member holds.
- Store last_role_id; skip Discord calls if already correct to reduce rate-limit usage.

## Sync Engine
- Background asyncio loop sleeping `settings.sync_interval_minutes`; manual `/sync` triggers immediate run; guard with lock to prevent overlap.
- Each run: load settings/thresholds/clan tags; fetch linked users; for each, compute wins per mode; update user row; apply roles idempotently; record `last_sync_at`.
- Per-user errors logged; do not abort run. Apply global backoff using `settings.backoff_until` on repeated OpenFront failures.

## Clan Matching Rules
- Store tags lowercased; match if tag is substring of `session.username.lower()`.
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
- Fill `config.yml` with token/admin_role_ids and optional DB path.
- Create bot in Discord; invite with role management permission to target guild; ensure role IDs in DB match guild roles.
- Run bot process (systemd/docker/container); monitor logs for missing roles and sync outcomes.
- Adjust sync interval via `/set_interval` if rate limits hit; switch modes via `/set_mode` as needed.
