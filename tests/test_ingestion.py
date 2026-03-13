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


def test_refresh_guild_player_aggregates_weights_overall_score_by_mode_confidence(
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
        mode_name: str,
        username: str,
        did_win: int,
        ended_at: datetime,
    ) -> None:
        game = ObservedGame.create(
            openfront_game_id=game_id,
            game_type="PUBLIC",
            mode_name=mode_name,
            num_teams=4 if mode_name == "Team" else None,
            total_player_count=100 if mode_name == "Free For All" else 8,
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

    for index in range(60):
        create_participant(
            game_id=f"team-king-{index}",
            mode_name="Team",
            username="TeamKing",
            did_win=1,
            ended_at=datetime(2026, 3, 1, 12, 0, 0),
        )
    for index in range(5):
        create_participant(
            game_id=f"team-solo-{index}",
            mode_name="Team",
            username="SoloAce",
            did_win=0,
            ended_at=datetime(2026, 3, 1, 12, 0, 0),
        )
    for index in range(2):
        create_participant(
            game_id=f"ffa-king-{index}",
            mode_name="Free For All",
            username="TeamKing",
            did_win=0,
            ended_at=datetime(2026, 3, 1, 12, 0, 0),
        )
    for index in range(60):
        create_participant(
            game_id=f"ffa-solo-{index}",
            mode_name="Free For All",
            username="SoloAce",
            did_win=1,
            ended_at=datetime(2026, 3, 1, 12, 0, 0),
        )

    refresh_guild_player_aggregates(guild)

    team_king = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "teamking"
    )
    solo_ace = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "soloace"
    )
    team_king_raw_overall = round((team_king.team_score * 0.7) + (team_king.ffa_score * 0.3), 2)

    assert team_king.team_score > solo_ace.team_score
    assert solo_ace.ffa_score > team_king.ffa_score
    assert team_king.overall_score != team_king_raw_overall
    assert team_king.overall_score > solo_ace.overall_score


def test_refresh_guild_player_aggregates_falls_back_to_team_score_without_ffa_games(
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

    for index in range(12):
        game = ObservedGame.create(
            openfront_game_id=f"team-only-{index}",
            game_type="PUBLIC",
            mode_name="Team",
            num_teams=4,
            ended_at=datetime(2026, 3, 1, 12, 0, 0),
        )
        GameParticipant.create(
            game=game,
            guild=guild,
            raw_username="Temujin",
            normalized_username="temujin",
            raw_clan_tag="NU",
            effective_clan_tag="NU",
            clan_tag_source="api",
            client_id=f"team-only-{index}",
            did_win=1,
        )

    refresh_guild_player_aggregates(guild)

    temujin = GuildPlayerAggregate.get(
        GuildPlayerAggregate.normalized_username == "temujin"
    )

    assert temujin.ffa_game_count == 0
    assert temujin.overall_score == temujin.team_score


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
