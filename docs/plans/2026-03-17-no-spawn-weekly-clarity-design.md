# No-Spawn Scoring And Weekly Clarity Design

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:writing-plans`
> before implementation, then use
> `superpowers:test-driven-development` for code changes.

**Goal:** Make `no-spawn` players count as played games but earn zero
score, and make weekly/home competitive views readable and semantically
trustworthy.

**Context:** Playwright review exposed a product inconsistency: the
roster pipeline already treats ambiguous `no-spawn` participants
conservatively, but the daily/weekly/read-model paths still award them
score and surface them in competitive UI. The same review also showed
that `Support Spotlight` pads with zero-value rows and the weekly
six-week trend is not readable as a competitive feature.

## Decisions

- A `no-spawn` participant counts as a played game and can still count
  as a win for ratio purposes.
- A `no-spawn` participant earns zero `team_presence_score`, zero
  `team_result_score`, and zero `support_bonus`.
- This rule must be centralized and reused by ingestion-derived read
  models so score-based views stay consistent.
- `Support Spotlight` must filter out rows with `support_bonus <= 0`
  instead of padding the top 3 with noise.
- Weekly trends need both:
  - a compact matrix/table with labeled weeks on the weekly page
  - a real chart for player-specific weekly contribution

## Backend design

- Add a shared helper in the score pipeline to detect `no-spawn` from
  the same strong signal used in roster inference:
  - zero gold
  - zero attacks / conquests
  - zero donation / support activity
  - zero meaningful unit/economy progression
- Use that helper in read-model refresh code so
  `GuildPlayerDailySnapshot` and `GuildWeeklyPlayerScore`:
  - increment `games`
  - increment `wins` if appropriate
  - add zero score contribution for `team` and `support`
- Keep recent-game participant exposure unchanged for now; the lot fixes
  ranking semantics first.
- Filter `support_spotlight` in the home payload to positive support rows only.

## Frontend design

- Weekly page:
  - replace raw unlabeled history chips with a labeled week matrix
  - add a multi-series trend chart for the current top players across returned weeks
- Player page:
  - keep the existing weekly contribution chart
  - no structural redesign needed for this lot if the backend values
    become trustworthy
- Home:
  - `Support Spotlight` may display fewer than 3 names when only one or
    two players have positive support

## Validation

- Backend tests must prove:
  - `no-spawn` still increments `games`
  - `no-spawn` yields zero `team` and `support` weekly/daily score
  - `Support Spotlight` excludes zero-value rows
- Frontend tests must prove:
  - weekly page renders labeled week columns / trend chart instead of raw chips
- Final validation must include Playwright review of text, ranking
  semantics, and visual readability, not just console status.
