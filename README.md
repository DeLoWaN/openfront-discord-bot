# OpenFront Guild Stats

Web-first OpenFront guild stats platform with a legacy Discord bot integration.

This repository now contains three product surfaces that share the same domain
logic:

- a public guild website
- an OpenFront ingestion and backfill worker
- the original Discord bot, kept alive during the migration

The important part if you are coming back to the repo after the recent changes:

- the Discord bot still works and is the easiest thing to run immediately
- the shared MariaDB schema, web routes, OAuth flow, and migration bridge now
  exist
- a dedicated `historical-backfill` CLI now exists for long-running history
  imports, status checks, resume, and cache replay

## Current status

Currently present in the repo:

- shared package layout: `src/apps`, `src/core`, `src/data`, `src/services`
- external CLIs under `src/apps/cli` for website guild CRUD and historical
  backfill operations
- shared MariaDB-backed Peewee schema for guilds, observed games, players, site
  users, aliases, links, and aggregates
- additive schema bootstrap and migration helpers
- website guild create/list/show/update/activate/deactivate/delete flows backed
  by the shared MariaDB schema
- public guild site routes:
  - `/`
  - `/leaderboard`
  - `/players`
  - `/players/{normalized_username}`
- guild stats API routes:
  - `/api/leaderboards/{view}`
  - `/api/scoring/{view}`
  - `/api/players/{normalized_username}`
- Discord OAuth sign-in and account linking routes:
  - `/auth/discord/login`
  - `/auth/discord/callback`
  - `/account`
  - `/account/link`
- shared ingestion logic for effective clan tag resolution, observed
  participants, aggregate refreshes, and historical backfill
- competitive leaderboard support for `Team`, `FFA`, `Overall`, and `Support`
  views backed by stored aggregates
- durable backfill run, cursor, queue, and cached OpenFront game payload tables
- hybrid historical backfill:
  - team discovery via clan sessions
  - FFA discovery via `/public/games`
  - deduplication by OpenFront game id
  - historical filtering by game start time
  - cache-backed replay without a second crawl, including turn data for Team
    games
- stdout progress logging plus persisted run status for long backfills
- legacy SQLite to shared-schema migration helper
- legacy Discord bot compatibility, with optional mirroring of bot links into
  the shared backend when MariaDB is configured

Still intentionally rough:

- no packaged web server command in the repo yet
- no packaged long-running worker daemon yet; historical backfill is driven by
  the dedicated CLI
- there is still no web admin UI; website guild management is CLI-only
- legacy SQLite and shared MariaDB models currently coexist during rollout

## What should you do now?

Pick one of these paths:

### 1. You just want something working today

Run the legacy Discord bot.

This is the lowest-friction path. You only need `config.yml`, no MariaDB, and
you can keep using the existing slash-command workflow.

### 2. You want to continue the web-first migration

Do these steps in order:

1. Create a MariaDB database and user.
2. Fill `mariadb` and `discord_oauth` in `config.yml`.
3. Bootstrap the shared schema and migrate any legacy SQLite bot data.
4. Create at least one guild site with the CLI.
5. Run the FastAPI app locally behind an ASGI server.
6. Backfill historical OpenFront games for that guild.

Concrete commands for all of those steps are included below.

### 3. You want to verify the repo before doing anything else

Run:

```bash
pytest -q
openspec validate add-competitive-web-leaderboards --type change --strict
```

## Repository layout

```text
src/
  apps/
    bot/      Legacy Discord bot entrypoints
    cli/      Website guild management and historical backfill CLIs
    web/      FastAPI public site
    worker/   Ingestion/backfill runtime helpers
  core/       Shared config, OpenFront client, win utilities
  data/
    legacy/   Existing SQLite bot models
    shared/   New shared MariaDB-oriented models and schema bootstrap
  services/   Provisioning, ingestion, linking, migration, backfill logic
tests/        Legacy bot tests plus new web/shared-backend coverage
```

Root launchers:

- `./guild-sites`
- `./historical-backfill`

## Prerequisites

