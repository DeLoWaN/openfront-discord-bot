from datetime import datetime, timedelta

from peewee import SqliteDatabase


def setup_shared_database(tmp_path):
    from src.data.database import shared_database
    from src.data.shared.schema import bootstrap_shared_schema

    database = SqliteDatabase(
        str(tmp_path / "ingestion.db"),
        check_same_thread=False,
    )
    shared_database.initialize(database)
    bootstrap_shared_schema(database)
    return database


def test_resolve_effective_clan_tag_prefers_api_then_username_fallback():
    from src.services.openfront_ingestion import resolve_effective_clan_tag

    api_resolution = resolve_effective_clan_tag("nu", "[ALT] Ace")
    username_resolution = resolve_effective_clan_tag(None, "Ace [deer] Runner")
    empty_resolution = resolve_effective_clan_tag("", "Ace")

    assert api_resolution.effective_tag == "NU"
    assert api_resolution.source == "api"
    assert username_resolution.effective_tag == "DEER"
    assert username_resolution.source == "username"
    assert empty_resolution.effective_tag is None
    assert empty_resolution.source == "missing"


def test_infer_team_count_uses_explicit_numeric_and_named_team_sizes():
    from src.services.openfront_ingestion import _infer_team_count

    assert _infer_team_count(num_teams=11, player_teams="Duos", total_player_count=60) == 11
    assert _infer_team_count(num_teams=None, player_teams="5", total_player_count=15) == 5
    assert _infer_team_count(num_teams=None, player_teams="Duos", total_player_count=24) == 12
    assert _infer_team_count(num_teams=None, player_teams="Trios", total_player_count=24) == 8
    assert _infer_team_count(num_teams=None, player_teams="Quads", total_player_count=24) == 6
    assert _infer_team_count(num_teams=None, player_teams="Duos", total_player_count=25) is None
    assert _infer_team_count(num_teams=None, player_teams=None, total_player_count=24) is None


def test_team_difficulty_weight_grows_monotonically_past_ten_teams():
    from src.services.openfront_ingestion import _team_difficulty_weight

    four_team = _team_difficulty_weight(4, players_per_team=4, tracked_guild_teammates=4)
    ten_team = _team_difficulty_weight(
        10, players_per_team=4, tracked_guild_teammates=4
    )
    sixty_team = _team_difficulty_weight(
        60, players_per_team=4, tracked_guild_teammates=4
    )

    assert four_team > 1.0
    assert ten_team > four_team
    assert sixty_team > ten_team


def test_team_difficulty_weight_increases_for_smaller_teams():
    from src.services.openfront_ingestion import _team_difficulty_weight

    quads = _team_difficulty_weight(8, players_per_team=4, tracked_guild_teammates=4)
    duos = _team_difficulty_weight(8, players_per_team=2, tracked_guild_teammates=2)

    assert duos > quads


def test_team_difficulty_weight_increases_for_lower_tracked_guild_presence():
    from src.services.openfront_ingestion import _team_difficulty_weight

    full_guild_team = _team_difficulty_weight(
        8, players_per_team=4, tracked_guild_teammates=4
    )
    partial_guild_team = _team_difficulty_weight(
        8, players_per_team=4, tracked_guild_teammates=2
    )

    assert partial_guild_team > full_guild_team


def test_team_game_points_reward_wins_without_subtracting_losses():
    from src.services.openfront_ingestion import _team_game_points

    loss_points = _team_game_points(
        inferred_num_teams=12,
        players_per_team=2,
        tracked_guild_teammates=1,
        did_win=False,
    )
    win_points = _team_game_points(
        inferred_num_teams=12,
        players_per_team=2,
        tracked_guild_teammates=1,
        did_win=True,
    )

    assert loss_points > 0.0
    assert win_points > loss_points


