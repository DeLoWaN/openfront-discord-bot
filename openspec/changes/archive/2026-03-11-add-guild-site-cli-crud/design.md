# Add Guild Site CLI CRUD Design

## Context

Website guild management currently exists as a manual Python snippet that calls
`provision_guild_site()` after loading config, initializing MariaDB, and
bootstrapping the shared schema. That is acceptable for initial scaffolding,
but it is not an operational interface: listing guilds, inspecting one guild,
disabling a site, and deleting a guild all require direct code execution or raw
database access.

The current service boundary is also biased toward provisioning, not strict
CRUD. `provision_guild_site()` normalizes inputs and either creates or updates a
guild by matching on slug, subdomain, or Discord guild id. That behavior is
useful for migration and manual setup, but it is too implicit for an external
CLI where operators need predictable create, read, update, deactivate, and
delete semantics.

This change needs a small admin surface that stays outside the website, uses
the existing shared MariaDB path, and fits the current `src/apps`,
`src/services`, and `src/data` structure without introducing a second
management stack.

## Goals / Non-Goals

**Goals:**

- Add an external CLI entrypoint for website guild management.
- Support strict create, list/read, update, deactivate/reactivate, and delete
  flows.
- Reuse existing guild normalization and clan-tag rules instead of duplicating
  them in the CLI layer.
- Keep the shared schema bootstrap path inside the CLI so operators can run the
  commands against a fresh MariaDB environment.
- Update the README so the supported operational workflow is CLI-first instead
  of Python-snippet-first.

**Non-Goals:**

- Add a web admin UI or authenticated operator dashboard.
- Replace the existing `provision_guild_site()` helper where migration code
  already depends on it.
- Introduce a new dependency such as Click or Typer just for this CLI.
- Redefine the legacy Discord bot `/guild_remove` flow.
- Add bulk import/export workflows in the same change.

## Decisions

### 1. Add a dedicated CLI app under `src/apps`

The CLI will live under `src/apps/cli/` so it matches the existing `bot`,
`web`, and `worker` application split. The intended runnable entrypoint is
`python -m src.apps.cli.guild_sites`.

This keeps operations discoverable inside the current app layout and avoids
adding another top-level script with its own bootstrap logic.

Alternatives considered:

- Standalone root script such as `scripts/guild_sites.py`: faster initially,
  but inconsistent with the repo's package layout and harder to reuse/import in
  tests.
- Fold management into the web app: not appropriate because the user asked for
  an external CLI and the repo has no admin auth model yet.

### 2. Use `argparse`, not a new CLI dependency

The CLI will use Python's standard `argparse` module with subcommands for
`create`, `list`, `show`, `update`, `activate`, `deactivate`, and `delete`.

This keeps the operational surface simple, avoids new packaging or dependency
  work, and matches the repo's preference for minimal additions. The commands
will remain explicit enough for README examples and shell usage.

Alternatives considered:

- Click or Typer: nicer ergonomics, but not justified for one focused admin
  CLI.
- Continue using inline Python snippets only: no longer acceptable because it
  keeps operational knowledge hidden in docs and code.

### 3. Split strict CRUD service functions from the existing provisioning helper

`provision_guild_site()` will remain for compatibility and migration code, but
the CLI will call new explicit service functions:

- `create_guild_site(...)`
- `list_guild_sites(...)`
- `get_guild_site(...)`
- `update_guild_site(...)`
- `set_guild_site_active(...)`
- `delete_guild_site(...)`

These functions will share the existing normalization helpers
(`normalize_slug`, `normalize_subdomain`, `normalize_clan_tag`) but will avoid
the current "find existing by any matching identity and then save" behavior for
create/update commands.

This is the key separation that makes CLI behavior safe and testable.

Alternatives considered:

- Reuse `provision_guild_site()` directly for create and update: too ambiguous
  because "create" can silently become an update.
- Put all CRUD logic inside the CLI module: would duplicate validation and make
  service-level tests weaker.

### 4. Use explicit selectors for non-create operations

Read, update, activation, and deletion commands will target a guild by a single
explicit selector, with support for `--id`, `--slug`, or `--subdomain`. The CLI
must require exactly one selector for single-guild operations.

This avoids accidental cross-updates and makes command intent clear in docs and
tests.

Alternatives considered:

- Positional selector with implicit interpretation: compact, but ambiguous when
  a slug and subdomain could overlap.
- Updating by Discord guild id: useful as a secondary attribute, but not a good
  primary operational selector for website management.

### 5. Keep deletion narrow and confirmed

The delete command will require an explicit confirmation flag and will delete
only the `Guild` row plus guild-owned cascaded records such as clan tags,
participants, and aggregates. Global shared records like `Player` and
`SiteUser` remain because they are not owned solely by one guild.

This matches the current foreign-key model and prevents the CLI from deleting
cross-guild identity data.

Alternatives considered:

- Hard delete with no confirmation: too risky for an operator-facing CLI.
- Deactivate-only with no delete support: does not satisfy the requested CRUD
  scope and still leaves operators doing manual database cleanup.

### 6. Bootstrap shared DB state inside the CLI command path

Each CLI invocation will:

1. Load config through `load_config()`
2. Require `config.mariadb`
3. Initialize the shared database
4. Bootstrap the shared schema
5. Execute the command

This keeps the CLI operational even on a fresh environment and matches the
existing README setup flow.

Alternatives considered:

- Assume the schema already exists: makes the CLI more brittle and less useful
  in local/dev setups.
- Add a separate init command before every operation: unnecessary ceremony for
  this repo.

### 7. Prefer stable human-readable output over a larger output-format feature

The CLI will print stable, concise text for operators and README examples:
single-record commands will show the resulting guild fields, and list commands
will print one guild per line or a compact block with clan tags.

This is enough for immediate operational use without expanding the scope to
multiple renderers or machine-oriented formats.

Alternatives considered:

- Add `--json` everywhere: useful for scripting, but extra scope not required
  by the current request.
- Render rich tables: prettier, but unnecessary complexity for a small admin
  CLI.

## Risks / Trade-offs

- [Create/update behavior may drift from the legacy provisioning helper] →
  Keep shared normalization helpers in one module and test service functions
  directly.
- [Delete could be misunderstood as deleting all related shared identity data]
  → Make deletion semantics explicit in both CLI help and README examples.
- [Operators may target the wrong guild when multiple selectors exist] →
  Require exactly one selector for single-guild commands and echo the resolved
  guild in output.
- [CLI output may later prove too limited for automation] → Keep output
  formatting isolated so JSON can be added later without changing service
  behavior.
- [Schema bootstrap on every invocation adds a little overhead] → Accept the
  small cost in exchange for operational simplicity and safer local usage.

## Migration Plan

1. Add explicit guild-site CRUD service functions alongside the existing
   provisioning helper.
2. Add the CLI app package and `argparse` entrypoint that bootstraps config and
   the shared schema.
3. Add service-level and CLI-level tests covering create, list/show, update,
   activate/deactivate, and confirmed delete behavior.
4. Update the README to replace manual Python provisioning snippets with CLI
   examples and explain deletion vs deactivation.
5. Keep existing migration code and any current callers of
   `provision_guild_site()` unchanged.

Rollback strategy:

- The change is additive to the shared backend and docs.
- If the CLI has issues, operators can temporarily fall back to the existing
  Python helper while the new CLI is fixed.
- No schema change is required, so rollback is limited to removing the CLI and
  service wrapper code.

## Open Questions

None at this stage. The remaining decisions are implementation-level details
that can be resolved in tasks and tests.
