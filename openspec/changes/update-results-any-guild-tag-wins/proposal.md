# Change: Count wins when any guild clan tag is in winner list

## Why
Some team games include multiple clan tags on the winning side. The bot currently skips these games because it requires a single winning clan tag, which causes legitimate guild wins to be ignored.

## What Changes
- Treat a game as a guild win when any configured clan tag appears in the winner client IDs.
- Allow multiple winning clan tags and update winner selection accordingly.
- Store multiple winning tags when present.

## Impact
- Affected specs: game-results-posting
- Affected code: src/bot.py (winner resolution, embed title, posted game storage), tests around results polling.
