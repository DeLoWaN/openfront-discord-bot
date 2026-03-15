# openfront-game-ingestion Specification

## Purpose

Define how guild-relevant OpenFront observations are ingested into persisted
participant records and derived aggregates.
## Requirements
### Requirement: Resolve effective clan tags for observations

For each observed session or game participant, the system SHALL determine an
effective clan tag by using the API `clanTag` when present and otherwise
parsing the first `[TAG]` token found anywhere in the username. The system
SHALL store the raw username, raw clan tag, effective clan tag, and the source
used to determine that effective clan tag.

#### Scenario: API clan tag present

- **WHEN** an observation includes a non-empty API `clanTag`
- **THEN** the system uses that value as the effective clan tag and records the
  source as the API

#### Scenario: API clan tag missing

- **WHEN** an observation has an empty or null API `clanTag` and the username
  contains `[TAG]`
- **THEN** the system uses the parsed tag as the effective clan tag and records
  the source as username parsing

### Requirement: Persist guild-relevant games and participants

The system SHALL persist observed public OpenFront games and participant data
needed to compute guild-scoped stats. A game SHALL be considered guild-relevant
for a guild when at least one participant's effective clan tag matches one of
that guild's tracked clan tags. For guild-relevant Team games, the system
SHALL also derive per-participant support metrics from turn data, including
exact donation totals and donation action counts. For guild-relevant Free For
All games, the system SHALL persist the mode-appropriate participant data
without requiring Team support metrics.

#### Scenario: Guild-relevant Team game stores support metrics

- **WHEN** a guild-relevant Team game is ingested with turn data available
- **THEN** the system persists the game, the participants, and the derived
  donor-centric support metrics for that game's players

#### Scenario: Guild-relevant FFA game stores solo metrics

- **WHEN** a guild-relevant Free For All game is ingested
- **THEN** the system persists the game and participants without requiring Team
  donation metrics

#### Scenario: Game relevant to multiple guilds

- **WHEN** a game's participants match tracked clan tags from more than one
  guild
- **THEN** the system allows the same observed game and its derived metrics to
  contribute to each matching guild scope

### Requirement: Maintain guild player aggregates from observations

The system SHALL maintain per-guild player aggregates derived from persisted
guild-relevant observations so leaderboard and public profile pages can be
served from stored guild stats rather than recalculating from raw observations
on each request. The aggregate model SHALL maintain separate inputs for Team,
FFA, and Support views, including mode-specific game counts, win counts,
donation totals, donation action counts, recent-activity metadata, and
player-facing sort metrics. The aggregate model SHALL NOT compute or persist a
public `overall` score.

#### Scenario: New Team observation refreshes Team aggregates

- **WHEN** a new guild-relevant Team observation is persisted for a player
- **THEN** the corresponding guild player aggregates are refreshed for Team and
  Support views

#### Scenario: New FFA observation refreshes FFA aggregates

- **WHEN** a new guild-relevant Free For All observation is persisted for a
  player
- **THEN** the corresponding guild player aggregates are refreshed for the FFA
  view

### Requirement: Merge observed players across tracked clan-tag username variants

The system SHALL derive observed player identity within a guild from a
guild-aware base username rather than the raw username string. If a player's
raw username starts with a `[TAG]` prefix and that tag belongs to the guild's
tracked clan tags, the system SHALL strip that tracked prefix before deriving
the observed identity key. If the prefix does not belong to the guild's
tracked clan tags, the system SHALL leave the username untouched for identity
purposes.

#### Scenario: Tracked tag variants merge inside one guild

- **WHEN** a guild tracks both `NU` and `UN` and the observed usernames are
  `[NU] Temujin` and `[UN] Temujin`
- **THEN** the system derives the same guild-scoped observed identity for both
  rows

#### Scenario: Untracked tag variant does not merge

- **WHEN** a guild does not track `XYZ` and the observed username is
  `[XYZ] Temujin`
- **THEN** the system does not strip that prefix when deriving the observed
  identity key

### Requirement: Derive role-oriented metrics without territory reconstruction