def test_no_spawn_detection_requires_explicit_zero_activity_evidence(tmp_path):
    from src.data.shared.models import GameParticipant, ObservedGame
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import _participant_is_no_spawn

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )
    game = ObservedGame.create(
        openfront_game_id="unknown-activity",
        game_type="PUBLIC",
        mode_name="Team",
        num_teams=6,
        total_player_count=12,
        ended_at=datetime(2026, 3, 1, 12, 0, 0),
    )
    participant = GameParticipant.create(
        game=game,
        guild=guild,
        raw_username="Veteran",
        normalized_username="veteran",
        raw_clan_tag="NU",
        effective_clan_tag="NU",
        clan_tag_source="api",
        client_id="unknown-activity",
        did_win=1,
    )

    assert _participant_is_no_spawn(participant) is False
    assert _participant_is_no_spawn(
        participant,
        {"stats": {"gold": ["0"], "attacks": ["0"], "conquests": ["0", "0", "0"]}},
    ) is True


def test_ingest_game_payload_persists_guild_relevant_participants_and_aggregates(
    tmp_path,
):
    from src.data.shared.models import GameParticipant, GuildPlayerAggregate, ObservedGame
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import (
        ingest_game_payload,
        refresh_guild_player_aggregates,
    )

    setup_shared_database(tmp_path)
    north = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )
    deer = provision_guild_site(
        slug="deer",
        subdomain="deer",
        display_name="Deer",
        clan_tags=["DEER"],
    )

    payload = {
        "info": {
            "gameID": "game-1",
            "config": {
                "gameType": "Public",
                "gameMode": "Team",
                "gameMap": "World",
                "playerTeams": "Duos",
            },
            "winner": ["team", "Team 1", "c1", "c2"],
            "start": 1763338803169,
            "end": 1763339806340,
            "players": [
                {"clientID": "c1", "username": "[NU] Ace", "clanTag": None},
                {"clientID": "c2", "username": "Bolt", "clanTag": "NU"},
                {"clientID": "c3", "username": "Cedar [DEER]", "clanTag": ""},
                {"clientID": "c4", "username": "Enemy", "clanTag": "XYZ"},
            ],
        }
    }

    summary = ingest_game_payload(payload)
    refresh_guild_player_aggregates(north)
    refresh_guild_player_aggregates(deer)

    north_aggregates = list(
        GuildPlayerAggregate.select().where(GuildPlayerAggregate.guild == north)
    )
    deer_aggregates = list(
        GuildPlayerAggregate.select().where(GuildPlayerAggregate.guild == deer)
    )

    assert summary.matched_guild_ids == {north.id, deer.id}
    assert ObservedGame.select().count() == 1
    assert GameParticipant.select().count() == 3
    assert {row.display_username: row.win_count for row in north_aggregates} == {
        "Ace": 1,
        "Bolt": 1,
    }
    assert {row.display_username: row.win_count for row in deer_aggregates} == {
        "Cedar [DEER]": 0
    }


def test_ingest_game_payload_refreshes_leaderboard_aggregates_immediately(tmp_path):
    from src.services.guild_sites import provision_guild_site
    from src.services.guild_stats_api import build_leaderboard_response
    from src.services.openfront_ingestion import ingest_game_payload

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    ingest_game_payload(
        {
            "info": {
                "gameID": "instant-refresh-1",
                "config": {"gameType": "Public", "gameMode": "Team"},
                "winner": ["team", "Team 1", "c1"],
                "players": [
                    {"clientID": "c1", "username": "[NU] Ace", "clanTag": None},
                ],
            }
        }
    )

    rows = build_leaderboard_response(guild, "team")["rows"]

    assert len(rows) == 1
    assert rows[0]["normalized_username"] == "ace"
    assert rows[0]["win_count"] == 1


def test_backfill_public_games_fetches_and_ingests_matching_games(tmp_path):
    from src.data.shared.models import GameParticipant, ObservedGame
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import backfill_public_games

    setup_shared_database(tmp_path)
    provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    class FakeClient:
        async def fetch_public_games(self, start, end):
            return [{"game": "game-1"}, {"game": "game-2"}]

        async def fetch_game(self, game_id):
            if game_id == "game-1":
                return {
                    "info": {
                        "gameID": game_id,
                        "config": {"gameType": "Public", "gameMode": "Team"},
                        "winner": ["team", "Team 1", "c1"],
                        "players": [
                            {"clientID": "c1", "username": "[NU] Ace", "clanTag": None}
                        ],
                    }
                }
            return {
                "info": {
                    "gameID": game_id,
                    "config": {"gameType": "Public", "gameMode": "Team"},
                    "winner": ["team", "Team 2", "c9"],
                    "players": [
                        {"clientID": "c9", "username": "Enemy", "clanTag": "XYZ"}
                    ],
                }
            }

    summary = backfill_public_games(
        FakeClient(),
        start=datetime(2026, 3, 1),
        end=datetime(2026, 3, 11),
    )

    assert summary.games_seen == 2
    assert summary.games_ingested == 1
    assert ObservedGame.select().count() == 1
    assert GameParticipant.select().count() == 1


