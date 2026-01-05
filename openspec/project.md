# Project Context

## Purpose
Discord bot for multiple guilds that links members to OpenFront player IDs, counts wins from the public OpenFront API, and assigns tier roles based on configured win thresholds. Each guild is isolated via its own SQLite database.

## Tech Stack
- Python 3.10+
- Discord bot platform (slash commands, guild roles, member intents)
- SQLite (central registry + per-guild databases)
- YAML configuration (`config.yml`)
- OpenFront public API (`https://api.openfront.io`)

## Project Conventions

### Code Style
Follow existing conventions in `src/`: type hints, `__future__` annotations, dataclasses where helpful, and standard `logging` usage. Configuration stays in YAML (`config.yml`).

### Architecture Patterns
- Multi-guild bot instance with per-guild data isolation.
- Central registry DB (`central.db`) plus one DB per guild in `guild_data/`.
- Background sync uses a single global interval from `sync_interval_hours`.

### Testing Strategy
Pytest-based tests under `tests/`, with `pytest-asyncio` for async behavior. Tests use local stubs in `tests/conftest.py` to avoid requiring the real `discord.py` and `peewee` packages during unit tests.

### Git Workflow
Not specified in the repo docs.

## Domain Context
- OpenFront win counting modes: total public wins, wins since link time, or wins in sessions matching stored clan tags.
- Role thresholds map minimum win counts to Discord roles; highest qualifying tier is assigned and lower tiers removed.

## Important Constraints
- Requires Discord bot token with Server Members Intent and role management permissions.
- Bot role must be higher than tier roles to assign/remove them.
- Needs network access to the OpenFront API.

## External Dependencies
- Discord API (bot, slash commands, role management)
- OpenFront public API (`https://api.openfront.io`)
- Python dependencies managed via `requirements.txt` / Pipenv, with dev tooling in `Pipfile` (`ruff`, `basedpyright`, `pytest`, `pytest-asyncio`).
