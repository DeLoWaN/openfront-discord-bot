# Refine Overall Scoring Copy Visibility Proposal

## Why

The public leaderboard currently risks showing the Overall weighting guidance
outside the `Overall` view, which makes the scoring help feel inaccurate in
mode-specific tables. Visitors should only see the `70% Team` / `30% FFA`
weighting explanation when they are looking at the `Overall` leaderboard it
actually describes.

## What Changes

- Limit the current Overall scoring guidance copy to the `Overall` leaderboard
  view instead of showing it on other leaderboard modes.
- Clarify that leaderboard scoring help is view-specific so Team, FFA, Support,
  and Overall views only render copy relevant to the active mode.
- Preserve the existing Overall explanation text and weighting semantics; this
  change only refines where that message is displayed.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `guild-player-leaderboards`: require the Overall weighting explanation to
  render only on the `Overall` leaderboard view as part of view-specific
  scoring help behavior

## Impact

- Affects public leaderboard rendering in the web app, including the scoring
  help or explanatory message shown above or around the leaderboard table.
- Affects leaderboard UI verification coverage so non-Overall views do not show
  the Overall weighting message.
- Does not change score formulas, API payload semantics, persistence, or
  dependencies.
