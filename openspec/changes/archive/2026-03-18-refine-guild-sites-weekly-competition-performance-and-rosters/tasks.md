# Tasks

## 1. OpenSpec and contracts

- [x] 1.1 Add the new change artifacts and spec deltas for weekly rankings,
  roster UX refinement, recent games, and performance-oriented read models.

## 2. Schema and aggregate refresh

- [x] 2.1 Add additive shared-schema support for daily snapshots, daily
  benchmarks, weekly player scores, and recent game results.
- [x] 2.2 Add Peewee models and refresh helpers for the new read models.
- [x] 2.3 Rebuild roster aggregates from history during aggregate refresh and
  support exact plus no-spawn-filtered roster inference.

## 3. Backend APIs and scoring views

- [x] 3.1 Extend home, leaderboard, player, recent-games, and roster APIs with
  the refined contracts.
- [x] 3.2 Add the weekly rankings API and expose six-week player trend data.
- [x] 3.3 Replace hash-style replay links with OpenFront `0.30` worker-path
  links and expose deterministic map thumbnail URLs when available.

## 4. Public web experience

- [x] 4.1 Rename public `Combos` UX to `Rosters` while keeping compatibility
  aliases.
- [x] 4.2 Refine the home page, leaderboard, player page, and recent-games
  page with clearer labels, sortable tables, richer cards, and weekly widgets.
- [x] 4.3 Add the dedicated weekly page and player weekly trend charts.

## 5. Verification

- [x] 5.1 Add unit and API tests for weekly windows, movers, replay links,
  roster inference, and richer recent-games/profile contracts.
- [x] 5.2 Add frontend tests for sortable tables, locked badges, weekly views,
  and recent-games card/list toggles.
- [x] 5.3 Validate the refined public flows with Playwright on fixture data and
  a real-like guild dataset.
