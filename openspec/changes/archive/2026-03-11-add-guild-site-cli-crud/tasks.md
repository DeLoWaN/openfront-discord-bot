# Add Guild Site CLI CRUD Tasks

## 1. Shared guild-site CRUD services

- [x] 1.1 Add explicit shared service helpers for create, list, get, update,
  activate/deactivate, and confirmed delete of website guild records
- [x] 1.2 Reuse existing slug, subdomain, and clan-tag normalization while
  enforcing strict create/update semantics instead of provisioning-style upsert
- [x] 1.3 Define and implement selector handling for single-guild operations
  using exactly one of id, slug, or subdomain
- [x] 1.4 Preserve guild-scoped cascade deletion while keeping unrelated global
  shared records intact

## 2. External CLI application

- [x] 2.1 Add a CLI app package under `src/apps/cli` with a runnable guild-site
  entrypoint
- [x] 2.2 Implement `argparse` subcommands for `create`, `list`, `show`,
  `update`, `activate`, `deactivate`, and `delete`
- [x] 2.3 Bootstrap config loading, MariaDB initialization, and shared schema
  creation inside the CLI command path
- [x] 2.4 Add stable human-readable command output and explicit failure messages
  for invalid selectors, duplicate identities, missing guilds, and unconfirmed
  deletes

## 3. Documentation and tests

- [x] 3.1 Add or update tests for shared guild-site CRUD services, including
  clan tag replacement, activation toggles, selector validation, and confirmed
  delete behavior
- [x] 3.2 Add CLI-level tests that cover the supported subcommands and their
  expected output/error paths
- [x] 3.3 Update `README.md` to replace manual Python provisioning snippets with
  CLI-based create/read/update/deactivate/delete examples and usage guidance
- [x] 3.4 Run the relevant automated tests, Markdown lint for changed docs, and
  OpenSpec validation for the completed change
