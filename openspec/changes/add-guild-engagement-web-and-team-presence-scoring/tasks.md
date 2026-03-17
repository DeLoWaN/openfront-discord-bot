# Tasks

## 1. OpenSpec and project scaffolding

- [x] 1.1 Add the frontend workspace and build integration for an in-repo
  `React + Vite` SPA served by the FastAPI app.
- [x] 1.2 Add the frontend dependencies and routing skeleton for home, combos,
  wins, leaderboard, and player profile pages.

## 2. Schema and read-model support

- [x] 2.1 Add additive shared-schema support for combo aggregates, combo
  members, and player badge awards.
- [x] 2.2 Add Peewee models and service-layer helpers for combo aggregates,
  combo members, and badge awards.

## 3. Team scoring and aggregate recomputation

- [x] 3.1 Extend Team difficulty inference to include players-per-team and
  tracked guild presence factors on top of team count.
- [x] 3.2 Update aggregate recomputation to rebuild combo read models for valid
  full-guild `Duos`, `Trios`, and `Quads`.
- [x] 3.3 Add badge-award recomputation that derives `earned_at` from ordered
  observed history and keeps badge thresholds code-defined.
- [x] 3.4 Update scoring explanation payloads and public text to reflect the
  revised Team difficulty factors.

## 4. Backend APIs

- [x] 4.1 Add the guild home API contract for pulse, confirmed combos, pending
  teaser, recent wins preview, and recent badges.
- [x] 4.2 Add combo list/detail APIs for confirmed and pending
  `duo`/`trio`/`quad` views.
- [x] 4.3 Add the recent guild wins API for `Team + FFA` with replay-oriented
  match context.
- [x] 4.4 Extend player profile APIs with badges, partner summaries, combo
  summaries, and player timeseries data.

## 5. Public web experience

- [x] 5.1 Implement the SPA home page with the approved section order and
  empty-state handling.
- [x] 5.2 Implement the dedicated combos experience with confirmed and pending
  views and combo detail rendering.
- [x] 5.3 Implement the recent wins page and profile pages with graphs, badge
  sections, and partner/combo summaries.
- [x] 5.4 Preserve existing public routes while routing them through the new
  frontend experience.

## 6. Verification

- [x] 6.1 Add unit and API tests for revised Team difficulty, combo
  confirmation rules, recent wins, badges, and timeseries payloads.
- [x] 6.2 Add frontend tests for home, combos, wins, and player profile
  screens, including pending and empty states.
- [x] 6.3 Run `basedpyright` for backend typing and validate the public web
  flows with Playwright before closing the change.
