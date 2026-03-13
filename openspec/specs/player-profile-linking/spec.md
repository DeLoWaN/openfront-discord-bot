# player-profile-linking Specification

## Purpose
TBD - created by archiving change add-web-guild-stats. Update Purpose after archive.
## Requirements
### Requirement: Link a site account to an OpenFront player identity

The system SHALL allow a signed-in site user authenticated through Discord to
link exactly one OpenFront `player_id` to their site account for use on public
guild player profiles.

#### Scenario: User links a player ID

- **WHEN** an authenticated site user submits a valid OpenFront `player_id`
- **THEN** the system stores that link on the user's site account

#### Scenario: User replaces a linked player ID

- **WHEN** an authenticated site user who already has a linked OpenFront
  `player_id` submits a different valid `player_id`
- **THEN** the system replaces the previous link with the new one

### Requirement: Recalculate linked guild stats by player ID

For a linked player profile, the system SHALL recalculate that player's
guild-scoped stats using the linked OpenFront `player_id` and SHALL only count
sessions relevant to the guild's tracked clan tags. When a session does not
provide `clanTag`, the system SHALL apply the same effective-clan-tag fallback
used for observed data.

#### Scenario: Linked player changed username

- **WHEN** a player has changed usernames over time but links a stable OpenFront
  `player_id`
- **THEN** the system calculates that player's guild-scoped linked stats from
  the linked player history instead of relying only on the current observed
  username

### Requirement: Associate exact observed aliases to linked players

When a player links an OpenFront `player_id`, the system SHALL associate the
linked profile with exact usernames observed in that player's retrieved
OpenFront history. The system SHALL NOT perform fuzzy matching between similar
usernames.

#### Scenario: Exact alias found in linked history

- **WHEN** the linked player's retrieved OpenFront history contains a username
  that exactly matches an observed guild player entry
- **THEN** the system associates that observed alias with the linked player

#### Scenario: Similar but non-exact alias

- **WHEN** an observed guild player entry has a username that only partially
  matches a linked player's known usernames
- **THEN** the system does not merge that observed entry into the linked player

### Requirement: Separate linked global stats from guild stats

The system SHALL label linked profiles with a factual linked state and SHALL
display OpenFront-global stats in a section separate from guild-scoped stats so
guild leaderboard totals remain scoped only to guild-relevant data.

#### Scenario: Visitor opens linked player profile

- **WHEN** a visitor opens a player profile that has a linked OpenFront
  identity
- **THEN** the profile shows linked state plus separate sections for guild stats
  and global OpenFront stats