def test_refresh_guild_player_aggregates_merges_tracked_tag_variants_only(
    tmp_path,
):
    from src.data.shared.models import GuildPlayerAggregate
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import (
        ingest_game_payload,
        refresh_guild_player_aggregates,
    )

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU", "ALT"],
    )

    ingest_game_payload(
        {
            "info": {
                "gameID": "merge-1",
                "config": {"gameType": "Public", "gameMode": "Free For All"},
                "winner": ["player", "c1"],
                "players": [
                    {"clientID": "c1", "username": "[NU] Temujin", "clanTag": "NU"},
                    {"clientID": "c2", "username": "[ALT] Temujin", "clanTag": "ALT"},
                    {
                        "clientID": "c3",
                        "username": "[XYZ] Temujin",
                        "clanTag": "NU",
                    },
                ],
            }
        }
    )

    aggregates = refresh_guild_player_aggregates(guild)

    assert len(aggregates) == 2
    merged = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "temujin"
    )
    untracked = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "[xyz] temujin"
    )
    assert merged.display_username == "Temujin"
    assert merged.game_count == 2
    assert merged.win_count == 1
    assert untracked.display_username == "[XYZ] Temujin"
    assert untracked.game_count == 1


def test_refresh_guild_player_aggregates_rewards_high_participation_over_tiny_perfect_samples(
    tmp_path,
):
    from src.data.shared.models import GameParticipant, GuildPlayerAggregate, ObservedGame
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import refresh_guild_player_aggregates

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    def create_participant(
        *,
        game_id: str,
        username: str,
        did_win: int,
        ended_at: datetime,
        num_teams: int = 4,
    ) -> None:
        game = ObservedGame.create(
            openfront_game_id=game_id,
            game_type="PUBLIC",
            mode_name="Team",
            num_teams=num_teams,
            total_player_count=num_teams * 2,
            ended_at=ended_at,
        )
        GameParticipant.create(
            game=game,
            guild=guild,
            raw_username=username,
            normalized_username=username.lower(),
            raw_clan_tag="NU",
            effective_clan_tag="NU",
            clan_tag_source="api",
            client_id=game_id,
            did_win=did_win,
        )

    for index in range(120):
        create_participant(
            game_id=f"veteran-{index}",
            username="Veteran",
            did_win=1 if index < 48 else 0,
            ended_at=datetime(2026, 3, 1, 12, 0, 0),
            num_teams=18,
        )
    for index in range(10):
        create_participant(
            game_id=f"sprinter-{index}",
            username="Sprinter",
            did_win=1,
            ended_at=datetime(2026, 3, 1, 12, 0, 0),
            num_teams=18,
        )

    refresh_guild_player_aggregates(guild)

    veteran = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "veteran"
    )
    sprinter = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "sprinter"
    )

    assert veteran.team_game_count == 120
    assert sprinter.team_game_count == 10
    assert veteran.team_score > sprinter.team_score
    assert veteran.team_score > 0
    assert sprinter.team_score > 0


def test_refresh_guild_player_aggregates_tracks_recent_activity_without_score_decay(
    tmp_path,
):
    from src.data.shared.models import GameParticipant, GuildPlayerAggregate, ObservedGame
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import refresh_guild_player_aggregates

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    old_time = datetime(2026, 1, 1, 12, 0, 0)
    recent_times = [
        datetime(2026, 3, 14, 12, 0, 0),
        datetime(2026, 3, 10, 12, 0, 0),
    ]

    for index, ended_at in enumerate([old_time, *recent_times]):
        game = ObservedGame.create(
            openfront_game_id=f"team-recency-{index}",
            game_type="PUBLIC",
            mode_name="Team",
            num_teams=12,
            ended_at=ended_at,
        )
        GameParticipant.create(
            game=game,
            guild=guild,
            raw_username="Temujin",
            normalized_username="temujin",
            raw_clan_tag="NU",
            effective_clan_tag="NU",
            clan_tag_source="api",
            client_id=f"team-recency-{index}",
            did_win=1 if index == 0 else 0,
        )

    refresh_guild_player_aggregates(guild)

    temujin = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "temujin"
    )

    assert temujin.ffa_game_count == 0
    assert temujin.team_game_count == 3
    assert temujin.team_recent_game_count_30d == 2
    assert temujin.last_team_game_at == recent_times[0]
    assert temujin.team_score > 0


