# Add Web Guild Stats Design

## Context

The current project is a Discord bot that stores one SQLite database per guild
and computes player wins from OpenFront player endpoints keyed by `player_id`.
That model works for Discord role assignment, but it does not fit a public
website that must publish guild statistics, expose player profiles, and evolve
independently from Discord.

The new product direction is web-first. Each guild is still provisioned
manually and served on its own subdomain, but the main experience moves to a
public website. Discord remains optional at two levels:

- A guild may exist without a connected Discord server.
- A player may browse public stats without signing in, but can optionally sign
  in with Discord to link an OpenFront `player_id`.

OpenFront's public game/session data introduces an identity constraint: guild
relevant observations primarily expose usernames, clan tags, and per-game
client IDs, while durable `player_id` access is only available when the system
already knows that `player_id`. That means guild leaderboards cannot depend on
all players proactively linking through Discord. The architecture must support
unlinked observed players while allowing linked players to get more reliable
stats.

This change also replaces the current per-guild SQLite isolation model with a
single MariaDB database. The repo should remain single for now, but be
restructured around a web app, ingestion worker, shared core/data code, and an
optional bot integration.

## Goals / Non-Goals

**Goals:**

- Make the website the primary product surface, with one public subdomain per
  manually provisioned guild.
- Build guild leaderboards from guild-relevant OpenFront games rather than from
  Discord-linked users only.
- Support public player profiles for both observed and linked players.
- Let players sign in with Discord to link an OpenFront `player_id`.
- Distinguish between observed guild stats and linked, more reliable stats.
- Preserve historical clan-tag handling by parsing `[TAG]` from usernames when
  the API `clanTag` field is absent.
- Migrate from per-guild SQLite storage to one multi-tenant MariaDB schema
  while keeping the current ORM.
- Keep the Discord bot viable as a secondary integration against the new shared
  backend.

**Non-Goals:**

- Build self-service guild creation or ownership claim flows.
- Use fuzzy matching to merge similar usernames.
- Guarantee perfect identity resolution for unlinked players.
- Replace the ORM as part of this change.
- Rebuild all Discord bot behavior before the web product ships.

## Decisions

### 1. Use a single repo and a web-first application layout

The repo will stay unified but shift from bot-first to web-first. The intended
layout is:

- `apps/web` for the public website and Discord login flow
- `apps/worker` for OpenFront ingestion, backfills, and aggregate refreshes
- `apps/bot` for optional Discord commands/integrations
- shared core/data modules for business logic and persistence

This keeps the existing codebase manageable while allowing the web app, worker,
and bot to share the same data model and business rules.

Alternatives considered:

- Separate web and bot repos: cleaner product separation, but would duplicate
  persistence and domain logic too early.
- Rewrite into a brand-new product repo: conceptually cleaner, but slower and
  riskier than evolving the existing codebase.

### 2. Replace per-guild SQLite with one MariaDB database keyed by `guild_id`

The current "one SQLite file per guild" pattern is poorly suited to a public
website, cross-guild administration, backfills, and shared services. A single
MariaDB database with logical multi-tenancy via `guild_id` simplifies hosting,
aggregation, migrations, and public reads.

The ORM remains in place to reduce migration risk and preserve familiarity with
the current codebase.

Alternatives considered:

- Keep SQLite for the bot and add a second web database: faster initially, but
  entrenches two competing storage models.
- Use two MariaDB databases, one for bot and one for web: increases operational
  and sync complexity without a clear product need today.

### 3. Make guild leaderboards game-first, not player-first

Guild leaderboard truth will come from observed games and participants, not
from the set of players who have linked accounts. A game is guild-relevant when
at least one tracked clan tag for that guild appears in the observed data.

The worker will ingest relevant games, persist participants, and compute guild
aggregates from those observations. The website reads those aggregates rather
than recalculating on demand.

This keeps the leaderboard representative of the guild even when many players
have never linked a `player_id`.

Alternatives considered:

- Build leaderboards only from linked players: more reliable identity, but far
  too incomplete for a public guild product.
- Compute leaderboards live from raw games on each request: simpler storage,
  but worse performance and more fragile logic.

### 4. Support two confidence levels for player stats

The system will expose two layers of player data:

- `Observed`: derived from guild-relevant games using usernames and clan tags
- `Linked`: available when a signed-in user associates an OpenFront `player_id`

Guild leaderboard totals remain guild-scoped. Linked players may also display a
separate OpenFront-global stats section on their profile. The linked state is
an enrichment path, not a requirement for appearing on the leaderboard.

