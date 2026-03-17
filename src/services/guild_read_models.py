from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from statistics import median
from typing import Any

from ..data.shared.models import (
    GameParticipant,
    Guild,
    GuildDailyBenchmark,
    GuildPlayerDailySnapshot,
    GuildRecentGameResult,
    GuildWeeklyPlayerScore,
    ObservedGame,
)
from .guild_sites import list_guild_clan_tags
from .openfront_ingestion import (
    _compute_support_bonus,
    _ffa_game_points,
    _infer_players_per_team,
    _infer_team_count,
    _is_ffa_mode,
    _is_team_mode,
    _participant_is_no_spawn,
    _player_payload_map,
    _team_difficulty_weight,
    _win_rate_multiplier,
    normalize_username,
    strip_tracked_clan_tag_prefix,
)
from .openfront_links import build_map_thumbnail_url, build_openfront_replay_link
from .guild_weekly_rankings import utc_week_start


def _tracked_team_presence_counts(
    participants: list[GameParticipant],
) -> dict[tuple[int, str], int]:
    counts: dict[tuple[int, str], int] = defaultdict(int)
    for participant in participants:
        if not _is_team_mode(participant.game.mode_name):
            continue
        effective_tag = str(participant.effective_clan_tag or "").strip().upper()
        if not effective_tag:
            continue
        counts[(participant.game_id, effective_tag)] += 1
    return counts


def _game_time(participant: GameParticipant) -> datetime | None:
    return participant.game.ended_at or participant.game.started_at


def _team_format_label(game: ObservedGame) -> str:
    players_per_team = _infer_players_per_team(
        num_teams=game.num_teams,
        player_teams=game.player_teams,
        total_player_count=game.total_player_count,
    )
    if isinstance(game.player_teams, str) and str(game.player_teams).strip():
        return str(game.player_teams).strip()
    if players_per_team:
        return f"{players_per_team}v"
    return "Team"


def build_team_distribution_label(game: ObservedGame) -> str:
    inferred_num_teams = _infer_team_count(
        num_teams=game.num_teams,
        player_teams=game.player_teams,
        total_player_count=game.total_player_count,
    )
    players_per_team = _infer_players_per_team(
        num_teams=game.num_teams,
        player_teams=game.player_teams,
        total_player_count=game.total_player_count,
    )
    if inferred_num_teams and players_per_team:
        label = f"{inferred_num_teams} teams of {players_per_team}"
        if isinstance(game.player_teams, str) and str(game.player_teams).strip():
            return f"{label} ({str(game.player_teams).strip()})"
        return label
    if inferred_num_teams:
        return f"{inferred_num_teams} teams"
    if players_per_team:
        return f"teams of {players_per_team}"
    return "FFA" if _is_ffa_mode(game.mode_name) else "Team"


def _player_payload_map(game: ObservedGame) -> dict[str, dict[str, Any]]:
    if not game.raw_payload:
        return {}
    try:
        payload = json.loads(game.raw_payload)
    except json.JSONDecodeError:
        return {}
    info = payload.get("info", payload)
    players = info.get("players")
    if not isinstance(players, list):
        return {}
    return {
        str(player.get("clientID") or ""): player
        for player in players
        if isinstance(player, dict) and str(player.get("clientID") or "")
    }


