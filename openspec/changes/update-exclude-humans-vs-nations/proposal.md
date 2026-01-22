# Change: Exclude Humans vs Nations from analysis

## Why
Humans vs Nations matches should not be included in win analysis or results posting. These games currently appear in analyzed results and can inflate win counts.

## What Changes
- Skip results posting when a game's `playerTeams` indicates Humans vs Nations.
- Exclude Humans vs Nations sessions from session-based win counting modes.
- Do not attempt to exclude Humans vs Nations in `total` mode since aggregate stats do not expose mode details.

## Impact
- Affected specs: `game-results-posting`, `win-counting` (new or updated capability)
- Affected code: `src/bot.py`, `src/wins.py`, `tests/`
