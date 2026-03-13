# Refine Competitive Leaderboard Columns Proposal

## Why

The current public leaderboard table is too generic for a competitive stats
site. Labels such as `Primary Metric` hide what is actually being compared, and
the default table omits several of the stats players need in order to
understand why one player ranks above another.

## What Changes

- Replace the generic public leaderboard table layout with view-specific default
  columns for `Team`, `FFA`, `Overall`, and `Support`.
- Remove the `Primary Metric` placeholder label from public leaderboard tables
  and replace it with explicit stat labels.
- Define a richer default `Team` table that surfaces score, results, support,
  and role signals together.
- Keep `Linked` versus `Observed` visible in the main table, but render it as a
  compact player indicator instead of spending a full standalone column on a
  low-information label.
- Preserve existing sorting behavior, but align the visible columns with the
  primary comparisons players are expected to make in each leaderboard view.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `guild-player-leaderboards`: define explicit default columns and labels for
  each competitive leaderboard view

## Impact

- Affects the public leaderboard rendering in
  `src/apps/web/app.py`
- Affects leaderboard page tests and browser verification coverage
- Does not change score formulas, ingestion logic, or database schema
- Does not require a new dependency