- Python 3.10+
- `pip`
- network access to `https://api.openfront.io`
- a Discord application and bot token if you want to run the bot
- a MariaDB server if you want to use the shared backend and website
- a Discord OAuth application if you want the website login flow
- an ASGI server such as `uvicorn` if you want to serve the FastAPI app locally

## Installation

For runtime-only usage, a plain virtual environment is enough:

```bash
git clone https://github.com/DeLoWaN/openfront-discord-bot
cd openfront-discord-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If you want to run the web app locally, install an ASGI server too:

```bash
pip install uvicorn
```

For development tooling from `Pipfile`, including `basedpyright`, use Pipenv:

```bash
pip install pipenv
pipenv sync --dev
```

Useful Pipenv commands:

```bash
pipenv run typecheck
pipenv run lint
pipenv run test
```

## Configuration

Copy the example file:

```bash
cp config.example.yml config.yml
```

Current config shape:

```yaml
token: "DISCORD_BOT_TOKEN"
central_database_path: "central.db"
log_level: "INFO"
sync_interval_hours: 24
results_lobby_poll_seconds: 2

mariadb:
  database: "openfront"
  user: "openfront"
  password: "change-me"
  host: "127.0.0.1"
  port: 3306
  charset: "utf8mb4"

discord_oauth:
  client_id: "discord-client-id"
  client_secret: "discord-client-secret"
  redirect_uri: "https://guild.example.com/auth/discord/callback"
  session_secret: "replace-with-a-long-random-secret"
  scope: "identify"
```

Notes:

- `token` is required by the current shared config loader. If you are only
  experimenting with the web app, you still need a non-empty placeholder value.
- `central_database_path` is the legacy bot registry and is also used by the
  SQLite-to-shared migration helper.
- omit `mariadb` and `discord_oauth` if you only want the legacy bot
- if `mariadb` is configured and you run the bot, the bot will bootstrap the
  shared schema bridge and mirror bot links into the shared backend

You can also point the bot to another config file with:

```bash
export CONFIG_PATH=/absolute/path/to/config.yml
```

## Path A: Run the legacy Discord bot

Start the bot:

```bash
source .venv/bin/activate
python -m src.bot
```

What happens:

- `central_database_path` is created if needed
- each Discord guild gets its own SQLite database in `guild_data/`
- slash commands are synced automatically
- admin roles are seeded from roles with `Administrator` or `Manage Guild`
- if `mariadb` is configured, the bot also bootstraps the shared backend bridge

Recommended first steps in Discord:

1. Invite the bot to your server with `Manage Roles`, `View Channels`,
   `Send Messages`, and `applications.commands`.
2. Add tier roles with `/roles_add`.
3. Enable role assignment with `/roles_start`.
4. Add clan tags with `/clan_tag_add`.
5. Link a test player with `/link`.
6. Run `/sync`.
7. Optionally enable results posting with `/post_game_results_start`.

## Path B: Enable the shared backend and website

### Step 1: Configure MariaDB and Discord OAuth

Fill the `mariadb` block in `config.yml`.

If you want player sign-in on the website, also fill `discord_oauth`.

### Step 2: Bootstrap the shared schema and migrate legacy bot data

The repo currently exposes migration as a Python helper, not a dedicated CLI.

Run:

```bash
python - <<'PY'
from src.core.config import load_config
from src.data.database import init_shared_database
from src.data.shared.schema import bootstrap_shared_schema
from src.services.legacy_migration import migrate_legacy_sqlite_to_shared

config = load_config("config.yml")
if not config.mariadb:
    raise SystemExit("config.yml is missing the mariadb section")

database = init_shared_database(config.mariadb)
bootstrap_shared_schema(database)
summary = migrate_legacy_sqlite_to_shared(config.central_database_path)
print(summary)
PY
```

What this migrates:

- guild identity placeholders for existing Discord guild ids
- guild clan tags
- Discord-linked users
- linked OpenFront player ids
- last known OpenFront usernames as exact aliases

### Step 3: Manage guild sites with the CLI

There is no admin UI yet. Use the external CLI instead:

Create a guild:

```bash
./guild-sites create \
  --slug north-guild \
  --subdomain north \
  --display-name "North Guild" \
  --clan-tag NU \
  --clan-tag NTH \
  --discord-guild-id 123456789012345678
