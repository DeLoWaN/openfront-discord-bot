# Recalibrate Competitive Scoring With UN Fixture Tasks

## 1. Capture the change and fixture workflow

- [x] 1.1 Add proposal, design, and spec deltas for the normalized scoring
  model, explanation UX, and UN fixture workflow
- [x] 1.2 Add fixture documentation that explains how to restore the checked-in
  UN SQL dump into an empty database

## 2. Add regression inputs and failing tests

- [x] 2.1 Add unit tests for Team difficulty inference, guild-stack
  adjustments, recency weighting, support normalization, and Overall confidence
- [x] 2.2 Add API and web tests for visible `support_bonus` columns plus summary
  and exact-computation scoring explanations
- [x] 2.3 Add the checked-in UN raw fixture and a regression test that restores
  it, rebuilds aggregates, and asserts key leaderboard outcomes

## 3. Implement the recalibrated scorer

- [x] 3.1 Rewrite aggregate scoring to use inferred Team difficulty, per-game
  recency decay, guild-stack adjustment, normalized support bonus, and
  normalized Overall composition
- [x] 3.2 Update leaderboard and profile API payloads so `support_bonus`
  remains visible and scoring explanations expose both summary and exact
  details
- [x] 3.3 Update the public web leaderboard and player profile rendering to
  show the new support visibility and the expandable exact-computation section

## 4. Verify and finish the change

- [x] 4.1 Run targeted scorer, API, web, and fixture regression tests
- [x] 4.2 Run the full test suite and `openspec validate` for the new change
