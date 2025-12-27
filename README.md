# OpenFront Roles Discord Bot

Discord bot for multiple Discord servers (guilds). It links members to their OpenFront player IDs, counts wins from the public API, and assigns tier roles automatically based on the win thresholds you set. Each server keeps its own small SQLite database so servers stay isolated.

## Hosted version
This project maintainer graciously provide an hosted version of this bot if you don't have the hardware to do this on your own. Please use [this link](https://discord.com/oauth2/authorize?client_id=1453381112134111354) to install the bot.

## Prerequisites
- Python 3.10+ and `pip`
- Discord application with a bot token; enable the **Server Members Intent**
- Ability to invite the bot with `Manage Roles`, `View Channels`, `Send Messages`, and `applications.commands` permissions
- Network access to https://api.openfront.io
- Guild roles created for each win tier, with the bot's role above them

## Discord setup
- In the Discord Developer Portal, create a bot, copy its **Token**, and enable the **Server Members Intent**.
- Invite the bot with scopes `bot applications.commands` and at least the permissions `Manage Roles`, `View Channels`, and `Send Messages`. Ensure the bot’s role is higher than any win-tier roles it must grant.

## Setup
1. Clone the project and create a virtual environment (keeps Python packages for this bot separate):
   ```bash
   git clone https://github.com/DeLoWaN/openfront-roles-discord-bot
   cd openfront-roles-discord-bot
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

## Configuration
1. Copy the example config and fill in your values:
   ```bash
   cp config.example.yml config.yml
   ```
2. Edit `config.yml` with your values:
   ```yaml
   token: "DISCORD_BOT_TOKEN"
   central_database_path: "central.db"  # Registry for all guilds the bot joins
   log_level: "INFO"                    # CRITICAL | ERROR | WARNING | INFO | DEBUG
   sync_interval_hours: 24             # Background sync for every guild (1–24 hours)
   ```
   - You can set an environment variable `CONFIG_PATH=/absolute/path/to/config.yml` if the file lives elsewhere.

## Running the bot
```bash
source .venv/bin/activate
python -m src.bot
```
- A small central DB is created at `central.db` (configurable) and one DB per server is created on first join under `guild_data/guild_<guild_id>.db`. Tables are created automatically; set up role thresholds via commands after the bot joins.
- Admin roles are auto-seeded from server roles that have `Administrator` or `Manage Guild`. You can add/remove admin roles later with commands.
- Slash commands sync automatically to every guild the bot is in.
- The background sync interval is global and comes from `sync_interval_hours` in the config (default 24 hours for every guild).
- `/guild_remove` deletes a guild’s data and the bot leaves; re-invite to start fresh.

## After first launch
- Add role thresholds with `/roles_add wins:<number> role:<pick a role>`, then check with `/roles`.
- Add clan tags (used by the default `sessions_with_clan` mode) via `/clan_tag_add TAG`, or switch counting mode with `/set_mode total|sessions_since_link|sessions_with_clan`.
- Test linking and role assignment with `/link <player_id>` and `/sync` (admin; you can target one user) or wait for the next scheduled sync.
- To wipe data and make the bot leave a server, run `/guild_remove confirm:true` (admin only) and re-invite later if needed.

## Counting modes
The bot uses one counting mode at a time (change it with `/set_mode`). Pick what fits your server:
- `sessions_with_clan` (default): Counts wins from *Public* sessions with the clan tag matching a list of stored tag (uppercase).  
  Example: Stored tags = `ABC`, `XYZ`. Username `[XYZ]Player` or `Player[ABC]` counts as a win; a session with no tag or a different tag is ignored.
- `sessions_since_link`: Counts wins from sessions that **started** after the user linked their player ID.
  Example: User links at `2024-04-01 12:00 UTC`. A win from a session that started on `2024-04-02` counts; a session that started earlier does not.
- `total`: Uses total public FFA + Team wins from the player profile.  
  Example: Profile shows `FFA Medium wins = 5` and `Team Medium wins = 7`; total wins = 12.

Quick guidance: use `sessions_with_clan` for clan-only tracking, `sessions_since_link` for “since they joined”, or `total` for lifetime wins.

## How role thresholds work
You set one or more “win tiers” that map a minimum win count to a Discord role. The bot gives each user the highest tier they qualify for and removes lower tiers to keep things tidy.

Example tiers:
- `10 wins -> Bronze role`
- `25 wins -> Silver role`
- `50 wins -> Gold role`

What happens:
- 8 wins: no tier role yet.
- 12 wins: gets Bronze.
- 30 wins: gets Silver (Bronze removed).
- 50 wins: gets Gold (Bronze/Silver removed).

Useful commands:
- Add or update a tier: `/roles_add wins:<number> role:<pick a role>`
- Remove a tier: `/roles_remove wins:<number>` or `/roles_remove role:<role>`
- List tiers: `/roles`

## Slash commands
| Command | Purpose | Admin only? |
| --- | --- | --- |
| `/link <player_id>` | Link your Discord account to an OpenFront player ID; fetches last session username | No |
| `/unlink` | Remove your link | No |
| `/status [user]` | Show link details and last sync info (target another user if admin) | No (admin to inspect others) |
| `/sync [user]` | Trigger immediate sync for all or a specific user | Yes |
| `/set_mode <mode>` | Set counting mode (`total`, `sessions_since_link`, `sessions_with_clan`) | Yes |
| `/get_mode` | Show current counting mode | Yes |
| `/roles_add wins:<n> role:<role>` | Insert/update a role threshold | Yes |
| `/roles_remove [wins] [role]` | Delete thresholds by wins and/or role ID | Yes |
| `/roles` | List configured thresholds | No |
| `/clan_tag_add <tag>` | Add a clan tag used for `sessions_with_clan` mode | Yes |
| `/clan_tag_remove <tag>` | Remove a clan tag | Yes |
| `/clans_list` | List stored clan tags | No |
| `/link_override <user> <player_id>` | Admin override to link a user | Yes |
| `/audit [page]` | Show recent audit entries (20 per page) | Yes |
| `/admin_role_add <role>` | Add an admin role for this guild | Yes |
| `/admin_role_remove <role>` | Remove an admin role | Yes |
| `/admin_roles` | List admin role IDs for this guild | Yes |
| `/guild_remove confirm:true` | Delete this guild’s data from the bot | Yes |

## Roles and clans
- Thresholds are not pre-set; add them with `/roles_add` and view them with `/roles`.
- Make sure the bot’s role is higher than your win-tier roles so it can assign them.
- Clan tags are stored uppercased and matched against session `clanTag` or a `[TAG]` parsed from username for PUBLIC games when using `sessions_with_clan` mode.

## Data storage and logging
- Central registry at `central_database_path` tracks which servers the bot knows about.
- Each server has its own SQLite DB under `guild_data/`, storing users, thresholds, clan tags, admin roles, settings, and audit entries.
- Logs go to stdout; adjust detail with `log_level` in the config. Watch for warnings about missing role IDs or sync failures.

## Systemd example (production)
Create `/etc/systemd/system/openfront-roles-discord-bot.service`:
```ini
[Unit]
Description=Counting Bot
After=network.target

[Service]
User=bot
WorkingDirectory=/opt/openfront-roles-discord-bot
Environment=CONFIG_PATH=/opt/openfront-roles-discord-bot/config.yml
ExecStart=/opt/openfront-roles-discord-bot/.venv/bin/python -m src.bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Then enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now openfront-roles-discord-bot
sudo systemctl status openfront-roles-discord-bot
```
- Logs are emitted to stdout/stderr (view with `journalctl -u openfront-roles-discord-bot -f`).