The system SHALL derive support and frontline signals from stored donation and
attack metrics and SHALL NOT require reconstructing full territory ownership
history in order to score support behavior. For Team players, the system SHALL
derive role-oriented signals from each observed Team game and SHALL compute the
persisted aggregate `role_label` from the dominant role mix across observed
Team games rather than from lifetime donation presence alone. Occasional
support actions MUST NOT by themselves prevent a mostly-frontline player from
being labeled `Frontliner`. When a player's observed Team sample is too small
or too mixed to support a stable dominant role, the system SHALL persist the
existing fallback label `Flexible`.

#### Scenario: Territory history is unavailable

- **WHEN** the system computes support and role-oriented metrics for a Team
  player
- **THEN** the calculation succeeds from stored donation and attack data
  without replaying territory state

#### Scenario: Mostly-frontline player occasionally donates

- **WHEN** a Team player has a meaningful observed Team sample where most games
  show frontline behavior but some games include support actions
- **THEN** the persisted aggregate `role_label` remains `Frontliner`

#### Scenario: Team sample is too small or ambiguous

- **WHEN** a Team player's observed games do not provide a stable dominant role
- **THEN** the persisted aggregate `role_label` is `Flexible` or `Hybrid`
  instead of forcing a frontline or backline label from isolated events

#### Scenario: Team player has no donation events

- **WHEN** the system computes support and role-oriented metrics for a Team
  player with no donation events
- **THEN** the calculation still produces non-support metrics without requiring
  territory-derived substitutes

### Requirement: Attribute support metrics to the donor

The system SHALL attribute support totals and support actions to the player who
performed each donation intent even when the recipient identity cannot yet be
resolved to a public player entry.

#### Scenario: Donation recipient is not publicly resolvable

- **WHEN** a Team donation intent references a recipient identifier that cannot
  be matched to a public player row
- **THEN** the donation still counts toward the donor's support metrics

#### Scenario: Multiple donation events from one player

- **WHEN** one player performs multiple donation intents in a Team game
- **THEN** the system accumulates each supported donation event into that
  player's support totals

### Requirement: Compute Team score as cumulative guild contribution

The system SHALL compute Team score as a positive cumulative guild-contribution
metric. Every guild-relevant Team game SHALL add participation value. Team
wins SHALL add extra value beyond participation. Team losses SHALL NOT subtract
historical score. Team win rate SHALL act only as a light multiplier on the
positive cumulative total. `support_bonus` SHALL remain a visible additive
bonus derived from persisted donation metrics and SHALL NOT be rank-normalized
independently from the Team score.

#### Scenario: Player loses a Team game

- **WHEN** a player participates in a guild-relevant Team game and does not win
- **THEN** that game still contributes positive participation value to the
  player's cumulative Team score

#### Scenario: Player wins a Team game

- **WHEN** a player wins a guild-relevant Team game
- **THEN** that game contributes the participation value plus extra Team win
  bonus value to the player's cumulative Team score

#### Scenario: Support player donates heavily

- **WHEN** a player records strong donation totals and support share across
  Team games
- **THEN** the persisted `support_bonus` increases the player's Team score as
  a capped additive modifier

### Requirement: Value larger Team lobbies without a hard cap at ten teams

The system SHALL infer Team difficulty from stored game data and SHALL make the
Team score increase monotonically with the number of teams in the lobby. The
difficulty model MUST value a `60`-team win more than a `10`-team win, while
using damped growth so a few extreme lobbies do not dominate the entire
leaderboard.

#### Scenario: Large Team lobby is ingested

- **WHEN** a guild-relevant Team game is inferred to have more than `10` teams
- **THEN** the Team contribution model applies a higher difficulty value than
  it would for a `10`-team game

#### Scenario: Difficulty grows without exploding

- **WHEN** the system compares two Team wins from different lobby sizes
- **THEN** the larger lobby win is worth more, but the growth remains damped
  rather than linearly exploding with team count

### Requirement: Surface recency as metadata instead of score decay

The system SHALL persist recent-activity metadata beside the cumulative Team
and FFA scores. The aggregate recomputation SHALL maintain timestamps and
recent-game counters without using them to decay the main Team or FFA score.

#### Scenario: Player has not played recently

- **WHEN** a player has not played for many weeks
- **THEN** the stored cumulative Team score remains unchanged while the recent
  activity metadata reflects the inactivity

#### Scenario: Player is currently active

- **WHEN** a player has played many recent Team or FFA games
- **THEN** the stored recent-activity metadata reflects that activity beside
  the cumulative score
