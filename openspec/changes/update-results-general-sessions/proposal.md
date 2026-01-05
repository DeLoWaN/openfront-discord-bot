# Change: Use general games for results polling

## Why
Clan sessions only cover team games, so FFA wins are missed. Polling public games allows us to detect both FFA and team wins while still restricting posts to configured clan tags.

## What Changes
- Replace clan-session polling with public games polling (`/public/games`) using pagination via `Content-Range`.
- Resolve winners from game details (`/public/game/:id?turns=false`) using `info.winner` client IDs.
- Determine a single winning clan tag from winner client IDs; skip games with no tag, multiple tags, or a tag not in the guild list.
- Include all players with the winning clan tag as winners; annotate non-winner client IDs as `*died early*`.

## Impact
- Affected specs: `game-results-posting` (new or updated capability)
- Affected code: `src/openfront.py`, `src/bot.py` (results poller), `tests/test_results_poll.py`