This avoids comparing incomparable numbers in the guild leaderboard while still
encouraging players to link for more accurate profiles.

Alternatives considered:

- Use `player_id`-based totals directly in the guild leaderboard for linked
  players: produces inconsistent ranking because linked and unlinked profiles
  would be based on different scopes.
- Ignore `player_id` entirely: simpler model, but loses the only strong
  identity signal available to users who choose to link.

### 5. Use exact observed identity by `(guild_id, normalized_username)`

For unlinked players, the observed identity key is the normalized username
within the guild. Clan tag is not part of the identity key, so the same
username seen under multiple tracked clan tags for the same guild is treated as
one player.

No fuzzy matching is performed. Similar names remain distinct until a stronger
signal exists. If two different people use the exact same username in one guild
scope, they may be merged until a linked identity can disambiguate them.

Alternatives considered:

- Include clan tag in the observed identity key: would incorrectly split one
  player moving between tracked tags in the same guild.
- Add fuzzy matching: would create hidden, hard-to-audit identity errors.

### 6. Resolve historical clan tags through a single ingestion rule

Each observed session or game participant will have an `effective_clan_tag`:

- Prefer the API `clanTag` when present.
- Otherwise parse the first `[TAG]` found anywhere in the username.

The system also stores `raw_clan_tag`, `raw_username`, and a tag-source marker
so historical behavior stays traceable. This preserves compatibility with older
OpenFront data where clan tags lived inside usernames rather than in a
dedicated field.

Alternatives considered:

- Use API `clanTag` only: loses historical guild relevance for older data.
- Parse usernames even when `clanTag` is present: adds unnecessary ambiguity.

### 7. Provision guilds manually and keep Discord optional

Guild creation and subdomain assignment remain manual. Discord is not a
prerequisite for a guild to exist. Discord sign-in is only used for end-user
account linking and any future optional integration features.

This matches the current operating model and avoids introducing claim,
moderation, and ownership workflows that are not needed for the first version.

Alternatives considered:

- Self-service guild creation: higher product complexity with little immediate
  value.
- Discord-required guild ownership: conflicts with the goal of making Discord
  optional.

## Risks / Trade-offs

- [Unlinked usernames are imperfect identities] → Show them as observed data,
  keep linking optional, and avoid overstating accuracy in the UI.
- [Two players with the same username may be merged] → Scope identity to one
  guild, keep merging rules simple, and let linked profiles become canonical.
- [MariaDB migration is broader than a simple driver swap] → Stage migration
  through new shared models and backfills rather than trying to preserve the
  current SQLite layout.
- [Backfills may be slow or partial] → Build an explicit worker pipeline with
  resumable ingestion and persistent aggregate refreshes.
- [The bot may lag behind the new backend model temporarily] → Treat the bot as
  a follow-on integration and keep the initial web launch independent.
- [Subdomain routing adds deployment complexity] → Keep guild provisioning
  manual so DNS and routing stay controlled during rollout.

## Migration Plan

1. Introduce MariaDB configuration and shared Peewee models for the new
   multi-tenant schema.
2. Add core entities for guilds, guild clan tags, site users, players,
   aliases/links, games, participants, and guild aggregates.
3. Migrate the small set of existing configuration data that still matters,
   especially guild identity, tracked clan tags, and any reusable Discord link
   metadata.
4. Build the worker ingestion flow for guild-relevant games and participant
   observations, including effective clan-tag resolution and aggregate refresh.
5. Backfill historical guild data into the new schema.
6. Launch a minimal public web app with guild landing page, leaderboard, and
   player profile pages.
7. Add Discord sign-in and `player_id` linking, then enrich linked profiles
   with more reliable guild stats plus separate global OpenFront stats.
8. Repoint or adapt the Discord bot to the new shared backend after the web
   stack is working.

Rollback strategy:

- Keep existing SQLite bot data untouched during the initial MariaDB rollout.
- Treat MariaDB and the web app as additive until the new pipeline is stable.
- If the web stack fails during early rollout, disable public traffic to the
  web app and continue operating the existing bot from SQLite while fixes are
  prepared.

## Open Questions

- Which web framework and rendering model should be used for `apps/web`,
  provided it can share the existing Python data/model layer cleanly?
- What is the preferred migration mechanism for MariaDB schema evolution in
  this repo, given the current SQLite `ALTER TABLE` style?
- How much historical backfill is realistically needed for the first public
  launch versus a phased import window?
