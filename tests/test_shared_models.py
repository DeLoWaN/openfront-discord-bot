from datetime import datetime

from peewee import IntegrityError, SqliteDatabase


def test_shared_models_create_expected_schema():
    from src.data.database import shared_database
    from src.data.shared.models import (
        BackfillCursor,
        BackfillGame,
        BackfillRun,
        CachedOpenFrontGame,
        GameParticipant,
        GuildDailyBenchmark,
        GuildComboAggregate,
        GuildComboMember,
        GuildPlayerDailySnapshot,
        Guild,
        GuildClanTag,
        GuildPlayerAggregate,
        GuildPlayerBadge,
        GuildRecentGameResult,
        GuildWeeklyPlayerScore,
        ObservedGame,
        Player,
        PlayerAlias,
        PlayerLink,
        SiteUser,
    )

    database = SqliteDatabase(":memory:")
    shared_database.initialize(database)
    database.bind(
        [
            Guild,
            GuildClanTag,
            SiteUser,
            Player,
            PlayerAlias,
            PlayerLink,
            BackfillRun,
            BackfillCursor,
            BackfillGame,
            CachedOpenFrontGame,
            ObservedGame,
            GameParticipant,
            GuildPlayerDailySnapshot,
            GuildDailyBenchmark,
            GuildWeeklyPlayerScore,
            GuildRecentGameResult,
            GuildPlayerAggregate,
            GuildComboAggregate,
            GuildComboMember,
            GuildPlayerBadge,
        ]
    )
    database.connect(reuse_if_open=True)
    database.create_tables(
        [
            Guild,
            GuildClanTag,
            SiteUser,
            Player,
            PlayerAlias,
            PlayerLink,
            BackfillRun,
            BackfillCursor,
            BackfillGame,
            CachedOpenFrontGame,
            ObservedGame,
            GameParticipant,
            GuildPlayerDailySnapshot,
            GuildDailyBenchmark,
            GuildWeeklyPlayerScore,
            GuildRecentGameResult,
            GuildPlayerAggregate,
            GuildComboAggregate,
            GuildComboMember,
            GuildPlayerBadge,
        ]
    )

    guild = Guild.create(
        slug="north",
        subdomain="north",
        display_name="North Guild",
        is_active=1,
        discord_guild_id=123,
    )
    GuildClanTag.create(guild=guild, tag_text="NRTH")
    user = SiteUser.create(discord_user_id=42, discord_username="damien")
    player = Player.create(
        openfront_player_id="player-1",
        canonical_username="Ace",
        canonical_normalized_username="ace",
        is_linked=1,
    )
    PlayerAlias.create(
        player=player,
        raw_username="Ace",
        normalized_username="ace",
        source="linked_history",
    )
    PlayerLink.create(site_user=user, player=player, linked_at=datetime(2026, 3, 11))
    run = BackfillRun.create(
        requested_start=datetime(2026, 3, 1),
        requested_end=datetime(2026, 3, 31),
        status="running",
    )
    cursor = BackfillCursor.create(
        run=run,
        source_type="team",
        source_key="NRTH",
        cursor_started_at=datetime(2026, 3, 1),
        cursor_ended_at=datetime(2026, 3, 3),
        next_offset=0,
        status="running",
    )
    cache = CachedOpenFrontGame.create(
        openfront_game_id="game-1",
        game_type="PUBLIC",
        mode_name="Team",
        started_at=datetime(2026, 3, 2),
        payload_json='{"info":{"gameID":"game-1"}}',
    )
    queued_game = BackfillGame.create(
        run=run,
        openfront_game_id="game-1",
        source_type="team",
        started_at=datetime(2026, 3, 2),
        status="pending",
        cache_entry=cache,
    )
    game = ObservedGame.create(
        openfront_game_id="game-1",
        game_type="PUBLIC",
        map_name="Europe",
        mode_name="Team",
    )
    GameParticipant.create(
        game=game,
        guild=guild,
        raw_username="Ace",
        normalized_username="ace",
        raw_clan_tag="NRTH",
        effective_clan_tag="NRTH",
        clan_tag_source="api",
        client_id="client-1",
        did_win=1,
    )
    aggregate = GuildPlayerAggregate.create(
        guild=guild,
        player=player,
        normalized_username="ace",
        display_username="Ace",
        win_count=1,
        game_count=1,
    )
    daily_snapshot = GuildPlayerDailySnapshot.create(
        guild=guild,
        normalized_username="ace",
        snapshot_date="2026-03-16",
        scope="team",
        score=100.0,
        wins=1,
        games=1,
        win_rate=1.0,
    )
    daily_benchmark = GuildDailyBenchmark.create(
        guild=guild,
        snapshot_date="2026-03-16",
        scope="team",
        median_score=80.0,
        leader_score=100.0,
    )
    weekly_score = GuildWeeklyPlayerScore.create(
        guild=guild,
        normalized_username="ace",
        display_username="Ace",
        week_start="2026-03-16",
        scope="team",
        score=100.0,
        wins=1,
        games=1,
        win_rate=1.0,
    )
    recent_game = GuildRecentGameResult.create(
        guild=guild,
        openfront_game_id="game-1",
        ended_at=datetime(2026, 3, 16, 10, 0, 0),
        mode="Team",
        result="win",
        map_name="Europe",
        format_label="Duos",
        team_distribution="6 teams of 2 (Duos)",
        replay_link="https://openfront.io/w1/game/game-1",
    )
    combo = GuildComboAggregate.create(
        guild=guild,
        format_slug="duo",
        roster_key="ace|bolt",
        games_together=5,
        wins_together=4,
        win_rate=0.8,
        is_confirmed=1,
    )
    GuildComboMember.create(
        combo=combo,
        player=player,
        normalized_username="ace",
        display_username="Ace",
        slot_index=0,
    )
    badge = GuildPlayerBadge.create(
        guild=guild,
        player=player,
        normalized_username="ace",
        badge_code="team-grinder",
        badge_level="Bronze",
        earned_at=datetime(2026, 3, 12),
    )

    assert getattr(shared_database, "obj", None) is database
    assert aggregate.guild_id == guild.id
    assert daily_snapshot.guild_id == guild.id
    assert daily_benchmark.guild_id == guild.id
    assert weekly_score.guild_id == guild.id
    assert recent_game.guild_id == guild.id
    assert aggregate.player_id == player.id
    assert cursor.run_id == run.id
    assert queued_game.cache_entry_id == cache.id
    assert combo.guild_id == guild.id
    assert badge.player_id == player.id

    try:
        BackfillGame.create(
            run=run,
            openfront_game_id="game-1",
            source_type="ffa",
            status="pending",
        )
    except IntegrityError:
        duplicate_blocked = True
    else:
        duplicate_blocked = False

    assert duplicate_blocked is True
