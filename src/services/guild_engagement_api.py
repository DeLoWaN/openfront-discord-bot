from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from ..data.shared.models import GameParticipant, Guild, GuildPlayerAggregate, ObservedGame
from .guild_badges import list_recent_badge_awards
from .guild_combo_service import combo_counts_by_format, list_combo_rankings
from .guild_sites import list_guild_clan_tags
from .openfront_ingestion import (
    _compute_support_bonus,
    _ffa_game_points,
    _infer_players_per_team,
    _infer_team_count,
    _is_ffa_mode,
    _is_team_mode,
    _team_difficulty_weight,
    _team_game_points,
    _win_rate_multiplier,
    normalize_username,
    strip_tracked_clan_tag_prefix,
)


def _tracked_team_presence_counts(
    guild: Guild,
) -> dict[tuple[int, str], int]:
    counts: dict[tuple[int, str], int] = defaultdict(int)
    query = (
        GameParticipant.select(GameParticipant, ObservedGame)
        .join(ObservedGame)
        .where(GameParticipant.guild == guild)
    )
    for participant in query:
        if not _is_team_mode(participant.game.mode_name):
            continue
        effective_tag = str(participant.effective_clan_tag or "").strip().upper()
        if not effective_tag:
            continue
        counts[(participant.game_id, effective_tag)] += 1
    return counts


def _team_format_label(game: ObservedGame) -> str:
    if str(game.player_teams or "").strip():
        return str(game.player_teams)
    if game.num_teams and game.total_player_count and game.num_teams > 0:
        players_per_team = int(game.total_player_count / game.num_teams)
        return f"{game.num_teams} teams of {players_per_team}"
    if game.num_teams:
        return f"{game.num_teams} teams"
    return "Team"


def build_recent_results_response(
    guild: Guild,
    *,
    limit: int = 20,
) -> dict[str, Any]:
    tracked_tags = set(list_guild_clan_tags(guild))
    query = list(
        GameParticipant.select(GameParticipant, ObservedGame)
        .join(ObservedGame)
        .where((GameParticipant.guild == guild) & (GameParticipant.did_win == 1))
        .order_by(ObservedGame.ended_at.desc(), ObservedGame.started_at.desc(), GameParticipant.id.desc())
    )
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for participant in query:
        game = participant.game
        game_time = game.ended_at or game.started_at
        if _is_team_mode(game.mode_name):
            grouping_key = (game.openfront_game_id, str(participant.effective_clan_tag or "").upper())
        elif _is_ffa_mode(game.mode_name):
            grouping_key = (game.openfront_game_id, participant.client_id)
        else:
            continue
        current = grouped.setdefault(
            grouping_key,
            {
                "openfront_game_id": game.openfront_game_id,
                "mode": game.mode_name,
                "format_label": _team_format_label(game)
                if _is_team_mode(game.mode_name)
                else "FFA",
                "map_name": game.map_name,
                "ended_at": game_time,
                "duration_seconds": game.duration_seconds,
                "replay_link": f"https://openfront.io/#join={game.openfront_game_id}",
                "winning_tag": participant.effective_clan_tag if _is_team_mode(game.mode_name) else None,
                "players": [],
            },
        )
        current["players"].append(
            {
                "normalized_username": participant.normalized_username,
                "display_username": strip_tracked_clan_tag_prefix(
                    participant.raw_username,
                    tracked_tags,
                ),
            }
        )
    items = list(grouped.values())
    items.sort(
        key=lambda item: (
            item["ended_at"] is None,
            item["ended_at"] or datetime.min,
            item["openfront_game_id"],
        ),
        reverse=True,
    )
    serialized = []
    for item in items[:limit]:
        serialized.append(
            {
                **item,
                "ended_at": item["ended_at"].isoformat() if item["ended_at"] else None,
            }
        )
    return {"items": serialized}


def build_home_response(guild: Guild) -> dict[str, Any]:
    from .guild_stats_api import build_leaderboard_response

    team = build_leaderboard_response(guild, "team")["rows"]
    support = build_leaderboard_response(guild, "support")["rows"]
    combo_podiums = {}
    pending_counts = {}
    featured_pending = []
    for format_slug in ("duo", "trio", "quad"):
        rankings = list_combo_rankings(guild, format_slug)
        combo_podiums[format_slug] = rankings["confirmed"][:3]
        pending_counts[format_slug] = len(rankings["pending"])
        if rankings["pending"]:
            featured_pending.append(rankings["pending"][0])
    featured_pending.sort(
        key=lambda combo: (
            combo["games_together"],
            combo["win_rate"],
            combo["last_game_at"] or "",
        ),
        reverse=True,
    )
    return {
        "guild": {
            "display_name": guild.display_name,
            "slug": guild.slug,
            "clan_tags": list_guild_clan_tags(guild),
        },
        "competitive_pulse": {
            "leaders": team[:3],
            "most_active": sorted(
                team,
                key=lambda row: (
                    row["team_recent_game_count_30d"],
                    row["team_score"],
                    row["display_username"],
                ),
                reverse=True,
            )[:3],
            "support_spotlight": support[:1],
        },
        "combo_podiums": combo_podiums,
        "pending_combo_teaser": {
            "counts": pending_counts,
            "featured": featured_pending[:3],
        },
        "recent_wins_preview": build_recent_results_response(guild, limit=5)["items"],
        "recent_badges": list_recent_badge_awards(guild, limit=6),
    }