```

List all guilds:

```bash
./guild-sites list
```

Show one guild:

```bash
./guild-sites show --slug north-guild
```

Update a guild:

```bash
./guild-sites update \
  --slug north-guild \
  --display-name "North Wolves" \
  --new-subdomain wolves \
  --clan-tag WLF
```

Deactivate or reactivate a guild site without deleting data:

```bash
./guild-sites deactivate --subdomain wolves
./guild-sites activate --subdomain wolves
```

Delete a guild site permanently:

```bash
./guild-sites delete --subdomain wolves --confirm
```

### Step 4: Run the web app locally

There is no packaged web runner yet, but the FastAPI app factory is ready.

Run:

```bash
python - <<'PY'
from src.core.config import load_config
from src.data.database import init_shared_database
from src.data.shared.schema import bootstrap_shared_schema
from src.apps.web.app import create_app
import uvicorn

config = load_config("config.yml")
database = init_shared_database(config.mariadb)
bootstrap_shared_schema(database)

uvicorn.run(
    create_app(config=config),
    host="127.0.0.1",
    port=8000,
)
PY
```

For local subdomain testing, use a host like:

- `http://north.localhost:8000`

If `*.localhost` subdomains do not resolve on your machine, add a local hosts
entry and send the correct `Host` header through your proxy.

### Step 5: Backfill historical OpenFront games

Use the dedicated CLI for historical runs.

Start a run:

```bash
./historical-backfill start \
  --start 2026-03-01T00:00:00Z \
  --end 2026-03-31T23:59:59Z
```

Inspect persisted status and cursor progress:

```bash
./historical-backfill status --run-id 1
```

Resume an interrupted run:

```bash
./historical-backfill resume --run-id 1
```

Replay cached payloads without crawling OpenFront again:

```bash
./historical-backfill replay --run-id 1
```

Reset ingested web data before rebuilding from the API:

```bash
./historical-backfill reset-data --confirm
```

Operational notes:

- the CLI requires `mariadb` to be configured
- runs are resumable through persisted run and cursor state
- team history is discovered through clan sessions
- FFA history is discovered through `/public/games`
- discovery deduplicates by OpenFront game id before hydration
- historical date boundaries are applied on the game start time
- fetched game details are cached locally, and Team games retain turn data so
  donation-based support metrics can be replayed later
- progress logs are emitted to stdout during discovery and hydration
- `reset-data` clears ingestion/cache/backfill tables only and preserves guild
  configuration plus linked account records

Tuning flags:

- `--concurrency`:
  concurrent `fetch_game()` workers during hydration
- `--refresh-batch-size`:
  how often aggregate refreshes are flushed
- `--progress-every`:
  how often hydration progress is logged

The worker runtime still exposes reusable async helpers for code-driven flows.

Programmatic example:

```bash
python - <<'PY'
import asyncio
from datetime import datetime

from src.core.config import load_config
from src.data.database import init_shared_database
from src.data.shared.schema import bootstrap_shared_schema
from src.apps.worker.app import create_worker

config = load_config("config.yml")
database = init_shared_database(config.mariadb)
bootstrap_shared_schema(database)

worker = create_worker()

async def main():
    summary = await worker.backfill(
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 11),
    )
    print(summary)
    await worker.client.close()

asyncio.run(main())
PY
```

## Website behavior

The implemented public web surface currently supports:

- guild resolution by subdomain
- guild home page with tracked clan tags
- leaderboard reads from stored guild aggregates only
- separate `Team`, `FFA`, `Overall`, and `Support` leaderboard views
- guild-scoped JSON endpoints for leaderboard, scoring, and player profile data
- public player profiles for observed-only and linked players
- Discord OAuth sign-in
- account-level OpenFront player linking
- separate guild-scoped and global OpenFront stats on linked profiles
- concise scoring explanations exposed by the backend

