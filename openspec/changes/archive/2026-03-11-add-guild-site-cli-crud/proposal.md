# Change: Add guild site CLI CRUD

## Why

Guild site provisioning currently exists only as an ad hoc Python snippet, which
makes routine website operations error-prone and hard to repeat. The project
needs a supported external CLI now so guild records can be created, inspected,
updated, deactivated, and deleted without editing code or issuing raw database
queries.

## What Changes

- Add an external CLI for shared website guild management.
- Support create, list/read, update, deactivate, and delete operations for
  guild site records backed by the shared MariaDB schema.
- Reuse the existing guild-site service rules for slug, subdomain, active
  state, Discord guild identity, and clan tag handling.
- Define deletion semantics for website guilds so operators can intentionally
  remove a guild site instead of only marking it inactive.
- Update the README to document the supported CLI workflow and replace the
  current manual provisioning guidance.

## Capabilities

### New Capabilities

- `guild-site-cli`: Manage website guild records from an external CLI, including
  create, inspect/list, update, deactivate, and delete flows.

### Modified Capabilities

None.

## Impact

- Affected code: shared guild-site services, a new CLI entrypoint/module, and
  supporting tests for shared website guild management.
- Affected docs: [`README.md`](/Users/damien/git_perso/openfront-discord-bot/README.md)
  should move from manual Python provisioning snippets to CLI-based operations.
- Affected systems: the shared MariaDB-backed website path only; this change
  does not redefine the legacy Discord bot guild removal flow.
