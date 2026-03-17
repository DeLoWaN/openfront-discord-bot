# No-Spawn Scoring And Weekly Clarity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Make `no-spawn` players count as games with zero score, remove
zero-value support noise, and redesign weekly competitive views so the
numbers are readable.

**Architecture:** Centralize `no-spawn` score gating in shared score
helpers, then reuse it in derived read models and home payload
assembly. Update weekly UI to consume the same API data with explicit
week labels and charts instead of unlabeled raw values.

**Tech Stack:** Python, FastAPI, Peewee, React, TanStack Query,
Recharts, pytest, Vitest, Playwright MCP

---

## Task 1: Add failing backend tests for no-spawn score gating

**Files:**

- Modify: `/Users/damien/git_perso/openfront-discord-bot/tests/test_guild_refinements_api.py`
- Modify: `/Users/damien/git_perso/openfront-discord-bot/tests/test_weekly_rankings.py`

### Step 1: Write the failing tests

- Assert that a `no-spawn` tracked player still appears in weekly rows
  only if they have non-zero score contributions from other games.
- Assert that in the seeded overflow case:
  - `Ghost` has `games > 0`
  - `Ghost` has `score == 0` for weekly `team`
  - `Ghost` has `support == 0`
- Assert home `support_spotlight` does not contain zero-value rows.

### Step 2: Run tests to verify failure

Run:

```bash
pytest tests/test_guild_refinements_api.py tests/test_weekly_rankings.py -q
```

Expected: FAIL on the new assertions because current read models still
award score or still expose zero-support rows.

### Step 3: Write minimal implementation

- Add shared `no-spawn` helper usage in read-model refresh paths.
- Filter `support_spotlight` to positive support values.

### Step 4: Run tests to verify they pass

Run:

```bash
pytest tests/test_guild_refinements_api.py tests/test_weekly_rankings.py -q
```

Expected: PASS

## Task 2: Add failing frontend tests for readable weekly trends

**Files:**

- Modify: `/Users/damien/git_perso/openfront-discord-bot/src/apps/web/frontend/src/test/app.test.jsx`

### Step 1: Write the failing frontend tests

- Assert weekly page shows explicit week labels from the payload.
- Assert the page no longer renders the unlabeled raw chip list behavior.
- Assert a chart container for weekly trends is present.

### Step 2: Run test to verify failure

Run:

```bash
npm run test:web -- src/apps/web/frontend/src/test/app.test.jsx
```

Expected: FAIL because current weekly page still renders raw history chips.

### Step 3: Write minimal frontend implementation

- Replace the weekly history chip block with:
  - a compact labeled matrix/table
  - a trend chart using returned week labels

### Step 4: Run test to verify it passes

Run:

```bash
npm run test:web -- src/apps/web/frontend/src/test/app.test.jsx
```

Expected: PASS

## Task 3: Verify integrated behavior

**Files:**

- Verify existing touched files only

### Step 1: Run targeted backend and frontend verification

Run:

```bash
pytest tests/test_guild_refinements_api.py tests/test_weekly_rankings.py -q
npm run test:web
npm run build
```

### Step 2: Run product-level Playwright validation

- Start a local seeded app instance
- Navigate through `/`, `/players/ace`, `/rosters/duo`, `/games`, `/weekly`
- Confirm:
  - no-spawn player no longer contaminates score-driven rankings
  - support spotlight does not pad with zeros
  - weekly trend is readable with labeled weeks and a visual chart

### Step 3: Document actual results

- Report the verification evidence precisely, including any remaining gaps.
