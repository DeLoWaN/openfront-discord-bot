# Refine Overall Scoring Copy Visibility Tasks

## 1. Scope Overall weighting copy to the Overall view

- [x] 1.1 Update leaderboard scoring-help rendering so the `70% Team` /
  `30% FFA` weighting message is shown only when the active leaderboard view is
  `overall`
- [x] 1.2 Keep Team, FFA, and Support leaderboard pages limited to copy that is
  relevant to their own active view

## 2. Verify leaderboard copy visibility

- [x] 2.1 Add or update web tests to assert that the Overall weighting message
  appears on the `Overall` leaderboard and is absent from `Team`, `FFA`, and
  `Support`
- [x] 2.2 Verify the leaderboard views in a browser so the Overall weighting
  copy is visible only on the `Overall` tab
