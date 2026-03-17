from __future__ import annotations

from datetime import datetime, timezone

from peewee import (
    AutoField,
    BigIntegerField,
    CharField,
    DateTimeField,
    FloatField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
)

from ..database import shared_database


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SharedBaseModel(Model):
    created_at = DateTimeField(default=utcnow_naive)
    updated_at = DateTimeField(default=utcnow_naive)

    def save(self, *args, **kwargs):  # type: ignore[override]
        self.updated_at = utcnow_naive()
        return super().save(*args, **kwargs)

    class Meta:
        database = shared_database


class LongTextField(TextField):
    field_type = "LONGTEXT"


class Guild(SharedBaseModel):
    id = AutoField()
    slug = CharField(unique=True)
    subdomain = CharField(unique=True)
    display_name = CharField()
    is_active = IntegerField(default=1)
    discord_guild_id = BigIntegerField(null=True, unique=True)

    class Meta:
        table_name = "guilds"


class GuildClanTag(SharedBaseModel):
    id = AutoField()
    guild = ForeignKeyField(Guild, backref="clan_tags", on_delete="CASCADE")
    tag_text = CharField()

    class Meta:
        table_name = "guild_clan_tags"
        indexes = ((("guild", "tag_text"), True),)


class SiteUser(SharedBaseModel):
    id = AutoField()
    discord_user_id = BigIntegerField(unique=True)
    discord_username = CharField()
    discord_global_name = CharField(null=True)
    discord_avatar_hash = CharField(null=True)
    last_login_at = DateTimeField(null=True)

    class Meta:
        table_name = "site_users"


class Player(SharedBaseModel):
    id = AutoField()
    openfront_player_id = CharField(unique=True, null=True)
    canonical_username = CharField()
    canonical_normalized_username = CharField()
    is_linked = IntegerField(default=0)

    class Meta:
        table_name = "players"


class PlayerAlias(SharedBaseModel):
    id = AutoField()
    player = ForeignKeyField(Player, backref="aliases", on_delete="CASCADE")
    raw_username = CharField()
    normalized_username = CharField()
    source = CharField()

    class Meta:
        table_name = "player_aliases"
        indexes = ((("player", "raw_username"), True),)


class PlayerLink(SharedBaseModel):
    id = AutoField()
    site_user = ForeignKeyField(SiteUser, backref="player_links", unique=True)
    player = ForeignKeyField(Player, backref="site_links", unique=True)
    linked_at = DateTimeField(default=utcnow_naive)

    class Meta:
        table_name = "player_links"


class BackfillRun(SharedBaseModel):
    id = AutoField()
    requested_start = DateTimeField()
    requested_end = DateTimeField()
    status = CharField(default="pending")
    started_at = DateTimeField(null=True)
    completed_at = DateTimeField(null=True)
    last_error = TextField(null=True)
    discovered_count = IntegerField(default=0)
    cached_count = IntegerField(default=0)
    ingested_count = IntegerField(default=0)
    matched_count = IntegerField(default=0)
    failed_count = IntegerField(default=0)
    skipped_known_count = IntegerField(default=0)
    replayed_count = IntegerField(default=0)
    cache_failure_count = IntegerField(default=0)
    refreshed_guild_count = IntegerField(default=0)

    class Meta:
        table_name = "backfill_runs"


class OpenFrontRateLimitState(SharedBaseModel):
    id = IntegerField(primary_key=True)
    lease_owner = CharField(null=True)
    lease_expires_at = DateTimeField(null=True)
    cooldown_until = DateTimeField(null=True)
    cooldown_reason = TextField(null=True)

    class Meta:
        table_name = "openfront_rate_limit_state"


class BackfillCursor(SharedBaseModel):
    id = AutoField()
    run = ForeignKeyField(BackfillRun, backref="cursors", on_delete="CASCADE")
    source_type = CharField()
    source_key = CharField(default="")
    cursor_started_at = DateTimeField(null=True)
    cursor_ended_at = DateTimeField(null=True)
    next_started_at = DateTimeField(null=True)
    next_offset = IntegerField(default=0)
    status = CharField(default="pending")
    last_error = TextField(null=True)

    class Meta:
        table_name = "backfill_cursors"
        indexes = ((("run", "source_type", "source_key"), True),)


