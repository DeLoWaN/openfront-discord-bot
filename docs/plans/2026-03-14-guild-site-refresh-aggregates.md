# Guild Site Refresh Aggregates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> to implement this plan task-by-task.

**Goal:** Add a `guild-sites refresh-aggregates` command that rebuilds one
guild's stored leaderboard aggregates from existing raw observations.

**Architecture:** Extend the existing `guild-sites` CLI with one new subcommand
that reuses the current guild selector pattern. The command should resolve a
guild, call `refresh_guild_player_aggregates`, and print a concise summary so
operators can force a recompute without running an ad-hoc Python snippet.

**Tech Stack:** Python, argparse, Peewee, pytest

---

## Task 1: Add the failing CLI test

**Files:**

- Modify: `tests/test_guild_site_cli.py`
- Test: `tests/test_guild_site_cli.py`

### Step 1: Write the failing test

Add a CLI test that:

- creates a guild through `guild_sites_cli.main(["create", ...])`
- inserts one `ObservedGame` and one `GameParticipant` row for that guild
- runs `guild_sites_cli.main(["refresh-aggregates", "--slug", "<slug>"])`
- asserts the command succeeds, prints a refresh summary, and leaves one
  `GuildPlayerAggregate` row

### Step 2: Run test to verify it fails

Run: `pytest -q tests/test_guild_site_cli.py -k refresh_aggregates`

Expected: FAIL because `refresh-aggregates` is not a recognized command yet.

## Task 2: Implement the CLI command

**Files:**

- Modify: `src/apps/cli/guild_sites.py`

### Step 1: Add parser support

Add a `refresh-aggregates` subparser and reuse `_add_selector_arguments(...)`.

### Step 2: Add minimal implementation

Resolve the guild with the existing selector flow, call
`refresh_guild_player_aggregates(guild)`, and print a concise line containing
the guild slug and refreshed player count.

### Step 3: Run the focused CLI test

Run: `pytest -q tests/test_guild_site_cli.py -k refresh_aggregates`

Expected: PASS.

## Task 3: Document and verify

**Files:**

- Modify: `README.md`

### Step 1: Add one usage example

Document `./guild-sites refresh-aggregates --slug <slug>` in the
`guild-sites` CLI section.

### Step 2: Run targeted verification

Run: `pytest -q tests/test_guild_site_cli.py`

Expected: PASS.

### Step 3: Run full verification

Run: `pytest -q`

Expected: PASS.
