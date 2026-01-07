# OpenFront Discord Bot

Discord bot for multiple Discord servers (guilds). It links members to OpenFront player IDs, counts wins from the OpenFront public API, assigns tier roles based on thresholds, and can post victory embeds for configured clan tags. Each guild keeps its own SQLite database so data stays isolated.

## Hosted version
This project's maintainer provides a hosted version if you do not want to self-host. Install it here: https://discord.com/oauth2/authorize?client_id=1453381112134111354

## Features
- Link Discord users to OpenFront player IDs to assign roles and mention winners from games.
- Automatic role assignment based on win thresholds
- Counting modes for role assigment: total wins, wins since date, or wins in public sessions with configurable clan tags.
- Background sync for all guilds plus manual sync on demand.
- Optional game results posting by polling public lobbies and posting victory embeds.
  <img width="372" height="330" alt="image" src="https://github.com/user-attachments/assets/089596be-1908-49ec-878e-daae968dfbf9" />
- Admin tools: audit log, admin role list, and link overrides.

## Prerequisites
- Python 3.10+ and `pip`
- Discord application with a bot token; enable the **Server Members Intent**
- Ability to invite the bot with `Manage Roles`, `View Channels`, `Send Messages`, and `applications.commands` permissions
- Network access to https://api.openfront.io and https://openfront.io
- Guild roles created for each win tier, with the bot's role above them

## Discord setup
- In the Discord Developer Portal, create a bot, copy its **Token**, and enable the **Server Members Intent**.
- Invite the bot with scopes `bot applications.commands` and at least the permissions `Manage Roles`, `View Channels`, and `Send Messages`. Ensure the bot's role is higher than any win-tier roles it must grant.

## Setup
1. Clone the project and create a virtual environment (keeps Python packages for this bot separate):
   ```bash
   git clone https://github.com/DeLoWaN/openfront-discord-bot
   cd openfront-discord-bot
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
   sync_interval_hours: 24              # Background sync cadence for all guilds (1-24 hours)
   results_lobby_poll_seconds: 2        # Public lobby poll interval (seconds)
   ```
   - You can set an environment variable `CONFIG_PATH=/absolute/path/to/config.yml` if the file lives elsewhere.

## Running the bot
```bash
source .venv/bin/activate
python -m src.bot
```
- A central DB is created at `central_database_path`, and one DB per server is created on first join under `guild_data/guild_<guild_id>.db`.
- Admin roles are auto-seeded from server roles that have `Administrator` or `Manage Guild`. You can add/remove admin roles later with commands.
- Slash commands sync automatically to every guild the bot is in.
- The background sync interval is global and comes from `sync_interval_hours` in the config (default 24 hours for every guild).
- If a player ID returns 404 three times, sync is disabled for that user until they re-link.
- `/guild_remove` deletes a guild's data and the bot leaves; re-invite to start fresh.

## After first launch
- Add role thresholds with `/roles_add wins:<number> role:<pick a role>`, then check with `/roles`.
- Add clan tags (used by the default `sessions_with_clan` mode) via `/clan_tag_add TAG`, or switch counting mode with `/set_mode total|sessions_since_link|sessions_with_clan`.
- Test linking and role assignment with `/link <player_id>` and `/sync` (admin; you can target one user) or wait for the next scheduled sync.
- To wipe data and make the bot leave a server, run `/guild_remove confirm:true` (admin only) and re-invite later if needed.

## Game results posting
The bot can post a victory embed when a tracked game finishes and one of your configured clan tags wins.
- Add clan tags with `/clan_tag_add` (results will not post without tags).
- Set the destination channel with `/post_game_results_channel <channel>`.
- Enable posting with `/post_game_results_start` (disable with `/post_game_results_stop`).
- For testing, `/post_game_results_test` seeds recent public games into the tracker.
- Game IDs are discovered by polling public lobbies; results are deduped using `posted_games` and retried if the game is not finished yet.

## Counting modes
The bot uses one counting mode at a time (change it with `/set_mode`). Pick what fits your server:
- `sessions_with_clan` (default): Counts wins from public sessions with a clan tag. Tags are matched against stored tags, or against `[TAG]` in usernames when `clanTag` is missing. If no tags are configured, any public session with a clan tag counts.
- `sessions_since_link`: Counts wins from sessions that started after the user linked their player ID.
- `total`: Uses total public FFA + Team wins from the player profile.

Quick guidance: use `sessions_with_clan` for clan-only tracking, `sessions_since_link` for "since they joined", or `total` for lifetime wins.

## How role thresholds work
You set one or more "win tiers" that map a minimum win count to a Discord role. The bot gives each user the highest tier they qualify for and removes lower tiers to keep things tidy.

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
| `/guild_remove confirm:true` | Delete this guild's data from the bot | Yes |
| `/post_game_results_start` | Enable posting game results | Yes |
| `/post_game_results_stop` | Disable posting game results | Yes |
| `/post_game_results_channel <channel>` | Set the channel for results posts | Yes |
| `/post_game_results_test` | Seed recent games for results testing | Yes |

## Roles and clans
- Thresholds are not pre-set; add them with `/roles_add` and view them with `/roles`.
- Make sure the bot's role is higher than your win-tier roles so it can assign them.
- Clan tags are stored uppercased and matched against session `clanTag` or a `[TAG]` parsed from username for public games when using `sessions_with_clan` mode.

## Data storage and logging
- Central registry at `central_database_path` tracks which servers the bot knows about and which games are queued for results processing.
- Each server has its own SQLite DB under `guild_data/`, storing users, thresholds, clan tags, admin roles, settings, audit entries, and posted game IDs.
- Audit entries are kept for 90 days; posted game IDs are kept for 7 days to avoid duplicates.
- Logs go to stdout; adjust detail with `log_level` in the config. Watch for warnings about missing role IDs, sync failures, or OpenFront API errors.

## Systemd example (production)
Create `/etc/systemd/system/openfront-discord-bot.service`:
```ini
[Unit]
Description=Counting Bot
After=network.target

[Service]
User=bot
WorkingDirectory=/opt/openfront-discord-bot
Environment=CONFIG_PATH=/opt/openfront-discord-bot/config.yml
ExecStart=/opt/openfront-discord-bot/.venv/bin/python -m src.bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Then enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now openfront-discord-bot
sudo systemctl status openfront-discord-bot
```
- Logs are emitted to stdout/stderr (view with `journalctl -u openfront-discord-bot -f`).
