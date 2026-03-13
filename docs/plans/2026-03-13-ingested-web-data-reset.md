# Ingested Web Data Reset Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task.

**Goal:** Add a safe command that wipes shared web-ingestion data so the site
can be repopulated from the OpenFront API without deleting guild config or
linked players.

**Architecture:** Implement a small backend reset service in the shared
historical-backfill area, then expose it through the existing
`historical-backfill` CLI with explicit confirmation. Keep the behavior narrow:
delete ingestion/cache/backfill tables only, preserve site configuration and
identity tables.

**Tech Stack:** Python, Peewee, argparse, pytest, markdownlint-cli2

---

## Task 1: Add failing regression tests

**Files:**

- Modify:
  `tests/test_historical_backfill.py`
- Modify:
  `tests/test_historical_backfill_cli.py`

### Step 1: Write the failing tests

- Add a service test that seeds shared ingestion rows plus guild/link records,
  runs the reset, and asserts only ingestion rows are deleted.
- Add a CLI test that proves `reset-data` requires `--confirm` and prints a
  deletion summary when confirmed.

### Step 2: Run tests to verify they fail

Run:

```bash
pytest tests/test_historical_backfill.py tests/test_historical_backfill_cli.py -q
```

Expected: failures because the reset service and CLI command do not exist yet.

### Step 3: Write the minimal implementation

- Add the reset service.
- Add the CLI subcommand and summary output.

### Step 4: Run tests to verify they pass

Run:

```bash
pytest tests/test_historical_backfill.py tests/test_historical_backfill_cli.py -q
```

Expected: all reset-related tests pass.

## Task 2: Update docs and execute the reset

**Files:**

- Modify:
  `README.md`

### Step 1: Document the command

- Add the new reset command to the historical backfill operational section.

### Step 2: Verify docs and focused tests

Run:

```bash
markdownlint-cli2 README.md \
  docs/plans/2026-03-13-ingested-web-data-reset-design.md \
  docs/plans/2026-03-13-ingested-web-data-reset.md
pytest tests/test_historical_backfill.py tests/test_historical_backfill_cli.py -q
```

Expected: docs lint and focused tests pass.

### Step 3: Execute the reset against the configured database

Run:

```bash
./historical-backfill reset-data --confirm
```

Expected: a summary of deleted ingestion rows, with guild config and linked
records untouched.
