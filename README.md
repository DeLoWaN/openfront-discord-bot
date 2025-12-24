# OpenFront Roles Discord Bot

Discord bot for a single guild that links members to their OpenFront player IDs, counts wins from the public API, and assigns tier roles automatically based on configured thresholds.

## Prerequisites
- Python 3.10+
- Discord application with a bot token; enable the Server Members Intent
- Ability to invite the bot with the permissions `Manage Roles`, `Send Messages`, and `applications.commands`
- Network access to https://api.openfront.io
- Guild roles created for each win tier, with the bot's role above them

## Setup
1. Create a virtualenv and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy the example config and fill in your values:
   ```bash
   cp config.example.yml config.yml
   ```
3. Edit `config.yml`:
   ```yaml
   token: "DISCORD_BOT_TOKEN"
   admin_role_ids:
     - 123456789012345678   # Roles allowed to run admin commands
   database_path: "bot.db"   # Optional; defaults to bot.db
   log_level: "INFO"         # CRITICAL | ERROR | WARNING | INFO | DEBUG
   ```
   - You can point to a different path by setting `CONFIG_PATH=/absolute/path/to/config.yml`.

## Running the bot
```bash
source .venv/bin/activate
python -m src.bot
```
- On first start the SQLite DB is created and tables are seeded (including default role thresholds).
- Slash commands sync automatically to the guild the bot is in.
- The background sync runs every 60 minutes by default; change it later with `/set_interval`.
- See `DEPLOYMENT.md` for a systemd example.

## Counting modes
The bot keeps one mode in the DB (change via `/set_mode`):
- `sessions_with_clan` (default): counts wins from sessions whose clan tag matches any stored tag.
- `sessions_since_link`: counts wins from sessions that ended after the user linked.
- `total`: sums total public FFA + Team wins from the player profile.

## Slash commands
| Command | Purpose | Admin only? |
| --- | --- | --- |
| `/link <player_id>` | Link your Discord account to an OpenFront player ID; fetches last session username | No |
| `/unlink` | Remove your link | No |
| `/status [user]` | Show link details and last sync info (target another user if admin) | No (admin to inspect others) |
| `/recompute [user]` | Recompute wins and roles for one user or all linked users | Yes |
| `/sync` | Trigger immediate sync loop | Yes |
| `/set_mode <mode>` | Set counting mode (`total`, `sessions_since_link`, `sessions_with_clan`) | Yes |
| `/set_interval <minutes>` | Update sync interval (5–1440 minutes) | Yes |
| `/add_role wins:<n> role:<role> role_name:<text>` | Insert/update a role threshold | Yes |
| `/remove_role [wins] [role]` | Delete thresholds by wins and/or role ID | Yes |
| `/list_roles` | List configured thresholds | No |
| `/clan_tag_add <tag>` | Add a clan tag used for `sessions_with_clan` mode | Yes |
| `/clan_tag_remove <tag>` | Remove a clan tag | Yes |
| `/list_clans` | List stored clan tags | No |
| `/link_override <user> <player_id>` | Admin override to link a user | Yes |
| `/audit [page]` | Show recent audit entries (20 per page) | Yes |

## Roles and clans
- Default seeded thresholds (editable) are stored in the DB; update them with `/add_role` and inspect with `/list_roles`.
- Ensure the role IDs match roles in your guild and that the bot's role is above those roles so it can assign them.
- Clan tags are stored in the DB and matched case-insensitively when using `sessions_with_clan` mode.

## Data storage and logging
- SQLite database path is set by `database_path` (default `bot.db`); it stores users, thresholds, clan tags, settings, and audit entries.
- Logs are sent to stdout; control verbosity with `log_level` in the config.
