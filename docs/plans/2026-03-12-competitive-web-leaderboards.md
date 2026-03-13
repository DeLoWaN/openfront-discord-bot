# Competitive Web Leaderboards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task.

**Goal:** Build donation-aware competitive leaderboards with separate Team,
FFA, Overall, and Support views, exposed through a backend API and rendered by
the guild website without embedding score logic in the frontend.

**Architecture:** Extend the shared MariaDB/SQLite-compatible schema
additively, enrich ingestion with donor-centric turn metrics for guild-relevant
Team games, materialize richer guild aggregates, and expose them through
guild-scoped JSON endpoints. Keep the first frontend pass thin and functional:
HTML shells plus backend-driven data and sorting, with visual redesign deferred
to a later change.

**Tech Stack:** Python, FastAPI, Peewee, pytest, markdownlint-cli2, OpenFront
public API

---

### Task 1: Add regression tests for richer ingestion and scoring

**Files:**

- Modify:
  `tests/test_ingestion.py`
- Create:
  `tests/test_guild_stats_api.py`
- Create:
  `tests/test_competitive_leaderboards.py`

**Step 1: Write the failing tests**

- Add an ingestion test that proves Team game ingestion stores donation and
  attack metrics from turnful payloads while leaving FFA support metrics empty.
- Add leaderboard-scoring tests that prove Team, FFA, Overall, and Support
  rows are computed separately from stored aggregates.
- Add API tests that prove the backend returns JSON for leaderboard views and
  scoring explanation data.

**Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_ingestion.py tests/test_competitive_leaderboards.py \
  tests/test_guild_stats_api.py -q
```

Expected: failures for missing schema fields, services, or endpoints.

**Step 3: Write the minimal implementation**

- Extend models and services only enough to satisfy the first failing tests.

**Step 4: Run tests to verify they pass**

Run:

```bash
pytest tests/test_ingestion.py tests/test_competitive_leaderboards.py \
  tests/test_guild_stats_api.py -q
```

Expected: all new tests pass.

### Task 2: Extend schema and caching for support-aware Team games

**Files:**

- Modify:
  `src/data/shared/models.py`
- Modify:
  `src/data/shared/schema.py`
- Modify:
  `src/core/openfront.py`
- Modify:
  `src/services/historical_backfill.py`

**Step 1: Write the failing tests**

- Add tests that require additive schema columns for Team/FFA/support
  aggregates and turn-payload caching.

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_ingestion.py::test_ingest_game_payload_persists_guild_relevant_participants_and_aggregates -q
```

Expected: failure due to missing columns or unsupported payload handling.

**Step 3: Write minimal implementation**

- Add additive fields for donor-centric support metrics and mode-specific
  aggregate values.
- Add additive migration helpers for the new columns.
- Add an OpenFront client method or parameter for fetching turnful game detail.
- Cache turnful payloads only when Team support metrics are needed.

**Step 4: Run tests to verify it passes**

Run:

```bash
pytest tests/test_ingestion.py -q
```

Expected: ingestion and cache tests pass.

### Task 3: Implement competitive aggregate refresh and scoring services

**Files:**

- Modify:
  `src/services/openfront_ingestion.py`
- Modify:
  `src/services/guild_leaderboard.py`
- Create:
  `src/services/guild_stats_api.py`

**Step 1: Write the failing tests**

- Add tests for Team/FFA/Overall/Support row generation, score explanation
  output, and support bonus behavior.

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_competitive_leaderboards.py -q
```

Expected: failure because the scoring service does not exist or returns wrong
values.

**Step 3: Write minimal implementation**

- Derive donor-centric support metrics from Team turns.
- Refresh guild aggregates with Team, FFA, Overall, and Support fields.
- Implement a service layer that returns leaderboard rows and scoring
  explanation text without exposing raw formulas.

**Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_competitive_leaderboards.py -q
```

Expected: scoring and explanation tests pass.

### Task 4: Add API endpoints and functional frontend integration

**Files:**

- Modify:
  `src/apps/web/app.py`
- Modify:
  `tests/test_web_leaderboard.py`
- Modify:
  `tests/test_auth_and_linking.py`
- Modify:
  `tests/test_web_guild_sites.py`
- Modify:
  `tests/test_guild_stats_api.py`

**Step 1: Write the failing tests**

- Add tests for `/api/leaderboards/{view}`-style endpoints, scoring explanation
  output, and basic leaderboard-page navigation for Team/FFA/Overall/Support.

**Step 2: Run test to verify it fails**

Run:

```bash
pytest tests/test_web_leaderboard.py tests/test_auth_and_linking.py \
  tests/test_web_guild_sites.py tests/test_guild_stats_api.py -q
```

Expected: failure because the new endpoints and navigation do not exist.

**Step 3: Write minimal implementation**

- Add guild-scoped JSON endpoints for leaderboards, player profiles, and score
  explanation data.
- Update the HTML shell to expose Team/FFA/Overall/Support navigation and
  render backend-driven data in a functional first pass.

**Step 4: Run test to verify it passes**

Run:

```bash
pytest tests/test_web_leaderboard.py tests/test_auth_and_linking.py \
  tests/test_web_guild_sites.py tests/test_guild_stats_api.py -q
```

Expected: the web/API tests pass.

### Task 5: Verify, update tasks, and validate the change

**Files:**

- Modify:
  `openspec/changes/add-competitive-web-leaderboards/tasks.md`

**Step 1: Run the focused verification suite**

Run:

```bash
pytest tests/test_ingestion.py tests/test_competitive_leaderboards.py \
  tests/test_guild_stats_api.py tests/test_web_leaderboard.py \
  tests/test_auth_and_linking.py tests/test_web_guild_sites.py -q
```

Expected: all targeted tests pass.

**Step 2: Run OpenSpec validation**

Run:

```bash
openspec validate add-competitive-web-leaderboards --type change --strict
```

Expected: validation succeeds.

**Step 3: Mark completed OpenSpec tasks**

- Update the relevant checkboxes in
  `openspec/changes/add-competitive-web-leaderboards/tasks.md`.

**Step 4: Re-run markdown lint if the task file changed**

Run:

```bash
markdownlint-cli2 openspec/changes/add-competitive-web-leaderboards/tasks.md \
  docs/plans/2026-03-12-competitive-web-leaderboards.md
```

Expected: zero errors.
