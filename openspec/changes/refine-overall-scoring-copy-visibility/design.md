# Refine Overall Scoring Copy Visibility Design

## Context

The public leaderboard page currently renders two layers of scoring copy: a
view-specific summary and a second sentence that always describes Overall score
weighting. That second sentence is sourced from the scoring response and
rendered unconditionally in the leaderboard page, so Team, FFA, and Support
views can show Overall-specific guidance that does not match the active table.

This change is intentionally narrow. It refines leaderboard copy visibility
without changing score formulas, stored aggregates, or the leaderboard API
shape beyond what is necessary to keep the rendered help aligned with the
active view.

## Goals / Non-Goals

**Goals:**

- Ensure the `70% Team` / `30% FFA` weighting message is shown only for the
  `Overall` leaderboard view.
- Keep scoring help aligned with the active leaderboard so non-Overall pages do
  not present misleading Overall guidance.
- Cover the behavior with leaderboard page tests and browser verification.

**Non-Goals:**

- Change Team, FFA, Overall, or Support scoring formulas.
- Redesign the leaderboard layout or rewrite the broader scoring-help copy.
- Introduce new persistence, schema, or dependency changes.

## Decisions

### 1. Treat the Overall weighting sentence as Overall-only help

The existing short summary for each view remains the default explanatory text.
The additional weighting sentence is specific to Overall normalization and
fallback behavior, so the page should render it only when the active view is
`overall`.

Alternatives considered:

- Leave the copy global and rely on users to infer it only applies to Overall:
  rejected because it contradicts the active Team, FFA, and Support views.
- Replace all scoring help with one generic paragraph: rejected because it
  removes useful mode-specific guidance.

### 2. Fix the visibility at the leaderboard rendering boundary

The minimal implementation is to keep the current scoring-response content but
make leaderboard rendering conditional on the resolved view. That keeps the
change local to the public leaderboard path and avoids unnecessary contract
changes for consumers that already receive view-specific summaries.

Alternatives considered:

- Remove the Overall-specific field from the scoring response entirely: viable,
  but broader than needed for this bug.
- Add a new multi-field explanation model for every view: rejected because the
  request only needs conditional visibility for one existing sentence.

### 3. Lock the contract with absence checks on non-Overall views

Tests should assert both presence and absence. The implementation needs proof
that the Overall weighting copy appears on the `Overall` leaderboard and does
not appear on `Team`, `FFA`, or `Support`.

Alternatives considered:

- Test only the `Overall` view: rejected because it would miss regressions
  where the copy still leaks into other views.

## Risks / Trade-offs

- [The page could still drift if future copy is added without view checks] ->
  Keep tests explicit about which views may render the Overall weighting
  message.
- [A narrow render-layer fix keeps an Overall-specific field in the scoring
  response] -> Accept the small asymmetry because it minimizes churn and fits
  the requested change scope.

## Migration Plan

No data or deployment migration is required. The change is a web rendering
refinement and can ship with the updated tests.

## Open Questions

None.
