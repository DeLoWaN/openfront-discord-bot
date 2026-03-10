## Context
Results posting currently polls clan sessions, which excludes FFA games. We need to detect wins from all public games while still limiting posts to the guild's configured clan tags.

## Goals / Non-Goals
- Goals:
  - Use public games polling with pagination to discover relevant games.
  - Resolve winners from game details and map them to a single winning clan tag.
  - Include clan members who share the winning tag even if they are not in the winner list, marking them as "died early".
- Non-Goals:
  - Change commands, settings, or database schema.
  - Alter mention mapping or embed layout beyond the winner annotation.

## Decisions
- Poll `GET /public/games` with `start/end` and `type=Public`, paging using the `Content-Range` header until all results are fetched.
- For each game ID, fetch `GET /public/game/:id?turns=false` and parse `info.winner` entries that match player `clientID` values.
- Derive the winning clan tag from the winner client IDs; if zero or multiple distinct clan tags are found, skip the game. If the tag is not in the guild's configured clan tags, skip the game.
- For team games, build the winners list from all players whose `clanTag` matches the winning tag; for any such player whose `clientID` is not in the winner list, append `- 💀 *died early*`, and add a `+X other players` suffix based on players-per-team.
- For Free For All games, only display the winner client ID(s) and do not promote same-tag players to winners.
- Keep opponents grouping by other clan tags and leave embed structure unchanged.

## Risks / Trade-offs
- Increased API usage due to paging the games list and fetching game details per candidate.
- Some winning games may be skipped if winners have no clan tag or mixed tags.
- Reliance on `Content-Range` parsing; if missing or malformed, fall back to a single page.

## Migration Plan
- No schema changes; existing settings and `posted_games` dedupe remain in place.
- Deploy updated polling logic; no data backfill required.

## Open Questions
- None.
