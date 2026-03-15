from datetime import datetime

from peewee import SqliteDatabase


def test_cli_package_does_not_eagerly_import_guild_sites_module():
    import importlib
    import sys

    sys.modules.pop("src.apps.cli", None)
    sys.modules.pop("src.apps.cli.guild_sites", None)

    importlib.import_module("src.apps.cli")

    assert "src.apps.cli.guild_sites" not in sys.modules


def patch_cli_runtime(monkeypatch, tmp_path):
    from src.core.config import BotConfig, MariaDBConfig
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema
    from src.apps.cli import guild_sites as guild_sites_cli

    database = SqliteDatabase(
        str(tmp_path / "guild-site-cli.db"),
        check_same_thread=False,
    )

    def fake_load_config(path=None):
        return BotConfig(
            token="test-token",
            log_level="INFO",
            central_database_path="central.db",
            sync_interval_hours=24,
            results_lobby_poll_seconds=2,
            mariadb=MariaDBConfig(
                database="openfront",
                user="openfront",
                password="change-me",
            ),
        )

    def fake_init_shared_database(_config, *, connect=True):
        shared_database.initialize(database)
        bootstrap_shared_schema(database)
        if connect:
            database.connect(reuse_if_open=True)
        return database

    monkeypatch.setattr(guild_sites_cli, "load_config", fake_load_config)
    monkeypatch.setattr(guild_sites_cli, "init_shared_database", fake_init_shared_database)
    return guild_sites_cli


def test_guild_site_cli_supports_full_crud_flow(monkeypatch, tmp_path, capsys):
    guild_sites_cli = patch_cli_runtime(monkeypatch, tmp_path)

    assert (
        guild_sites_cli.main(
            [
                "create",
                "--slug",
                "north-guild",
                "--subdomain",
                "north",
                "--display-name",
                "North Guild",
                "--clan-tag",
                "NRTH",
                "--clan-tag",
                "NTH",
                "--discord-guild-id",
                "123",
            ]
        )
        == 0
    )
    create_output = capsys.readouterr().out
    assert "north-guild" in create_output
    assert "North Guild" in create_output

    assert guild_sites_cli.main(["list"]) == 0
    list_output = capsys.readouterr().out
    assert "north-guild" in list_output
    assert "active" in list_output.lower()

    assert guild_sites_cli.main(["show", "--slug", "north-guild"]) == 0
    show_output = capsys.readouterr().out
    assert "NRTH" in show_output
    assert "NTH" in show_output

    assert (
        guild_sites_cli.main(
            [
                "update",
                "--slug",
                "north-guild",
                "--display-name",
                "North Wolves",
                "--new-subdomain",
                "wolves",
                "--clan-tag",
                "WLF",
            ]
        )
        == 0
    )
    update_output = capsys.readouterr().out
    assert "North Wolves" in update_output
    assert "wolves" in update_output

    assert guild_sites_cli.main(["deactivate", "--subdomain", "wolves"]) == 0
    deactivate_output = capsys.readouterr().out
    assert "inactive" in deactivate_output.lower()

    assert guild_sites_cli.main(["activate", "--subdomain", "wolves"]) == 0
    activate_output = capsys.readouterr().out
    assert "active" in activate_output.lower()

    assert guild_sites_cli.main(["delete", "--subdomain", "wolves", "--confirm"]) == 0
    delete_output = capsys.readouterr().out
    assert "deleted" in delete_output.lower()


def test_guild_site_cli_reports_selector_and_confirmation_errors(
    monkeypatch,
    tmp_path,
    capsys,
):
    guild_sites_cli = patch_cli_runtime(monkeypatch, tmp_path)

    assert (
        guild_sites_cli.main(
            [
                "show",
                "--id",
                "1",
                "--slug",
                "north-guild",
            ]
        )
        == 1
    )
    selector_error = capsys.readouterr().err
    assert "exactly one" in selector_error

    assert (
        guild_sites_cli.main(
            [
                "create",
                "--slug",
                "north-guild",
                "--subdomain",
                "north",
                "--display-name",
                "North Guild",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert guild_sites_cli.main(["delete", "--slug", "north-guild"]) == 1
    delete_error = capsys.readouterr().err
    assert "confirmation" in delete_error.lower()


def test_guild_site_cli_splits_comma_separated_clan_tags(
    monkeypatch,
    tmp_path,
    capsys,
):
    guild_sites_cli = patch_cli_runtime(monkeypatch, tmp_path)

    assert (
        guild_sites_cli.main(
            [
                "create",
                "--slug",
                "north-guild",
                "--subdomain",
                "north",
                "--display-name",
                "North Guild",
                "--clan-tag",
                "NRTH,NTH",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert guild_sites_cli.main(["show", "--slug", "north-guild"]) == 0
    show_output = capsys.readouterr().out
    assert "NRTH" in show_output
    assert "NTH" in show_output
    assert "NRTH,NTH" not in show_output


def test_guild_site_cli_can_refresh_guild_aggregates(
    monkeypatch,
    tmp_path,
    capsys,
):
    from src.data.shared.models import GameParticipant, Guild, GuildPlayerAggregate, ObservedGame

    guild_sites_cli = patch_cli_runtime(monkeypatch, tmp_path)

    assert (
        guild_sites_cli.main(
            [
                "create",
                "--slug",
                "north-guild",
                "--subdomain",
                "north",
                "--display-name",
                "North Guild",
                "--clan-tag",
                "NRTH",
            ]
        )
        == 0
    )
    capsys.readouterr()

    guild = Guild.get(Guild.slug == "north-guild")
    game = ObservedGame.create(
        openfront_game_id="game-1",
        game_type="PUBLIC",
        mode_name="Team",
        player_teams="Duos",
        total_player_count=8,
        ended_at=datetime(2026, 3, 10, 12, 0, 0),
    )
    GameParticipant.create(
        game=game,
        guild=guild,
        raw_username="[NRTH] Temujin",
        normalized_username="temujin",
        raw_clan_tag="NRTH",
        effective_clan_tag="NRTH",
        clan_tag_source="session",
        client_id="c1",
        did_win=1,
        attack_troops_total=250,
        attack_action_count=3,
        donated_troops_total=125,
        donated_gold_total=50,
        donation_action_count=2,
    )
    GuildPlayerAggregate.create(
        guild=guild,
        normalized_username="stale-user",
        display_username="Stale User",
        last_observed_clan_tag="NRTH",
    )

    assert guild_sites_cli.main(["refresh-aggregates", "--slug", "north-guild"]) == 0
    refresh_output = capsys.readouterr().out
    assert "north-guild" in refresh_output
    assert "refreshed_players=1" in refresh_output

    aggregates = list(
        GuildPlayerAggregate.select().where(GuildPlayerAggregate.guild == guild)
    )
    assert len(aggregates) == 1
    assert aggregates[0].normalized_username == "temujin"
