# Rework Guild Contribution Scoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL:
> Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Replace the normalized Team/FFA/Overall scorer with the approved
contribution-first Team and FFA model, remove public `overall`, keep visible
support bonus plus support leaderboard, and expose recent-activity metadata
beside cumulative scores.

**Architecture:** Rebuild `GuildPlayerAggregate` from persisted
`ObservedGame` and `GameParticipant` rows using positive cumulative formulas
for Team and FFA, persist separate recent-activity counters, then simplify the
stats API and public site to Team/FFA/Support only. Keep the raw observation
tables and UN fixture workflow intact so the change is a recompute plus
contract update, not a new ingestion pipeline.

**Tech Stack:** Python, Peewee, FastAPI, pytest, OpenSpec, SQLite/MariaDB
shared schema

---

## Task 1: Lock the new public contract with failing tests

### Task 1 Files

- Modify: `tests/test_guild_stats_api.py`
- Modify: `tests/test_web_leaderboard.py`
- Modify: `tests/test_web_guild_sites.py`
- Modify: `tests/test_competitive_leaderboards.py`

### Step 1: Write the failing tests

- Remove `overall` expectations from leaderboard, scoring, and player-profile
  tests.
- Add assertions for Team / FFA / Support-only navigation and API responses.
- Add assertions for recent-activity fields such as
  `team_recent_game_count_30d` and `ffa_recent_game_count_30d`.

### Step 2: Run tests to verify they fail

Run:

```bash
pytest -q \
  tests/test_guild_stats_api.py \
  tests/test_web_leaderboard.py \
  tests/test_web_guild_sites.py \
  tests/test_competitive_leaderboards.py
```

Expected: failures caused by the old `overall` contract and missing
recent-activity fields.

### Step 3: Implement the minimal API/web contract changes

- Update the supported view list and view-specific columns.
- Remove `overall` sections from response payloads and rendered HTML.
- Add recent-activity fields to the API row payloads and surface them in the
  tables and profile.

### Step 4: Re-run the same tests

Run:

```bash
pytest -q \
  tests/test_guild_stats_api.py \
  tests/test_web_leaderboard.py \
  tests/test_web_guild_sites.py \
  tests/test_competitive_leaderboards.py
```

Expected: contract tests pass or fail only on scorer details not yet
implemented.

## Task 2: Replace aggregate scoring with the positive cumulative model

### Task 2 Files

- Modify: `tests/test_ingestion.py`
- Modify: `src/services/openfront_ingestion.py`
- Modify: `src/data/shared/models.py`
- Modify: `src/data/shared/schema.py`

### Step 1: Write the failing scorer tests

- Add unit tests for Team difficulty growth beyond 10 teams.
- Add tests proving losses keep positive participation value instead of
  subtracting.
- Add tests for light win-rate multiplier behavior and additive support bonus.
- Add tests for persisted recent-activity counters.

### Step 2: Run scorer tests to verify they fail

Run:

`pytest -q tests/test_ingestion.py`

Expected: failures because the old normalized / subtractive scorer is still
active.

### Step 3: Implement the new scorer minimally

- Remove rank-normalized Team/FFA helpers no longer needed.
- Compute Team score from participation points, win bonus, light win-rate
  multiplier, and capped additive support bonus.
- Compute FFA score from participation points, win bonus, and light win-rate
  multiplier.
- Persist `team_recent_game_count_30d` and `ffa_recent_game_count_30d`.
- Stop computing public `overall`.

### Step 4: Re-run scorer tests

Run:

`pytest -q tests/test_ingestion.py`

Expected: scorer tests pass.

## Task 3: Recalibrate the UN regression around the new philosophy

### Task 3 Files

- Modify: `tests/test_un_guild_regression.py`
- Modify: `tests/fixtures/un_guild_snapshot.json`

### Step 1: Write the failing regression expectations

- Remove `overall` checks.
- Assert high-participation anchors remain near the top of Team.
- Assert small high-win-rate samples do not dominate.
- Keep support-order assertions based on visible `support_bonus`.

### Step 2: Run the regression test to verify it fails

Run:

`pytest -q tests/test_un_guild_regression.py`

Expected: failures while the scorer or snapshot still reflect the old
normalized model.

### Step 3: Refresh the snapshot from the new recompute

- Rebuild aggregates from the checked-in UN fixture.
- Inspect the resulting ordering and update `un_guild_snapshot.json` with the
  new anchors.

### Step 4: Re-run the regression

Run:

`pytest -q tests/test_un_guild_regression.py`

Expected: regression passes against the revised anchors.

## Task 4: Update OpenSpec artifacts and verification

### Task 4 Files

- Modify: `openspec/changes/rework-guild-contribution-scoring/tasks.md`
- Optional if implementation reveals drift:
  `openspec/changes/rework-guild-contribution-scoring/design.md`

### Step 1: Mark completed tasks

- Flip the completed checklist items in `tasks.md` once code and tests are
  done.

### Step 2: Run focused and full verification

Run:

```bash
pytest -q \
  tests/test_guild_stats_api.py \
  tests/test_web_leaderboard.py \
  tests/test_web_guild_sites.py \
  tests/test_competitive_leaderboards.py \
  tests/test_ingestion.py \
  tests/test_un_guild_regression.py

pytest -q

openspec validate rework-guild-contribution-scoring --type change --strict

markdownlint-cli2 \
  docs/plans/2026-03-15-rework-guild-contribution-scoring.md \
  openspec/changes/rework-guild-contribution-scoring/*.md \
  openspec/changes/rework-guild-contribution-scoring/specs/**/*.md

git diff --check
```

### Step 3: Only then report completion

- Summarize the contract changes, the new scoring shape, and any
  migration/recompute step the user still needs to run locally.
