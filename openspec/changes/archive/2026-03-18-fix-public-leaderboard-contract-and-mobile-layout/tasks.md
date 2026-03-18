## 1. Implementation

- [x] 1.1 Update public leaderboard payload shaping so the `ffa` view excludes
  players without guild-relevant FFA participation.
- [x] 1.2 Restore explicit Team, FFA, and Support column definitions in the
  public leaderboard UI, including `Role` and donation metrics where required.
- [x] 1.3 Constrain leaderboard overflow on narrow screens so the page does not
  grow wider than the viewport.
- [x] 1.4 Add or update regression coverage for leaderboard headers, FFA row
  eligibility, and narrow-screen overflow behavior.

## 2. Verification

- [x] 2.1 Validate the change with Playwright MCP across home, leaderboard,
  weekly, rosters, recent games, and player profile flows.
- [x] 2.2 Run the relevant automated tests for the public web leaderboard
  behavior.
