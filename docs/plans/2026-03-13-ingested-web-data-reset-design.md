# Ingested Web Data Reset Design

## Summary

Add a safe operational reset for shared web-ingestion data so the site can be
reseeded from the OpenFront API without deleting guild configuration or linked
account records.

## Scope

The reset must delete only ingestion-derived shared data:

- `backfill_runs`
- `backfill_cursors`
- `backfill_games`
- `cached_openfront_games`
- `observed_games`
- `game_participants`
- `guild_player_aggregates`

The reset must preserve:

- `guilds`
- `guild_clan_tags`
- `site_users`
- `players`
- `player_aliases`
- `player_links`

## Operational Shape

Expose the reset through the historical backfill operational surface rather
than inventing a separate tool. Add a backend service function that performs
the deletion in a transaction and returns deleted row counts. Wrap that
function in a new CLI command with explicit confirmation.

## Safety Rules

- Require `--confirm` on the CLI.
- Delete child tables before parent tables to avoid foreign key issues across
  SQLite and MariaDB.
- Return a summary so operators can confirm what was wiped.

## Validation

- Add a service-level regression test that proves ingestion tables are cleared
  while guild configuration and links remain.
- Add a CLI regression test that proves the command requires confirmation and
  prints a useful summary.