def _winner_players_payload(
    game: ObservedGame,
    tracked_tags: set[str],
    guild_participants: list[GameParticipant],
) -> dict[str, list[dict[str, Any]]]:
    if not game.raw_payload:
        return {"guild": [], "other": []}
    try:
        payload = json.loads(game.raw_payload)
    except json.JSONDecodeError:
        return {"guild": [], "other": []}
    info = payload.get("info", payload)
    players = info.get("players")
    winner = info.get("winner")
    if not isinstance(players, list) or not isinstance(winner, list):
        return {"guild": [], "other": []}
    player_map = {
        str(player.get("clientID") or ""): player
        for player in players
        if isinstance(player, dict) and str(player.get("clientID") or "")
    }
    winner_ids: list[str]
    if winner[:1] == ["team"]:
        winner_ids = [str(item) for item in winner[2:]]
    elif winner[:1] == ["player"]:
        winner_ids = [str(item) for item in winner[1:2]]
    else:
        winner_ids = []

    guild_usernames = {participant.normalized_username for participant in guild_participants}
    grouped = {"guild": [], "other": []}
    seen = set()
    for winner_id in winner_ids:
        player = player_map.get(winner_id)
        if player is None:
            continue
        raw_username = str(player.get("username") or "").strip()
        display_username = strip_tracked_clan_tag_prefix(raw_username, tracked_tags)
        normalized_username = normalize_username(display_username)
        payload_row = {
            "client_id": winner_id,
            "raw_username": raw_username,
            "display_username": display_username,
            "normalized_username": normalized_username,
        }
        key = (winner_id, normalized_username)
        if key in seen:
            continue
        seen.add(key)
        grouped["guild" if normalized_username in guild_usernames else "other"].append(payload_row)
    return grouped


