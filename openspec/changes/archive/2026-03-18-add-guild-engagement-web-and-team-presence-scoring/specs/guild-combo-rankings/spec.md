# guild-combo-rankings Delta

## ADDED Requirements

### Requirement: Publish confirmed guild combo rankings

The system SHALL expose public guild-scoped combo rankings for `duo`, `trio`,
and `quad` formats. A combo SHALL be eligible for confirmed ranking only when
it comes from a guild-relevant `Team` game whose format is exactly `Duos`,
`Trios`, or `Quads`, the guild-side tracked-tag group exactly fills the team
size, and the combo has played at least `5` games together. Confirmed combos
SHALL be ranked by raw win rate, then by games together, then by wins
together, then by most recent win.

#### Scenario: Duo reaches confirmed threshold

- **WHEN** the same full-guild duo has played `5` or more valid `Duos` games
- **THEN** the duo appears in the confirmed guild combo rankings

#### Scenario: Mixed guild and random team is excluded

- **WHEN** a `Duos`, `Trios`, or `Quads` team contains fewer tracked guild-tag
  players than the full team size
- **THEN** that team does not contribute to confirmed combo rankings

### Requirement: Publish pending guild combo rankings separately

The system SHALL expose pending guild combo views for valid `duo`, `trio`, and
`quad` combinations that have played together but have not yet reached the
confirmed threshold. Pending combos SHALL NOT appear in the confirmed podiums
shown on the guild home page.

#### Scenario: Combo is still pending

- **WHEN** a valid full-guild trio has played `1` to `4` games together
- **THEN** the trio appears in the pending combo view and not in confirmed
  rankings

#### Scenario: Home teases pending combos without merging them into podiums

- **WHEN** a guild home page includes combo teaser content
- **THEN** the teaser links visitors to pending combo views instead of mixing
  pending rows into confirmed combo podiums

### Requirement: Expose combo detail views and histories

The system SHALL expose public combo detail views for confirmed and pending
guild combos. A combo detail view SHALL identify the roster, the combo format,
games together, wins together, win rate, and a recent result history that can
be rendered as a graph or timeline.

#### Scenario: Visitor opens confirmed combo detail

- **WHEN** a visitor opens a confirmed guild duo detail view
- **THEN** the system shows the duo roster, confirmed status, cumulative combo
  metrics, and recent result history

#### Scenario: Visitor opens pending combo detail

- **WHEN** a visitor opens a pending guild quad detail view
- **THEN** the system shows the quad roster, pending status, and the current
  sub-threshold sample without labeling it as confirmed
