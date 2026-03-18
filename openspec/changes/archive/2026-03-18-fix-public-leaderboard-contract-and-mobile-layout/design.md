## Context

The current public leaderboard implementation diverges from the refined web
spec in three places that showed up during Playwright verification:

- the frontend renders collapsed generic columns instead of the required
  Team-, FFA-, and Support-specific labels and metrics
- the FFA leaderboard includes players with no guild-relevant FFA history,
  which makes the view read like a global player index rather than an
  FFA-scoped ranking
- the leaderboard table expands the full page width on small screens instead of
  being contained within the leaderboard region

The fix crosses the service layer, frontend rendering, CSS, and regression
coverage, but it does not require a schema change or a new API surface.

## Goals / Non-Goals

**Goals:**

- Make the public Team, FFA, and Support tables match the current OpenSpec
  contract exactly enough to verify with stable UI tests.
- Limit FFA rows to players with at least one guild-relevant FFA game while
  keeping Team and Support behavior unchanged.
- Keep the leaderboard usable on narrow viewports without introducing
  page-level horizontal overflow.
- Preserve the existing leaderboard routes, sort model, and backend-driven
  scoring semantics.

**Non-Goals:**

- Rework the underlying Team, FFA, or Support scoring formulas.
- Redesign the broader guild-site visual language beyond the responsive fix
  needed for leaderboard tables.
- Introduce new leaderboard views, filters, or APIs.

## Decisions

### Keep the existing leaderboard API shape and restore explicit columns in the UI

The current backend already exposes the metrics needed for the required
columns, so the least risky approach is to restore view-specific column
definitions in the frontend instead of introducing a new contract. This keeps
the change local to rendering and avoids unnecessary API churn.

Alternative considered:
- Expand the API with a fully declarative backend column schema. Rejected
  because it is larger than the verified issue and would duplicate view logic
  already expressed in the product spec.

### Filter FFA rows in the service layer

FFA row eligibility should be enforced before the payload reaches the frontend.
Applying the rule in `guild_stats_api` keeps the view contract consistent
across web rendering, tests, and any other consumer of the public leaderboard
API.

Alternative considered:
- Filter zero-score FFA rows in the React layer. Rejected because it would make
  the browser responsible for spec logic and could leave other consumers with
  inconsistent data.

### Contain table overflow within the leaderboard panel

On narrow screens, the page should remain viewport-bounded even if the table
needs more horizontal space than the screen can provide. The preferred approach
is to wrap the table in a scroll container and ensure parent layout rules do
not force the body wider than the viewport.

Alternatives considered:
- Drop columns on mobile. Rejected because it would conflict with the explicit
  column contract and hide required metrics.
- Convert the table into stacked cards on mobile. Rejected because it is a
  broader redesign and would require a second presentation contract.

## Risks / Trade-offs

- [UI contract drift between spec and component labels] -> Mitigate with
  regression tests that assert the exact public headers for each view.
- [FFA filtering unintentionally removing valid players] -> Mitigate by
  filtering on guild-relevant FFA game count rather than score, so players with
  FFA participation but low or zero score still appear.
- [Responsive fix introducing awkward horizontal scrolling] -> Mitigate by
  constraining scrolling to the table region and preserving the rest of the
  page layout.

## Migration Plan

This change is rollout-safe because it does not change stored data or routes.
Deploy the service/frontend update together, then run the existing web
regression suite and Playwright verification pass against the leaderboard
pages. Rollback is a normal application rollback to the previous release.

## Open Questions

None. The verification findings map directly to existing spec language and do
not require new product decisions.