Important behavior rules:

- observed players are keyed by `(guild_id, normalized_username)`
- clan tag matching prefers API `clanTag` and falls back to `[TAG]` in username
- exact aliases from linked player history are associated; fuzzy matching is not
  used
- linked profiles show global OpenFront wins separately from guild-scoped stats
- Team score rewards wins most, gives more weight to recent results, counts
  matches with more teams as harder, and adds a limited support bonus from
  exact troop and gold donations
- Overall score combines `70% Team` and `30% FFA`

## Discord bot commands

### User commands

| Command | Purpose |
| --- | --- |
| `/link <player_id>` | Link your Discord account to an OpenFront player id |
| `/unlink` | Remove your link |
| `/status [user]` | Show your link status; admins can inspect another user |
| `/roles_list` | List configured role thresholds |
| `/clans_tag_list` | List stored clan tags |

### Admin commands

| Command | Purpose |
| --- | --- |
| `/sync [user]` | Trigger an immediate sync |
| `/set_mode <mode>` | Set counting mode |
| `/get_mode` | Show current counting mode |
| `/roles_start` | Enable role threshold assignments |
| `/roles_stop` | Disable role threshold assignments |
| `/roles_add wins:<n> role:<role>` | Add or update a threshold role |
| `/roles_remove [wins] [role]` | Remove a threshold role |
| `/clan_tag_add <tag>` | Add a clan tag |
| `/clan_tag_remove <tag>` | Remove a clan tag |
| `/post_game_results_start` | Enable results posting |
| `/post_game_results_stop` | Disable results posting |
| `/post_game_results_channel <channel>` | Set the results channel |
| `/post_game_results_test` | Seed recent public games for results testing |
| `/link_override <user> <player_id>` | Override a user link |
| `/admin_role_add <role>` | Add a guild admin role override |
| `/admin_role_remove <role>` | Remove a guild admin role override |
| `/admin_roles` | List admin role overrides |
| `/audit [page]` | Show recent audit entries |
| `/guild_remove confirm:true` | Delete guild legacy SQLite data and leave |

### Counting modes

- `sessions_with_clan`:
  default mode; counts wins in public sessions whose clan tag matches a stored
  guild tag
- `sessions_since_link`:
  counts wins in sessions starting after the user linked
- `total`:
  counts total public FFA + Team wins from the player profile

## Data storage

There are currently two storage layers in the repo.

### Legacy SQLite layer

Used by the existing Discord bot flow.

- central registry:
  `central_database_path`
- per-guild databases:
  `guild_data/guild_<guild_id>.db`

### Shared backend layer

Used by the new web-first architecture.

- MariaDB via Peewee `MySQLDatabase`
- shared tables for guilds, clan tags, observed games, participants, site users,
  players, aliases, links, guild player aggregates, backfill runs/cursors, and
  cached OpenFront game payloads

Current coexistence rule:

- if `mariadb` is not configured, the bot remains SQLite-only
- if `mariadb` is configured, the bot still uses SQLite for its primary guild
  flow but mirrors link data into the shared backend

## Validation and tests

Run the full suite:

```bash
pytest -q
```

Validate the current OpenSpec changes:

```bash
openspec validate add-competitive-web-leaderboards --type change --strict
```

## Known limitations

- there is no packaged web runner yet
- there is no packaged always-on worker daemon yet; history imports are run via
  `./historical-backfill`
- shared-schema migration is still a manual Python helper
- website guild management is CLI-only; there is no web admin UI
- the shared config loader still requires a non-empty `token`
- the shared backend bridge is intentionally conservative; the legacy bot still
  owns its main guild workflow until the full cutover happens

## If you only read one section

If you are unsure what to do next, do this:

1. Keep using the bot if your immediate goal is a working product.
2. Add MariaDB config only when you are ready to test the web-first path.
3. Run the migration helper once.
4. Create one guild with `./guild-sites create ...`.
5. Start the web app locally on `north.localhost:8000`.
6. Backfill a small date range and confirm the leaderboard fills in.