def test_refresh_guild_player_aggregates_values_larger_team_lobbies_more_highly(tmp_path):
    from src.data.shared.models import GameParticipant, GuildPlayerAggregate, ObservedGame
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import refresh_guild_player_aggregates

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    for username, num_teams in (("TenTeams", 10), ("SixtyTeams", 60)):
        game = ObservedGame.create(
            openfront_game_id=f"{username}-{num_teams}",
            game_type="PUBLIC",
            mode_name="Team",
            num_teams=num_teams,
            total_player_count=num_teams * 2,
            ended_at=datetime(2026, 3, 1, 12, 0, 0),
        )
        GameParticipant.create(
            game=game,
            guild=guild,
            raw_username=username,
            normalized_username=username.lower(),
            raw_clan_tag="NU",
            effective_clan_tag="NU",
            clan_tag_source="api",
            client_id=f"{username}-{num_teams}",
            did_win=1,
        )

    refresh_guild_player_aggregates(guild)

    ten_team = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "tenteams"
    )
    sixty_team = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "sixtyteams"
    )

    assert sixty_team.team_score > ten_team.team_score


def test_ingest_team_payload_tracks_support_metrics_and_mode_specific_aggregates(
    tmp_path,
):
    from src.data.shared.models import GameParticipant, GuildPlayerAggregate
    from src.services.guild_sites import provision_guild_site
    from src.services.openfront_ingestion import (
        ingest_game_payload,
        refresh_guild_player_aggregates,
    )

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    ingest_game_payload(
        {
            "info": {
                "gameID": "team-1",
                "config": {
                    "gameType": "Public",
                    "gameMode": "Team",
                    "playerTeams": "Duos",
                },
                "numTeams": 4,
                "winner": ["team", "Team 1", "c1"],
                "players": [
                    {"clientID": "c1", "username": "Support", "clanTag": "NU"},
                    {"clientID": "c2", "username": "Front", "clanTag": "NU"},
                    {"clientID": "c9", "username": "Enemy", "clanTag": "XYZ"},
                ],
            },
            "turns": [
                {
                    "turnNumber": 1,
                    "hash": "turn-1",
                    "intents": [
                        {
                            "clientID": "c1",
                            "type": "donate_troops",
                            "recipient": "ally-1",
                            "troops": 50000,
                        },
                        {
                            "clientID": "c1",
                            "type": "donate_gold",
                            "recipient": "ally-1",
                            "gold": 200000,
                        },
                        {
                            "clientID": "c2",
                            "type": "attack",
                            "targetID": "enemy-1",
                            "troops": 75000,
                        },
                    ],
                }
            ],
        }
    )

    refresh_guild_player_aggregates(guild)

    support_participant = GameParticipant.get(
        GameParticipant.normalized_username == "support"
    )
    front_participant = GameParticipant.get(GameParticipant.normalized_username == "front")
    support_aggregate = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "support"
    )
    front_aggregate = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "front"
    )

    assert support_participant.donated_troops_total == 50000
    assert support_participant.donated_gold_total == 200000
    assert support_participant.donation_action_count == 2
    assert support_participant.attack_troops_total == 0
    assert front_participant.attack_troops_total == 75000
    assert front_participant.attack_action_count == 1
    assert support_aggregate.team_game_count == 1
    assert support_aggregate.team_win_count == 1
    assert support_aggregate.ffa_game_count == 0
    assert support_aggregate.support_bonus > 0
    assert support_aggregate.team_score > front_aggregate.team_score
    assert support_aggregate.role_label == "Flexible"
    assert front_aggregate.support_bonus == 0
    assert front_aggregate.role_label == "Flexible"