def build_player_timeseries_response(
    guild: Guild,
    normalized_username: str,
) -> dict[str, Any]:
    normalized = normalize_username(normalized_username)
    tracked_presence_counts = _tracked_team_presence_counts(guild)
    player_rows = list(
        GameParticipant.select(GameParticipant, ObservedGame)
        .join(ObservedGame)
        .where(
            (GameParticipant.guild == guild)
            & (GameParticipant.normalized_username == normalized)
        )
        .order_by(ObservedGame.started_at, ObservedGame.ended_at, GameParticipant.id)
    )
    progression: list[dict[str, Any]] = []
    recent_form: list[dict[str, Any]] = []
    team_games = 0
    team_wins = 0
    ffa_games = 0
    ffa_wins = 0
    donated_troops_total = 0
    donated_gold_total = 0
    donation_action_count = 0
    attack_troops_total = 0
    team_presence_score = 0.0
    team_result_score = 0.0
    ffa_presence_score = 0.0
    ffa_result_score = 0.0

    for participant in player_rows:
        game = participant.game
        game_time = game.ended_at or game.started_at
        did_win = bool(participant.did_win)
        donated_troops_total += int(participant.donated_troops_total or 0)
        donated_gold_total += int(participant.donated_gold_total or 0)
        donation_action_count += int(participant.donation_action_count or 0)
        attack_troops_total += int(participant.attack_troops_total or 0)
        if _is_team_mode(game.mode_name):
            team_games += 1
            team_wins += int(did_win)
            players_per_team = _infer_players_per_team(
                num_teams=game.num_teams,
                player_teams=game.player_teams,
                total_player_count=game.total_player_count,
            )
            inferred_num_teams = _infer_team_count(
                num_teams=game.num_teams,
                player_teams=game.player_teams,
                total_player_count=game.total_player_count,
            )
            tracked_guild_teammates = tracked_presence_counts.get(
                (participant.game_id, str(participant.effective_clan_tag or "").upper()),
                1,
            )
            difficulty_weight = _team_difficulty_weight(
                inferred_num_teams=inferred_num_teams,
                players_per_team=players_per_team,
                tracked_guild_teammates=tracked_guild_teammates,
            )
            team_presence_score += 10.0 * difficulty_weight
            if did_win:
                team_result_score += 6.0 * difficulty_weight
        elif _is_ffa_mode(game.mode_name):
            ffa_games += 1
            ffa_wins += int(did_win)
            ffa_presence_score += _ffa_game_points(
                total_player_count=game.total_player_count,
                did_win=False,
            )
            if did_win:
                ffa_result_score += _ffa_game_points(
                    total_player_count=game.total_player_count,
                    did_win=True,
                ) - _ffa_game_points(total_player_count=game.total_player_count, did_win=False)

        core_team_score = (
            (team_presence_score + team_result_score) * _win_rate_multiplier(team_wins, team_games)
            if team_games
            else 0.0
        )
        support_bonus = _compute_support_bonus(
            {
                "donated_troops_total": donated_troops_total,
                "donated_gold_total": donated_gold_total,
                "donation_action_count": donation_action_count,
                "attack_troops_total": attack_troops_total,
            },
            core_team_score,
        )
        ffa_score = (
            (ffa_presence_score + ffa_result_score) * _win_rate_multiplier(ffa_wins, ffa_games)
            if ffa_games
            else 0.0
        )
        point = {
            "ended_at": game_time.isoformat() if game_time else None,
            "mode": game.mode_name,
            "did_win": did_win,
            "team_score": round(core_team_score + support_bonus, 2),
            "team_games": team_games,
            "team_wins": team_wins,
            "ffa_score": round(ffa_score, 2),
            "ffa_games": ffa_games,
            "ffa_wins": ffa_wins,
        }
        progression.append(point)
        recent_form.append(
            {
                "ended_at": point["ended_at"],
                "mode": game.mode_name,
                "did_win": did_win,
                "map_name": game.map_name,
                "format_label": _team_format_label(game)
                if _is_team_mode(game.mode_name)
                else "FFA",
            }
        )

    return {
        "progression": progression,
        "recent_form": recent_form[-12:],
    }