class CachedOpenFrontGame(SharedBaseModel):
    id = AutoField()
    openfront_game_id = CharField(unique=True)
    game_type = CharField(null=True)
    mode_name = CharField(null=True)
    started_at = DateTimeField(null=True)
    ended_at = DateTimeField(null=True)
    fetched_at = DateTimeField(default=utcnow_naive)
    payload_json = LongTextField()
    turn_payload_json = LongTextField(null=True)

    class Meta:
        table_name = "cached_openfront_games"


class BackfillGame(SharedBaseModel):
    id = AutoField()
    run = ForeignKeyField(BackfillRun, backref="games", on_delete="CASCADE")
    openfront_game_id = CharField()
    source_type = CharField()
    started_at = DateTimeField(null=True)
    status = CharField(default="pending")
    attempts = IntegerField(default=0)
    matched_guild_count = IntegerField(default=0)
    last_error = TextField(null=True)
    cache_entry = ForeignKeyField(
        CachedOpenFrontGame,
        backref="backfill_games",
        null=True,
        on_delete="SET NULL",
    )

    class Meta:
        table_name = "backfill_games"
        indexes = ((("run", "openfront_game_id"), True),)


class ObservedGame(SharedBaseModel):
    id = AutoField()
    openfront_game_id = CharField(unique=True)
    game_type = CharField()
    map_name = CharField(null=True)
    mode_name = CharField(null=True)
    player_teams = CharField(null=True)
    num_teams = IntegerField(null=True)
    total_player_count = IntegerField(null=True)
    started_at = DateTimeField(null=True)
    ended_at = DateTimeField(null=True)
    duration_seconds = IntegerField(null=True)
    raw_payload = TextField(null=True)

    class Meta:
        table_name = "observed_games"


class GameParticipant(SharedBaseModel):
    id = AutoField()
    game = ForeignKeyField(ObservedGame, backref="participants", on_delete="CASCADE")
    guild = ForeignKeyField(Guild, backref="participants", on_delete="CASCADE")
    raw_username = CharField()
    normalized_username = CharField()
    raw_clan_tag = CharField(null=True)
    effective_clan_tag = CharField(null=True)
    clan_tag_source = CharField()
    client_id = CharField(default="")
    did_win = IntegerField(default=0)
    attack_troops_total = BigIntegerField(default=0)
    attack_action_count = IntegerField(default=0)
    donated_troops_total = BigIntegerField(default=0)
    donated_gold_total = BigIntegerField(default=0)
    donation_action_count = IntegerField(default=0)
    player = ForeignKeyField(Player, backref="participants", null=True)

    class Meta:
        table_name = "game_participants"
        indexes = ((("guild", "game", "normalized_username", "client_id"), True),)


class GuildPlayerAggregate(SharedBaseModel):
    id = AutoField()
    guild = ForeignKeyField(Guild, backref="player_aggregates", on_delete="CASCADE")
    player = ForeignKeyField(Player, backref="guild_aggregates", null=True)
    normalized_username = CharField()
    display_username = CharField()
    last_observed_clan_tag = CharField(null=True)
    win_count = IntegerField(default=0)
    game_count = IntegerField(default=0)
    team_win_count = IntegerField(default=0)
    team_game_count = IntegerField(default=0)
    ffa_win_count = IntegerField(default=0)
    ffa_game_count = IntegerField(default=0)
    donated_troops_total = BigIntegerField(default=0)
    donated_gold_total = BigIntegerField(default=0)
    donation_action_count = IntegerField(default=0)
    attack_troops_total = BigIntegerField(default=0)
    attack_action_count = IntegerField(default=0)
    support_bonus = FloatField(default=0)
    team_score = FloatField(default=0)
    ffa_score = FloatField(default=0)
    role_label = CharField(null=True)
    team_recent_game_count_30d = IntegerField(default=0)
    ffa_recent_game_count_30d = IntegerField(default=0)
    last_team_game_at = DateTimeField(null=True)
    last_ffa_game_at = DateTimeField(null=True)
    last_game_at = DateTimeField(null=True)

    class Meta:
        table_name = "guild_player_aggregates"
        indexes = ((("guild", "normalized_username"), True),)