def test_refresh_guild_player_aggregates_uses_team_role_mix_for_role_labels(tmp_path):
    from src.data.shared.models import GameParticipant, GuildPlayerAggregate, ObservedGame
    from src.services.guild_sites import provision_guild_site
    from src.services.guild_stats_api import build_leaderboard_response
    from src.services.openfront_ingestion import refresh_guild_player_aggregates

    setup_shared_database(tmp_path)
    guild = provision_guild_site(
        slug="north",
        subdomain="north",
        display_name="North",
        clan_tags=["NU"],
    )

    def add_team_game(
        username: str,
        normalized_username: str,
        index: int,
        *,
        donated_troops_total: int = 0,
        donated_gold_total: int = 0,
        donation_action_count: int = 0,
        attack_troops_total: int = 0,
        attack_action_count: int = 0,
    ) -> None:
        game = ObservedGame.create(
            openfront_game_id=f"{normalized_username}-{index}",
            game_type="PUBLIC",
            mode_name="Team",
            num_teams=4,
            ended_at=datetime(2026, 3, 1, 12, 0, 0) + timedelta(days=index),
        )
        GameParticipant.create(
            game=game,
            guild=guild,
            raw_username=username,
            normalized_username=normalized_username,
            raw_clan_tag="NU",
            effective_clan_tag="NU",
            clan_tag_source="api",
            client_id=f"{normalized_username}-{index}",
            did_win=1,
            donated_troops_total=donated_troops_total,
            donated_gold_total=donated_gold_total,
            donation_action_count=donation_action_count,
            attack_troops_total=attack_troops_total,
            attack_action_count=attack_action_count,
        )

    for index in range(5):
        add_team_game(
            "Frontmain",
            "frontmain",
            index,
            attack_troops_total=75_000,
            attack_action_count=1,
        )
    add_team_game(
        "Frontmain",
        "frontmain",
        5,
        donated_troops_total=25_000,
        donation_action_count=1,
        attack_troops_total=75_000,
        attack_action_count=1,
    )

    for index in range(6, 11):
        add_team_game(
            "Backmain",
            "backmain",
            index,
            donated_troops_total=50_000,
            donated_gold_total=200_000,
            donation_action_count=2,
        )

    add_team_game(
        "Mixmain",
        "mixmain",
        11,
        attack_troops_total=75_000,
        attack_action_count=1,
    )
    add_team_game(
        "Mixmain",
        "mixmain",
        12,
        attack_troops_total=75_000,
        attack_action_count=1,
    )
    add_team_game(
        "Mixmain",
        "mixmain",
        13,
        donated_troops_total=60_000,
        donation_action_count=1,
    )
    add_team_game(
        "Mixmain",
        "mixmain",
        14,
        donated_troops_total=60_000,
        donation_action_count=1,
    )
    add_team_game(
        "Mixmain",
        "mixmain",
        15,
        donated_troops_total=25_000,
        donation_action_count=1,
        attack_troops_total=75_000,
        attack_action_count=1,
    )

    for index in range(16, 20):
        add_team_game(
            "Rookie",
            "rookie",
            index,
            attack_troops_total=75_000,
            attack_action_count=1,
        )

    refresh_guild_player_aggregates(guild)

    frontmain = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "frontmain"
    )
    backmain = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "backmain"
    )
    mixmain = GuildPlayerAggregate.get(GuildPlayerAggregate.normalized_username == "mixmain")
    rookie = GuildPlayerAggregate.get(GuildPlayerAggregate.normalized_username == "rookie")

    assert frontmain.role_label == "Frontliner"
    assert backmain.role_label == "Backliner"
    assert mixmain.role_label == "Hybrid"
    assert rookie.role_label == "Flexible"

    rows = {
        row["normalized_username"]: row
        for row in build_leaderboard_response(guild, "team")["rows"]
    }
    assert rows["frontmain"]["role_label"] == "Frontliner"
    assert rows["backmain"]["role_label"] == "Backliner"
    assert rows["mixmain"]["role_label"] == "Hybrid"
    assert rows["rookie"]["role_label"] == "Flexible"
