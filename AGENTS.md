# AGENTS.md

## 1. Overview

- OpenFront Guild Stats is now a web-first OpenFront stats platform. The public
  guild website and ingestion/backfill flow are the primary product surfaces;
  the Discord bot remains as a secondary integration and compatibility path.
- The dedicated `historical-backfill` CLI and durable MariaDB backfill state
  are the supported operational path for month-scale history imports.
- Shared domain logic should live below the app layer. Prefer implementing core
  behavior in `src/core`, `src/data`, and `src/services`, then wiring it into
  `src/apps/web`, `src/apps/worker`, `src/apps/cli`, or `src/apps/bot`.
- OpenSpec artifacts in `openspec/` are part of the working contract. When a
  change exists, treat its proposal, design, specs, and tasks as the source of
  truth instead of inferring scope from older code paths.
- Peewee is the repository ORM for both legacy SQLite and shared MariaDB data.
  Keep using it unless a change explicitly states otherwise.
- The repository uses Pipenv with the root `Pipfile`/`Pipfile.lock`. Run
  project commands inside that environment, typically with `pipenv run ...`.

## 2. Folder Structure

- `src/apps/bot`: packaged Discord bot runtime and entrypoint wiring
- `src/apps/cli`: operational CLIs for guild-site management and historical
  backfill runs
- `src/apps/web`: FastAPI guild site, leaderboard, profile, auth, and account
  routes
- `src/apps/worker`: reusable ingestion and historical backfill runtime helpers
- `src/core`: shared config loading, OpenFront client, and win/stat helpers
- `src/data/database.py`: shared database proxy/bootstrap for the MariaDB path
- `src/data/legacy`: legacy per-guild SQLite schema and central registry logic
- `src/data/shared`: shared MariaDB models, additive schema bootstrap, durable
  backfill state, and cached OpenFront game payloads
- `src/services`: guild provisioning, leaderboards, ingestion, OAuth, account
  linking, legacy migration, historical backfill orchestration, and bot/shared
  bridge logic
- `src/*.py`: compatibility shims that preserve older import paths; keep them
  stable unless a deliberate cleanup removes downstream consumers
- `tests`: regression coverage for the legacy bot, shared backend, and web app
- `openspec`: change proposals, designs, specs, and task lists
- `openfront-api-examples`: reference payloads for the OpenFront public API
- `guild_data/`: generated legacy SQLite guild databases; treat as runtime data
- `guild-sites` / `historical-backfill`: repo-local launcher scripts for the
  supported operational CLIs

## 3. Core Behaviors & Patterns

- The product is web-first: guild sites should read stored aggregates from the
  shared schema, while ingestion and backfill populate those records.
- Historical backfill is hybrid by design: team discovery comes from clan
  sessions, while FFA discovery comes from `/public/games`.
- Historical date filtering is based on the game start time. Keep that boundary
  behavior intact when changing discovery or hydration code.
- Backfill discovery must deduplicate by `openfront_game_id` before hydration.
- Cache turn-free OpenFront game payloads locally so ingestion can be replayed
  without another crawl when requirements change.
- Long-running backfill paths should persist progress and emit useful logging so
  operators can monitor discovery and hydration.
- Keep handlers thin. HTTP endpoints and Discord commands should delegate to
  service-layer functions instead of reimplementing business rules inline.
- Compatibility still matters. Linking, clan tags, usernames, and win-count
  changes often touch both the shared backend and the legacy bot bridge.
- Ingestion resolves effective clan tags from API fields first and only falls
  back to parsing a `[TAG]` username prefix when `clanTag` is missing.
- Schema work should stay additive and migration-safe. Follow the patterns in
  `src/data/shared/schema.py` and `src/services/legacy_migration.py`.

## 4. Conventions

- Keep Python code explicit and small: snake_case, narrow helpers, and comments
  only where the logic is not already obvious from the code.
- Keep CLI modules thin. Argument parsing and environment bootstrap belong in
  `src/apps/cli`; operational behavior belongs in `src/services`.
- Prefer `pipenv run <command>` for repository commands so tools execute
  against the dependencies declared in the root `Pipfile`.
- Prefer single-purpose modules colocated near related code rather than adding
  generic utility layers.
- Preserve public route paths, bot command names, and compatibility imports
  unless the change explicitly requires breaking them.
- When behavior changes, keep OpenSpec artifacts and user-facing docs aligned so
  the repo does not drift back to stale operational guidance.
- Avoid bypassing Peewee models or service-layer functions for core flows unless
  there is a repo-wide reason to do so.

## 5. Working Agreements

- Respond in the user's preferred language; if unspecified, infer from repo
  context. Keep technical terms in English and never translate code blocks.
- Create tests, lint, or format tasks only when the user explicitly asks for
  them.
- Before editing, review related usages, wrappers, and tests because many flows
  still bridge legacy and shared code.
- When touching historical backfill, review the CLI, service layer, shared
  models, and OpenSpec change together because correctness depends on persisted
  state and OpenFront API constraints.
- Prefer minimal, focused changes that match the requested scope; avoid
  opportunistic refactors.
- Ask for clarification when requirements or rollout behavior are ambiguous,
  especially around legacy/shared cutover points.
- Preserve public APIs and behavior unless the user asks to change them, and
  call out any intentional behavior change.
- After implementing a change, validate the affected behavior with the
  Playwright MCP before considering the task complete. Verification must cover
  functional needs end to end, inspect view/controller/data-model coherence,
  confirm the browser console stays free of errors, and look for visual bugs or
  inconsistent UI states.
- Run `basedpyright` after code changes when type safety needs verification;
  `pyrightconfig.json` is the repo's current type-check configuration.
- Keep new functions and modules single-purpose and close to the code they
  support.
- Add external dependencies only when necessary and explain why.
