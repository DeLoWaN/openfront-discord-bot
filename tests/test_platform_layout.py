from pathlib import Path

from src.bot import main as legacy_bot_main
from src.central_db import init_central_db as legacy_init_central_db
from src.config import BotConfig as LegacyBotConfig
from src.models import init_guild_db as legacy_init_guild_db
from src.openfront import OpenFrontClient as LegacyOpenFrontClient
from src.wins import compute_wins_total as legacy_compute_wins_total


def test_platform_layout_exposes_new_app_and_shared_modules():
    from src.apps.bot.main import CountingBot, main as app_bot_main
    from src.apps.web.app import create_app
    from src.apps.worker.app import create_worker
    from src.core.config import BotConfig as SharedBotConfig
    from src.core.openfront import OpenFrontClient as SharedOpenFrontClient
    from src.core.wins import compute_wins_total as shared_compute_wins_total
    from src.data.legacy.central_db import init_central_db as shared_init_central_db
    from src.data.legacy.models import init_guild_db as shared_init_guild_db

    web_app = create_app()
    worker = create_worker()

    assert CountingBot.__name__ == "CountingBot"
    assert app_bot_main is legacy_bot_main
    assert web_app.name == "openfront-guild-stats"
    assert worker.name == "openfront-guild-stats-worker"
    assert SharedBotConfig is LegacyBotConfig
    assert SharedOpenFrontClient is LegacyOpenFrontClient
    assert shared_compute_wins_total is legacy_compute_wins_total
    assert shared_init_central_db is legacy_init_central_db
    assert shared_init_guild_db is legacy_init_guild_db


def test_platform_layout_exposes_executable_guild_sites_cli():
    launcher = Path(__file__).resolve().parent.parent / "guild-sites"

    assert launcher.exists()
    assert launcher.stat().st_mode & 0o111


def test_platform_layout_exposes_executable_historical_backfill_cli():
    launcher = Path(__file__).resolve().parent.parent / "historical-backfill"

    assert launcher.exists()
    assert launcher.stat().st_mode & 0o111
