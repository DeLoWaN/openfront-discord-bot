## ADDED Requirements

### Requirement: Keep public leaderboard views usable on narrow screens

The public website SHALL keep leaderboard pages usable on narrow viewports
without causing page-level horizontal overflow. If the active leaderboard table
requires more width than the viewport, the overflow MUST be contained within
the leaderboard content region rather than expanding the full document width.

#### Scenario: Visitor opens leaderboard on a narrow screen

- **WHEN** a visitor opens a guild leaderboard view on a narrow viewport
- **THEN** the page remains bounded to the viewport and any extra horizontal
  width is contained within the leaderboard region
