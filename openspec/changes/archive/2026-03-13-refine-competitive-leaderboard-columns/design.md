# Refine Competitive Leaderboard Columns Design

## Context

The competitive leaderboard change introduced the correct views and backend
metrics, but the current public table still uses a generic layout:
`Player`, `Score`, `Primary Metric`, `Games`, `State`. That layout was useful
as a temporary scaffold, but it is not specific enough for a competitive site.
It hides which stat is being shown in each view, wastes space on a vague
header, and forces users to open profiles before they can see the most relevant
comparisons.

This follow-up change stays presentation-focused. The backend already exposes
the metrics needed for richer public tables, so the work should refine the
visible default columns without reopening scoring, ingestion, or schema work.

## Goals / Non-Goals

**Goals:**

- define explicit default columns for `Team`, `FFA`, `Overall`, and `Support`
  leaderboard views
- remove the `Primary Metric` placeholder from public tables
- surface the most useful comparison stats directly in the default table,
  especially for the primary `Team` view
- keep `Linked` versus `Observed` visible without spending a dedicated low-value
  column on it
- preserve existing sort behavior while making the visible headers match the
  numbers shown

**Non-Goals:**

- changing Team, FFA, Overall, or Support score formulas
- adding new aggregate fields or database schema
- redesigning the whole website look and feel
- defining a final responsive design system for mobile and desktop
- introducing pair-level support or advanced role analytics

## Decisions

### 1. Use view-specific default columns instead of one generic table shape

Each leaderboard view will define its own visible columns.

- `Team`: `Player`, `Team Score`, `Wins`, `Win Rate`, `Games`,
  `Troops Donated`, `Support Bonus`, `Role`
- `FFA`: `Player`, `FFA Score`, `Wins`, `Win Rate`, `Games`
- `Overall`: `Player`, `Overall Score`, `Team Score`, `FFA Score`,
  `Team Games`, `FFA Games`
- `Support`: `Player`, `Troops Donated`, `Gold Donated`,
  `Donation Actions`, `Support Bonus`, `Team Games`, `Role`

This keeps the default table aligned with what players actually want to compare
in each mode. `Team` becomes the richest view because it is the primary guild
surface.

Alternatives considered:

- Keep one generic table shape across all views: simpler implementation, but
  not informative enough.
- Expose every sortable metric by default: too wide and too noisy for the first
  visible table.

### 2. Replace the standalone state column with an inline player indicator

`Linked` versus `Observed` is still useful, but it does not deserve a full
table column once the main table becomes denser. The state should be rendered
inside the `Player` cell as a compact badge or inline label.

This frees one column slot for a more meaningful stat without removing identity
context from the leaderboard.

Alternatives considered:

- Keep `State` as a standalone column: easy, but low-information and wasteful.
- Remove the state indicator entirely: too much loss of player identity
  context.

### 3. Keep advanced sorts broader than visible columns

The visible columns define the default comparison surface, but they should not
limit the supported sort fields already exposed by the backend. Existing sort
options can remain broader than the table headers.

This keeps the contract stable while allowing the default table to stay focused
and readable.

Alternatives considered:

- Restrict sort options to visible columns only: simpler mental model, but
  unnecessary loss of flexibility.

### 4. Keep the change frontend-facing and contract-light

The first version of this change should avoid adding new backend metadata for
column layout. The public site can introduce a single per-view mapping in the
web layer using fields already present in the leaderboard payloads.

This keeps the change small and avoids reopening the API contract unless the
team later decides to move column metadata server-side.

Alternatives considered:

- Add API-provided column configuration immediately: more decoupled, but a
  larger follow-up than needed for the current problem.

## Risks / Trade-offs

- [More visible columns can make tables feel busy] -> Keep the default set
  focused per view and avoid dumping every available metric into the main table.
- [Inline state badges may be easier to miss than a dedicated column] ->
  render them consistently next to the player name.
- [Visible columns and supported sorts may drift over time] -> centralize the
  per-view column mapping in one web-layer definition and test it explicitly.
- [Overall view can still look dense] -> keep it centered on score composition
  rather than role or support details.

## Migration Plan

1. Update the OpenSpec requirement for the public leaderboard table shape.
2. Update the server-rendered leaderboard template to use per-view headers and
   per-view row values.
3. Render `Linked` versus `Observed` inline in the player cell.
4. Extend web tests to assert the new headers and visible values.
5. Verify with browser checks that the new tables read correctly in `Team`,
   `FFA`, `Overall`, and `Support`.

## Open Questions

- Should `Win Rate` be rendered as a percentage string or kept as a decimal in
  the visible table?
- Should the `Support Bonus` column remain visible in `Team` on smaller
  screens, or collapse behind a narrower mobile layout later?