def _grouped_guild_players(
    guild_participants: list[GameParticipant],
    tracked_tags: set[str],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    players = []
    for participant in guild_participants:
        if participant.normalized_username in seen:
            continue
        seen.add(participant.normalized_username)
        players.append(
            {
                "normalized_username": participant.normalized_username,
                "display_username": strip_tracked_clan_tag_prefix(
                    participant.raw_username,
                    tracked_tags,
                ),
                "did_win": bool(participant.did_win),
            }
        )
    players.sort(key=lambda row: row["display_username"])
    return players


def _core_team_score(payload: dict[str, Any]) -> float:
    team_games = int(payload["team_games"])
    team_wins = int(payload["team_wins"])
    if team_games <= 0:
        return 0.0
    return (
        float(payload["team_presence_score"] or 0.0)
        + float(payload["team_result_score"] or 0.0)
    ) * _win_rate_multiplier(team_wins, team_games)


def _support_bonus(payload: dict[str, Any]) -> float:
    return _compute_support_bonus(
        {
            "donated_troops_total": payload["donated_troops_total"],
            "donated_gold_total": payload["donated_gold_total"],
            "donation_action_count": payload["donation_action_count"],
            "attack_troops_total": payload["attack_troops_total"],
        },
        _core_team_score(payload),
    )


def _ffa_score(payload: dict[str, Any]) -> float:
    ffa_games = int(payload["ffa_games"])
    ffa_wins = int(payload["ffa_wins"])
    if ffa_games <= 0:
        return 0.0
    return (
        float(payload["ffa_presence_score"] or 0.0)
        + float(payload["ffa_result_score"] or 0.0)
    ) * _win_rate_multiplier(ffa_wins, ffa_games)


def _refresh_daily_snapshots_and_benchmarks(
    guild: Guild,
    participants: list[GameParticipant],
) -> None:
    GuildPlayerDailySnapshot.delete().where(GuildPlayerDailySnapshot.guild == guild).execute()
    GuildDailyBenchmark.delete().where(GuildDailyBenchmark.guild == guild).execute()
    if not participants:
        return

    tracked_tags = set(list_guild_clan_tags(guild))
    tracked_team_presence = _tracked_team_presence_counts(participants)
    player_payloads_by_game = {
        participant.game_id: _player_payload_map(participant.game) for participant in participants
    }
    state_by_player: dict[str, dict[str, Any]] = {}
    snapshot_payloads: dict[tuple[str, str, str], dict[str, Any]] = {}

    for participant in participants:
        game_time = _game_time(participant)
        if game_time is None:
            continue
        snapshot_date = game_time.date().isoformat()
        payload = state_by_player.setdefault(
            participant.normalized_username,
            {
                "player_id": participant.player_id,
                "display_username": strip_tracked_clan_tag_prefix(
                    participant.raw_username,
                    tracked_tags,
                ),
                "team_wins": 0,
                "team_games": 0,
                "team_presence_score": 0.0,
                "team_result_score": 0.0,
                "ffa_wins": 0,
                "ffa_games": 0,
                "ffa_presence_score": 0.0,
                "ffa_result_score": 0.0,
                "donated_troops_total": 0,
                "donated_gold_total": 0,
                "donation_action_count": 0,
                "attack_troops_total": 0,
            },
        )
        if participant.player_id and not payload["player_id"]:
            payload["player_id"] = participant.player_id
        payload["display_username"] = strip_tracked_clan_tag_prefix(
            participant.raw_username,
            tracked_tags,
        )
        payload["donated_troops_total"] += int(participant.donated_troops_total or 0)
        payload["donated_gold_total"] += int(participant.donated_gold_total or 0)
        payload["donation_action_count"] += int(participant.donation_action_count or 0)
        payload["attack_troops_total"] += int(participant.attack_troops_total or 0)

        if _is_team_mode(participant.game.mode_name):
            payload["team_games"] += 1
            payload["team_wins"] += int(bool(participant.did_win))
            is_no_spawn = _participant_is_no_spawn(
                participant,
                player_payloads_by_game.get(participant.game_id, {}).get(
                    str(participant.client_id or "")
                ),
            )
            difficulty_weight = _team_difficulty_weight(
                _infer_team_count(
                    num_teams=participant.game.num_teams,
                    player_teams=participant.game.player_teams,
                    total_player_count=participant.game.total_player_count,
                ),
                players_per_team=_infer_players_per_team(
                    num_teams=participant.game.num_teams,
                    player_teams=participant.game.player_teams,
                    total_player_count=participant.game.total_player_count,
                ),
                tracked_guild_teammates=tracked_team_presence.get(
                    (participant.game_id, str(participant.effective_clan_tag or "").upper()),
                    1,
                ),
            )
            if not is_no_spawn:
                payload["team_presence_score"] += 10.0 * difficulty_weight
                if participant.did_win:
                    payload["team_result_score"] += 6.0 * difficulty_weight
            team_score = round(_core_team_score(payload) + _support_bonus(payload), 2)
            snapshot_payloads[
                (participant.normalized_username, snapshot_date, "team")
            ] = {
                "guild": guild,
                "player": payload["player_id"],
                "normalized_username": participant.normalized_username,
                "display_username": payload["display_username"],
                "snapshot_date": snapshot_date,
                "scope": "team",
                "score": team_score,
                "wins": payload["team_wins"],
                "games": payload["team_games"],
                "win_rate": round(
                    payload["team_wins"] / payload["team_games"], 4
                )
                if payload["team_games"]
                else 0.0,
            }
        elif _is_ffa_mode(participant.game.mode_name):
            payload["ffa_games"] += 1
            payload["ffa_wins"] += int(bool(participant.did_win))
            payload["ffa_presence_score"] += _ffa_game_points(
                total_player_count=participant.game.total_player_count,
                did_win=False,
            )
            if participant.did_win:
                payload["ffa_result_score"] += (
                    _ffa_game_points(
                        total_player_count=participant.game.total_player_count,
                        did_win=True,
                    )
                    - _ffa_game_points(
                        total_player_count=participant.game.total_player_count,
                        did_win=False,
                    )
                )
            ffa_score = round(_ffa_score(payload), 2)
            snapshot_payloads[
                (participant.normalized_username, snapshot_date, "ffa")
            ] = {
                "guild": guild,
                "player": payload["player_id"],
                "normalized_username": participant.normalized_username,
                "display_username": payload["display_username"],
                "snapshot_date": snapshot_date,
                "scope": "ffa",
                "score": ffa_score,
                "wins": payload["ffa_wins"],
                "games": payload["ffa_games"],
                "win_rate": round(payload["ffa_wins"] / payload["ffa_games"], 4)
                if payload["ffa_games"]
                else 0.0,
            }

    for row in snapshot_payloads.values():
        GuildPlayerDailySnapshot.create(**row)

    grouped_scores: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in snapshot_payloads.values():
        grouped_scores[(row["snapshot_date"], row["scope"])].append(float(row["score"]))
    for (snapshot_date, scope), scores in grouped_scores.items():
        GuildDailyBenchmark.create(
            guild=guild,
            snapshot_date=snapshot_date,
            scope=scope,
            median_score=round(float(median(scores)), 2),
            leader_score=round(max(scores), 2),
        )


def _refresh_weekly_scores(
    guild: Guild,
    participants: list[GameParticipant],
) -> None:
    GuildWeeklyPlayerScore.delete().where(GuildWeeklyPlayerScore.guild == guild).execute()
    if not participants:
        return

    tracked_tags = set(list_guild_clan_tags(guild))
    tracked_team_presence = _tracked_team_presence_counts(participants)
    player_payloads_by_game = {
        participant.game_id: _player_payload_map(participant.game) for participant in participants
    }
    payloads: dict[tuple[str, str], dict[str, Any]] = {}

    for participant in participants:
        game_time = _game_time(participant)
        if game_time is None:
            continue
        week_start = utc_week_start(game_time).date().isoformat()
        key = (week_start, participant.normalized_username)
        payload = payloads.setdefault(
            key,
            {
                "player_id": participant.player_id,
                "display_username": strip_tracked_clan_tag_prefix(
                    participant.raw_username,
                    tracked_tags,
                ),
                "team_wins": 0,
                "team_games": 0,
                "team_presence_score": 0.0,
                "team_result_score": 0.0,
                "ffa_wins": 0,
                "ffa_games": 0,
                "ffa_presence_score": 0.0,
                "ffa_result_score": 0.0,
                "donated_troops_total": 0,
                "donated_gold_total": 0,
                "donation_action_count": 0,
                "attack_troops_total": 0,
            },
        )
        if participant.player_id and not payload["player_id"]:
            payload["player_id"] = participant.player_id
        payload["display_username"] = strip_tracked_clan_tag_prefix(
            participant.raw_username,
            tracked_tags,
        )
        payload["donated_troops_total"] += int(participant.donated_troops_total or 0)
        payload["donated_gold_total"] += int(participant.donated_gold_total or 0)
        payload["donation_action_count"] += int(participant.donation_action_count or 0)
        payload["attack_troops_total"] += int(participant.attack_troops_total or 0)

        if _is_team_mode(participant.game.mode_name):
            payload["team_games"] += 1
            payload["team_wins"] += int(bool(participant.did_win))
            is_no_spawn = _participant_is_no_spawn(
                participant,
                player_payloads_by_game.get(participant.game_id, {}).get(
                    str(participant.client_id or "")
                ),
            )
            difficulty_weight = _team_difficulty_weight(
                _infer_team_count(
                    num_teams=participant.game.num_teams,
                    player_teams=participant.game.player_teams,
                    total_player_count=participant.game.total_player_count,
                ),
                players_per_team=_infer_players_per_team(
                    num_teams=participant.game.num_teams,
                    player_teams=participant.game.player_teams,
                    total_player_count=participant.game.total_player_count,
                ),
                tracked_guild_teammates=tracked_team_presence.get(
                    (participant.game_id, str(participant.effective_clan_tag or "").upper()),
                    1,
                ),
            )
            if not is_no_spawn:
                payload["team_presence_score"] += 10.0 * difficulty_weight
                if participant.did_win:
                    payload["team_result_score"] += 6.0 * difficulty_weight
        elif _is_ffa_mode(participant.game.mode_name):
            payload["ffa_games"] += 1
            payload["ffa_wins"] += int(bool(participant.did_win))
            payload["ffa_presence_score"] += _ffa_game_points(
                total_player_count=participant.game.total_player_count,
                did_win=False,
            )
            if participant.did_win:
                payload["ffa_result_score"] += (
                    _ffa_game_points(
                        total_player_count=participant.game.total_player_count,
                        did_win=True,
                    )
                    - _ffa_game_points(
                        total_player_count=participant.game.total_player_count,
                        did_win=False,
                    )
                )

    for (week_start, normalized_username), payload in payloads.items():
        if payload["team_games"] > 0:
            team_score = round(_core_team_score(payload) + _support_bonus(payload), 2)
            GuildWeeklyPlayerScore.create(
                guild=guild,
                player=payload["player_id"],
                normalized_username=normalized_username,
                display_username=payload["display_username"],
                week_start=week_start,
                scope="team",
                score=team_score,
                wins=payload["team_wins"],
                games=payload["team_games"],
                win_rate=round(payload["team_wins"] / payload["team_games"], 4),
            )
            GuildWeeklyPlayerScore.create(
                guild=guild,
                player=payload["player_id"],
                normalized_username=normalized_username,
                display_username=payload["display_username"],
                week_start=week_start,
                scope="support",
                score=round(_support_bonus(payload), 2),
                wins=payload["team_wins"],
                games=payload["team_games"],
                win_rate=round(payload["team_wins"] / payload["team_games"], 4),
            )
        if payload["ffa_games"] > 0:
            GuildWeeklyPlayerScore.create(
                guild=guild,
                player=payload["player_id"],
                normalized_username=normalized_username,
                display_username=payload["display_username"],
                week_start=week_start,
                scope="ffa",
                score=round(_ffa_score(payload), 2),
                wins=payload["ffa_wins"],
                games=payload["ffa_games"],
                win_rate=round(payload["ffa_wins"] / payload["ffa_games"], 4),
            )


def _refresh_recent_game_results(
    guild: Guild,
    participants: list[GameParticipant],
) -> None:
    GuildRecentGameResult.delete().where(GuildRecentGameResult.guild == guild).execute()
    if not participants:
        return
    tracked_tags = set(list_guild_clan_tags(guild))
    grouped: dict[int, list[GameParticipant]] = defaultdict(list)
    for participant in participants:
        grouped[participant.game_id].append(participant)

    items = []
    for rows in grouped.values():
        rows.sort(key=lambda row: row.id)
        game = rows[0].game
        ended_at = game.ended_at or game.started_at
        guild_team_players = _grouped_guild_players(rows, tracked_tags)
        winner_players = _winner_players_payload(game, tracked_tags, rows)
        items.append(
            {
                "guild": guild,
                "game": game,
                "openfront_game_id": game.openfront_game_id,
                "ended_at": ended_at,
                "mode": game.mode_name or "",
                "result": "win" if any(bool(row.did_win) for row in rows) else "loss",
                "map_name": game.map_name,
                "format_label": _team_format_label(game) if _is_team_mode(game.mode_name) else "FFA",
                "team_distribution": build_team_distribution_label(game),
                "replay_link": build_openfront_replay_link(str(game.openfront_game_id)),
                "map_thumbnail_url": build_map_thumbnail_url(game.map_name),
                "guild_team_players_json": json.dumps(guild_team_players),
                "winner_players_json": json.dumps(winner_players),
            }
        )

    items.sort(
        key=lambda row: (
            row["ended_at"] is None,
            row["ended_at"] or datetime.min,
            row["openfront_game_id"],
        ),
        reverse=True,
    )
    for item in items:
        GuildRecentGameResult.create(**item)


def refresh_guild_read_models(
    guild: Guild,
    *,
    participants: list[GameParticipant],
) -> None:
    ordered_participants = sorted(
        participants,
        key=lambda participant: (
            _game_time(participant) is None,
            _game_time(participant) or datetime.min,
            participant.id,
        ),
    )
    _refresh_daily_snapshots_and_benchmarks(guild, ordered_participants)
    _refresh_weekly_scores(guild, ordered_participants)
    _refresh_recent_game_results(guild, ordered_participants)
