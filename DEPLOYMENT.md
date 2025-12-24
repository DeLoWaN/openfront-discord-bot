# Deploying the Counting Bot

## Prerequisites
- Python 3.10+ and `pip`
- A Discord application with a bot token and permission to invite it to your guild
- Guild roles created for each win threshold (bot role must sit above them)
- Network egress to `https://api.openfront.io`

## Discord setup
- In the Discord Developer Portal, create a bot, copy its **Token**, and enable the **Server Members Intent** (the bot assigns roles and needs member info).
- Invite the bot to your server with the scopes `bot applications.commands` and at least the permissions `Manage Roles`, `View Channels`, and `Send Messages`. Ensure the bot’s role is higher than any win-tier roles it must grant.

## Server setup
```bash
git clone https://github.com/<your-org>/counting-bot.git
cd counting-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configuration
1) Copy the example and fill in your values:
```bash
cp config.example.yml config.yml
```
2) Edit `config.yml`:
```yaml
token: "DISCORD_BOT_TOKEN"
admin_role_ids:
  - 123456789012345678   # IDs of roles allowed to run admin commands
database_path: "bot.db"  # optional; defaults to bot.db in the repo
```
- Optionally set `CONFIG_PATH=/absolute/path/to/config.yml` if the file lives elsewhere.

## Running the bot
```bash
source .venv/bin/activate
python -m src.bot
```
- On first start the SQLite DB is created and default role thresholds are seeded (role_id=0 placeholders). Slash commands are auto-registered in the guild the bot is in.
- The bot syncs every 60 minutes by default; adjust later with `/set_interval`.

## After first launch
- Assign real role IDs to thresholds: from an admin account (with a role listed in `admin_role_ids`), run `/add_role wins:<n> role:<select role> role_name:<display name>`. Repeat for each threshold, then check with `/list_roles`.
- Set clan tags (for the default `sessions_with_clan` mode) via `/set_clan TAG`, or switch counting mode with `/set_mode total|sessions_since_link|sessions_with_clan`.
- Test linking and role assignment with `/link <player_id>` and `/sync` (admin) or wait for the next scheduled sync.

## Systemd example (production)
Create `/etc/systemd/system/counting-bot.service`:
```ini
[Unit]
Description=Counting Bot
After=network.target

[Service]
User=bot
WorkingDirectory=/opt/counting-bot
Environment=CONFIG_PATH=/opt/counting-bot/config.yml
ExecStart=/opt/counting-bot/.venv/bin/python -m src.bot
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Then enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now counting-bot
sudo systemctl status counting-bot
```
- Logs are emitted to stdout/stderr (view with `journalctl -u counting-bot -f`); watch for warnings about missing role IDs or sync failures.
