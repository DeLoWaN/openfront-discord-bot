# Design

## Context

The current web surface is intentionally minimal: it exposes leaderboard and
player-profile pages backed by stored aggregates, but it does not yet create a
strong return loop for guild members. The product goal has shifted from
publishing cumulative stats to driving repeat visits through comparison,
collection, and visible recent activity.

The current Team scoring model also under-specifies difficulty. It already
values higher team-count lobbies, but it does not distinguish between:

- small-team formats such as `Duos` and `Trios`
- larger teams with more room for support and coordination
- teams with strong tracked guild presence versus teams with only a couple of
  tracked guild members alongside random teammates

This change therefore combines a richer public engagement experience with a
scoring refinement that better matches the guild product philosophy.

## Goals / Non-Goals

**Goals:**

- Replace the minimal guild site with a richer engagement-oriented SPA.
- Add confirmed and pending combo rankings for `Duos`, `Trios`, and `Quads`.
- Add a recent guild wins feed covering `Team` and `FFA`.
- Add player badges, recent badge surfacing, and profile-level graph data.
- Keep the Team score cumulative and contribution-first.
- Refine Team difficulty so it grows with:
  - more teams in the lobby
  - fewer players per team
  - fewer tracked guild-tag teammates on the player's team
- Preserve additive, migration-safe schema changes and stored-aggregate reads.

**Non-Goals:**

- Build a self-serve CMS or badge administration UI.
- Add seasonal ladders or score decay in this change.
- Materialize recent wins or timeseries snapshot tables in v1.
- Replace existing Python service-layer ownership of the scoring logic.
- Require perfect team reconstruction beyond the tracked guild-tag signal.

## Decisions

### 1. Add an integrated SPA instead of extending the inline HTML pages

The existing inline FastAPI HTML is enough for simple leaderboard pages, but
it is the wrong shape for a home dashboard, combo browsing, recent wins feed,
and graph-heavy player profiles. The repo will keep FastAPI as the backend and
add an integrated SPA built with `React`, `React Router`, `TanStack Query`,
and `Recharts`.

This keeps business logic in Python while giving the public site a modern
rendering model with richer navigation and data visualization.

Rejected alternatives:

- keep enhancing server-rendered HTML
  - rejected because the new engagement surfaces would become awkward to
    compose and maintain
- build a fully separate frontend repo
  - rejected because it adds deployment and contract complexity too early

### 2. Keep backend-owned contracts and expose engagement-specific read APIs

The frontend will remain a consumer of backend-owned contracts. FastAPI will
add dedicated endpoints for the home page, combos, recent wins, and player
timeseries, while existing leaderboard/profile APIs stay stable and become
additive.

This keeps ranking logic, badge eligibility, combo confirmation, and scoring
explanation out of the browser.

Rejected alternative:

- compute combo and badge logic in the frontend
  - rejected because it would duplicate business rules and make the UI the
    source of truth

### 3. Materialize combo and badge read models, but not wins or timeseries

Combos and badges are persistent read models:

- combo views need confirmed/pending status, stable roster identity, partner
  lookups, and reusable profile/home ordering
- badge views need durable `earned_at` values so “recent badges” stays correct

Recent wins and timeseries stay read-time queries in v1 because:

- the recent wins page is capped at `20`
- graph windows are intentionally short and profile-scoped
- the observed game tables already contain the timestamps and match metadata

Rejected alternative:

- materialize every engagement surface
  - rejected because it increases schema and recompute complexity without a
    clear v1 need

### 4. Treat confirmed combos as strict full-guild teams only

Combo rankings are only valid for `Duos`, `Trios`, and `Quads`, and only when
the guild-side group exactly fills the team size. The signal is:

- group participants by `(game_id, effective_clan_tag)` for the guild
- infer `players_per_team` from the Team format
- accept the combo only when the grouped guild-tag players equal the inferred
  team size

This intentionally excludes mixed guild/random teams so combo win rate remains
comparable and player-facing.

Rejected alternative:

- allow combos where a random teammate fills the team
  - rejected because it makes the published combo identity misleading

### 5. Rank combos by raw win rate, with confirmation as a separate gate

Confirmed combo podiums use raw win rate. They do not use a hidden combo score.

- confirmed requires `games_together >= 5`
- ranking order is `win_rate desc`, then `games_together desc`, then
  `wins_together desc`, then `last_win_at desc`
- pending combos live on a dedicated page and only receive a teaser on home

This preserves transparency while still blocking tiny samples from the main
podiums.

Rejected alternative:

- hybrid combo score with hidden weighting
  - rejected because the product requirement is explainability

### 6. Refine Team difficulty with multiplicative factors

Team difficulty keeps team count as the primary factor, then multiplies in two
lighter boosts:

```text
team_count_factor =
  1 + 0.25 * log2(max(2, inferred_num_teams))

small_team_factor =
  1 + 0.15 * log2(max(1, 6 / players_per_team))

guild_presence_factor =
  1 + 0.25 * (
    1 - min(players_per_team, tracked_guild_teammates) / players_per_team
  )

difficulty_weight =
  team_count_factor * small_team_factor * guild_presence_factor
```

Interpretation:

- more teams means a harder lobby
- smaller teams are harder because coordination and individual execution matter
  more
- lower tracked guild presence means less organized guild support on that team

If `players_per_team` cannot be inferred, the extra factors collapse to `1.0`
and the model falls back to the existing team-count-only behavior.

Rejected alternatives:

- replace team-count difficulty entirely
  - rejected because team count is already a valid and intuitive difficulty
    signal
- make low guild presence the dominant factor
  - rejected because it should refine difficulty, not overpower lobby shape

### 7. Encode the badge system as code-defined, threshold-stable rules

The badge catalog and thresholds live in code. v1 uses a mixed model:

- milestone badges use `Bronze / Silver / Gold`
- performance, role, combo, and map badges are single unlocks

Badge award calculation replays the player's observed history chronologically
to find the first qualifying timestamp, which is stored as `earned_at`.

This makes recent badge feeds historically accurate after backfills and keeps
the badge system stable without introducing admin tooling.

Rejected alternative:

- configurable badge definitions in the database
  - rejected because it adds operational complexity before the first real
    catalog is validated

## Risks / Trade-offs

- [Frontend scope grows materially] → keep FastAPI and service ownership in
  place and confine the new stack to the public site
- [Combo views may have sparse confirmed data in some guilds] → support
  explicit pending states and empty-state messaging
- [Tracked guild-tag teammates are an approximation of guild presence] →
  document that signal clearly and do not mix in heuristics or linked-only
  identity assumptions
- [Badge thresholds may need tuning after real usage] → keep the definitions in
  one code-owned catalog and validate against the checked-in `UN` fixture
- [Recent wins and timeseries read queries may grow more expensive later] →
  keep the v1 limits small and leave room for later materialization if needed

## Migration Plan

1. Add the new OpenSpec spec deltas for the web experience and scoring model.
2. Add additive schema support for combo aggregates, combo members, and badge
   awards.
3. Extend aggregate recomputation so affected guilds rebuild combo and badge
   read models after observation refresh.
4. Add the new backend APIs and scoring explanation updates.
5. Add the SPA and migrate the public site rendering to consume those APIs.
6. Recompute aggregates from the existing observed data.
7. Validate the public flows with Playwright and keep rollback simple by
   reverting to the prior public rendering and scorer if needed.

## Open Questions

- None. This change intentionally fixes the frontend stack, combo rules, and
  Team difficulty formula so the implementation can proceed without further
  design decisions.
