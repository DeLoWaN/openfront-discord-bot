# guild-player-leaderboards Specification

## ADDED Requirements

### Requirement: Publish descriptive team role labels

The system SHALL expose player-facing Team role labels that describe a
player's dominant observed Team play style rather than reacting to isolated
support actions. When leaderboard or profile views show a Team role label, a
player who mostly fronts across a meaningful Team sample MUST remain
`Frontliner` even if some games include donations. Players whose Team sample is
too small or too mixed to support a stable dominant style SHALL render the
existing fallback label `Flexible`.

#### Scenario: Mostly-frontline player appears on Team leaderboard

- **WHEN** a player appears on a guild Team or Support leaderboard after mostly
  playing frontline games with occasional donations
- **THEN** the displayed role label is `Frontliner`

#### Scenario: Small-sample player appears on public profile

- **WHEN** a player's observed Team history is too small to support a stable
  role classification
- **THEN** the public leaderboard and player profile show `Flexible`

#### Scenario: Mixed-style player appears on Team leaderboard

- **WHEN** a player's observed Team history does not show a clear dominant
  frontline or backline style
- **THEN** the displayed role label is `Hybrid`
