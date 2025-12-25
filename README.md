# OpenFront Roles Discord Bot

Discord bot that works across multiple guilds. It links members to their OpenFront player IDs, counts wins from the public API, and assigns tier roles automatically based on configured thresholds. Each guild is isolated in its own SQLite database.

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
   central_database_path: "central.db"  # Registry for all guilds the bot joins
   log_level: "INFO"                    # CRITICAL | ERROR | WARNING | INFO | DEBUG
   ```
   - You can point to a different path by setting `CONFIG_PATH=/absolute/path/to/config.yml`.

## Running the bot
```bash
source .venv/bin/activate
python -m src.bot
```
- A central registry DB is created at `central.db` (configurable) and a per-guild DB is created on first join under `guild_data/guild_<guild_id>.db`. Tables and default thresholds are seeded automatically.
- Slash commands sync automatically to every guild the bot is in.
- The background sync runs every 60 minutes per guild by default; change it later with `/set_interval`.
- `/guild_remove` deletes a guild’s data and the bot leaves; re-invite to start fresh.
- When the bot joins a guild, admin roles are auto-seeded from roles that have the `Administrator` or `Manage Guild` permission. Use admin-role commands to manage them later.
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
| `/admin_role_add <role>` | Add an admin role for this guild | Yes |
| `/admin_role_remove <role>` | Remove an admin role | Yes |
| `/admin_roles` | List admin role IDs for this guild | Yes |
| `/guild_remove confirm:true` | Delete this guild’s data from the bot | Yes |

## Roles and clans
- Default seeded thresholds (editable) are stored in the DB; update them with `/add_role` and inspect with `/list_roles`.
- Ensure the role IDs match roles in your guild and that the bot's role is above those roles so it can assign them.
- Clan tags are stored in the DB and matched case-insensitively when using `sessions_with_clan` mode.

## Data storage and logging
- Central registry at `central_database_path` tracks guild IDs and DB paths.
- Each guild has its own SQLite DB under `guild_data/`, storing users, thresholds, clan tags, admin roles, settings, and audit entries.
- Logs are sent to stdout; control verbosity with `log_level` in the config.
