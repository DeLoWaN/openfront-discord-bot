# Refine Competitive Leaderboard Columns Tasks

## 1. Leaderboard Table Layout

- [x] 1.1 Replace the generic leaderboard table headers with per-view default
  column definitions for `Team`, `FFA`, `Overall`, and `Support`
- [x] 1.2 Render `Linked` versus `Observed` as an inline player indicator so
  the player cell keeps identity context without consuming a standalone column

## 2. Verification

- [x] 2.1 Update web tests to assert the new default headers and visible stats
  for each leaderboard view
- [x] 2.2 Verify the rendered leaderboard views in a browser against the new
  column expectations