class GuildPlayerDailySnapshot(SharedBaseModel):
    id = AutoField()
    guild = ForeignKeyField(Guild, backref="daily_snapshots", on_delete="CASCADE")
    player = ForeignKeyField(Player, backref="daily_snapshots", null=True)
    normalized_username = CharField()
    display_username = CharField(null=True)
    snapshot_date = CharField()
    scope = CharField()
    score = FloatField(default=0)
    wins = IntegerField(default=0)
    games = IntegerField(default=0)
    win_rate = FloatField(default=0)

    class Meta:
        table_name = "guild_player_daily_snapshots"
        indexes = ((("guild", "normalized_username", "snapshot_date", "scope"), True),)


class GuildDailyBenchmark(SharedBaseModel):
    id = AutoField()
    guild = ForeignKeyField(Guild, backref="daily_benchmarks", on_delete="CASCADE")
    snapshot_date = CharField()
    scope = CharField()
    median_score = FloatField(default=0)
    leader_score = FloatField(default=0)

    class Meta:
        table_name = "guild_daily_benchmarks"
        indexes = ((("guild", "snapshot_date", "scope"), True),)


class GuildWeeklyPlayerScore(SharedBaseModel):
    id = AutoField()
    guild = ForeignKeyField(Guild, backref="weekly_scores", on_delete="CASCADE")
    player = ForeignKeyField(Player, backref="weekly_scores", null=True)
    normalized_username = CharField()
    display_username = CharField()
    week_start = CharField()
    scope = CharField()
    score = FloatField(default=0)
    wins = IntegerField(default=0)
    games = IntegerField(default=0)
    win_rate = FloatField(default=0)

    class Meta:
        table_name = "guild_weekly_player_scores"
        indexes = ((("guild", "normalized_username", "week_start", "scope"), True),)


class GuildRecentGameResult(SharedBaseModel):
    id = AutoField()
    guild = ForeignKeyField(Guild, backref="recent_game_results", on_delete="CASCADE")
    openfront_game_id = CharField()
    game = ForeignKeyField(ObservedGame, backref="recent_results", null=True, on_delete="SET NULL")
    ended_at = DateTimeField(null=True)
    mode = CharField()
    result = CharField()
    map_name = CharField(null=True)
    format_label = CharField()
    team_distribution = CharField(null=True)
    replay_link = CharField()
    map_thumbnail_url = CharField(null=True)
    guild_team_players_json = LongTextField(null=True)
    winner_players_json = LongTextField(null=True)

    class Meta:
        table_name = "guild_recent_game_results"
        indexes = ((("guild", "openfront_game_id"), True),)


class GuildComboAggregate(SharedBaseModel):
    id = AutoField()
    guild = ForeignKeyField(Guild, backref="combo_aggregates", on_delete="CASCADE")
    format_slug = CharField()
    roster_key = CharField()
    games_together = IntegerField(default=0)
    wins_together = IntegerField(default=0)
    win_rate = FloatField(default=0)
    is_confirmed = IntegerField(default=0)
    first_game_at = DateTimeField(null=True)
    last_game_at = DateTimeField(null=True)
    last_win_at = DateTimeField(null=True)

    class Meta:
        table_name = "guild_combo_aggregates"
        indexes = ((("guild", "format_slug", "roster_key"), True),)


class GuildComboMember(SharedBaseModel):
    id = AutoField()
    combo = ForeignKeyField(
        GuildComboAggregate,
        backref="members",
        on_delete="CASCADE",
    )
    player = ForeignKeyField(Player, backref="combo_memberships", null=True)
    normalized_username = CharField()
    display_username = CharField()
    slot_index = IntegerField(default=0)

    class Meta:
        table_name = "guild_combo_members"
        indexes = ((("combo", "slot_index"), True),)


class GuildPlayerBadge(SharedBaseModel):
    id = AutoField()
    guild = ForeignKeyField(Guild, backref="player_badges", on_delete="CASCADE")
    player = ForeignKeyField(Player, backref="guild_badges", null=True)
    normalized_username = CharField()
    badge_code = CharField()
    badge_level = CharField(null=True)
    earned_at = DateTimeField()
    metadata_json = TextField(null=True)

    class Meta:
        table_name = "guild_player_badges"
        indexes = ((("guild", "normalized_username", "badge_code", "badge_level"), True),)


SHARED_MODELS = (
    Guild,
    GuildClanTag,
    SiteUser,
    Player,
    PlayerAlias,
    PlayerLink,
    BackfillRun,
    OpenFrontRateLimitState,
    BackfillCursor,
    CachedOpenFrontGame,
    BackfillGame,
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
)
