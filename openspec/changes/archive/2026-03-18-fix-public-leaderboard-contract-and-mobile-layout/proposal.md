## Why

The public leaderboard experience is out of sync with the current OpenSpec
contract in ways that are visible to users. The shipped tables collapse
required view-specific columns, the FFA view includes players with no
guild-relevant FFA participation, and narrow viewports allow the leaderboard
layout to overflow horizontally.

These gaps matter now because they undermine the trustworthiness of the new
web-first public site. The leaderboard is one of the primary product surfaces,
so its public contract and responsive behavior need to match the verified spec.

## What Changes

- Restore explicit Team, FFA, and Support leaderboard columns so the public UI
  matches the current spec language and exposes role/support metrics where
  required.
- Restrict the FFA leaderboard to players with guild-relevant FFA participation
  instead of listing zero-activity rows from other scopes.
- Define and implement responsive leaderboard containment so mobile visitors do
  not get page-level horizontal overflow when viewing leaderboard tables.
- Update the public leaderboard spec deltas and related site requirements so
  the expected column labels, row eligibility, and mobile behavior are
  unambiguous.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `guild-player-leaderboards`: tighten public leaderboard column contracts,
  FFA row eligibility, and responsive presentation requirements
- `guild-public-sites`: clarify public leaderboard/mobile presentation behavior

## Impact

- Affects the public SPA leaderboard rendering in
  `src/apps/web/frontend/src/App.jsx` and related CSS in
  `src/apps/web/frontend/src/styles.css`.
- Affects leaderboard payload shaping and/or filtering in
  `src/services/guild_stats_api.py`.
- Requires updates to OpenSpec delta files and web regression coverage for
  leaderboard views and mobile layout behavior.
