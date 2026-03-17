from __future__ import annotations

import json
from collections import deque
from datetime import datetime
from typing import Any

from ..data.shared.models import (
    GameParticipant,
    Guild,
    GuildDailyBenchmark,
    GuildPlayerDailySnapshot,
    GuildPlayerAggregate,
    GuildRecentGameResult,
    GuildWeeklyPlayerScore,
    ObservedGame,
)
from .guild_badges import list_recent_badge_awards
from .guild_combo_service import combo_counts_by_format, list_combo_rankings
from .guild_sites import list_guild_clan_tags
from .guild_weekly_rankings import build_weekly_rankings_response
from .openfront_ingestion import normalize_username


def _decode_json_rows(value: str | None) -> Any:
    if not value:
        return []
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []


def build_recent_results_response(
    guild: Guild,
    *,
    limit: int = 20,
    result: str | None = None,
) -> dict[str, Any]:
    query = (
        GuildRecentGameResult.select()
        .where(GuildRecentGameResult.guild == guild)
        .order_by(
            GuildRecentGameResult.ended_at.desc(),
            GuildRecentGameResult.openfront_game_id.desc(),
        )
    )
    normalized_result = str(result or "").strip().lower()
    if normalized_result in {"win", "loss"}:
        query = query.where(GuildRecentGameResult.result == normalized_result)

    items = []
    for row in query.limit(limit):
        items.append(
            {
                "openfront_game_id": row.openfront_game_id,
                "ended_at": row.ended_at.isoformat() if row.ended_at else None,
                "mode": row.mode,
                "result": row.result,
                "map_name": row.map_name,
                "format_label": row.format_label,
                "team_distribution": row.team_distribution,
                "replay_link": row.replay_link,
                "map_thumbnail_url": row.map_thumbnail_url,
                "guild_team_players": _decode_json_rows(row.guild_team_players_json),
                "winner_players": _decode_json_rows(row.winner_players_json),
            }
        )
    return {"items": items}


def _ranked_rows(rows: list[dict[str, Any]], score_key: str) -> list[dict[str, Any]]:
    ranked = []
    for index, row in enumerate(rows[:3]):
        ranked.append({**row, "rank": index + 1, "score_key": score_key})
    return ranked


def build_home_response(guild: Guild) -> dict[str, Any]:
    from .guild_stats_api import build_leaderboard_response

    team = build_leaderboard_response(guild, "team")["rows"]
    support = build_leaderboard_response(guild, "support")["rows"]
    weekly = build_weekly_rankings_response(guild, scope="team", weeks=6)
    roster_podiums = {}
    pending_counts = {}
    featured_pending = []
    for format_slug in ("duo", "trio", "quad"):
        rankings = list_combo_rankings(guild, format_slug)
        roster_podiums[format_slug] = rankings["confirmed"][:3]
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
    latest_games_preview = build_recent_results_response(guild, limit=5)["items"]
    return {
        "guild": {
            "display_name": guild.display_name,
            "slug": guild.slug,
            "clan_tags": list_guild_clan_tags(guild),
        },
        "competitive_pulse": {
            "leaders": _ranked_rows(team, "team_score"),
            "most_active": _ranked_rows(
                sorted(
                    team,
                    key=lambda row: (
                        row["team_recent_game_count_30d"],
                        row["team_score"],
                        row["display_username"],
                    ),
                    reverse=True,
                ),
                "team_recent_game_count_30d",
            ),
            "support_spotlight": _ranked_rows(support[:3], "support_bonus"),
        },
        "roster_podiums": roster_podiums,
        "combo_podiums": roster_podiums,
        "pending_roster_teaser": {
            "counts": pending_counts,
            "featured": featured_pending[:3],
        },
        "pending_combo_teaser": {
            "counts": pending_counts,
            "featured": featured_pending[:3],
        },
        "latest_games_preview": latest_games_preview,
        "recent_wins_preview": latest_games_preview,
        "weekly_pulse": {
            "scope": weekly["scope"],
            "rows": weekly["rows"][:3],
            "movers": weekly["movers"][:3],
        },
        "recent_badges": list_recent_badge_awards(guild, limit=6),
        "roster_counts": combo_counts_by_format(guild),
    }


def _daily_progression_rows(
    guild: Guild,
    normalized_username: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    snapshots = list(
        GuildPlayerDailySnapshot.select()
        .where(
            (GuildPlayerDailySnapshot.guild == guild)
            & (GuildPlayerDailySnapshot.normalized_username == normalized_username)
            & (GuildPlayerDailySnapshot.scope == "team")
        )
        .order_by(GuildPlayerDailySnapshot.snapshot_date)
    )
    benchmarks = {
        row.snapshot_date: {
            "median_score": round(float(row.median_score or 0.0), 2),
            "leader_score": round(float(row.leader_score or 0.0), 2),
        }
        for row in GuildDailyBenchmark.select().where(
            (GuildDailyBenchmark.guild == guild)
            & (GuildDailyBenchmark.scope == "team")
        )
    }
    return (
        [
            {
                "date": row.snapshot_date,
                "score": round(float(row.score or 0.0), 2),
                "wins": int(row.wins or 0),
                "games": int(row.games or 0),
                "win_rate": round(float(row.win_rate or 0.0), 4),
            }
            for row in snapshots
        ],
        benchmarks,
    )


def _recent_performance_rows(
    daily_progression: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not daily_progression:
        return []
    recent = daily_progression[-14:]
    rolling_window: deque[tuple[int, int]] = deque()
    recent_rows = []
    previous_score = 0.0
    previous_wins = 0
    previous_games = 0
    for row in recent:
        daily_wins = max(0, int(row["wins"]) - previous_wins)
        daily_games = max(0, int(row["games"]) - previous_games)
        rolling_window.append((daily_wins, daily_games))
        while len(rolling_window) > 7:
            rolling_window.popleft()
        rolling_wins = sum(item[0] for item in rolling_window)
        rolling_games = sum(item[1] for item in rolling_window)
        recent_rows.append(
            {
                "date": row["date"],
                "score_delta": round(float(row["score"]) - previous_score, 2),
                "daily_wins": daily_wins,
                "daily_games": daily_games,
                "rolling_win_rate": round(rolling_wins / rolling_games, 4)
                if rolling_games
                else 0.0,
            }
        )
        previous_score = float(row["score"])
        previous_wins = int(row["wins"])
        previous_games = int(row["games"])
    return recent_rows


def _weekly_score_rows(
    guild: Guild,
    normalized_username: str,
) -> list[dict[str, Any]]:
    rows = list(
        GuildWeeklyPlayerScore.select()
        .where(
            (GuildWeeklyPlayerScore.guild == guild)
            & (GuildWeeklyPlayerScore.normalized_username == normalized_username)
        )
        .order_by(GuildWeeklyPlayerScore.week_start, GuildWeeklyPlayerScore.scope)
    )
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        current = grouped.setdefault(
            row.week_start,
            {
                "week_start": row.week_start,
                "team": 0.0,
                "ffa": 0.0,
                "support": 0.0,
            },
        )
        current[row.scope] = round(float(row.score or 0.0), 2)
    return [grouped[key] for key in sorted(grouped.keys())[-6:]]


def build_player_timeseries_response(
    guild: Guild,
    normalized_username: str,
) -> dict[str, Any]:
    normalized = normalize_username(normalized_username)
    daily_progression, benchmarks = _daily_progression_rows(guild, normalized)
    daily_benchmarks = [
        {
            "date": row["date"],
            "median_score": benchmarks.get(row["date"], {}).get("median_score", 0.0),
            "leader_score": benchmarks.get(row["date"], {}).get("leader_score", 0.0),
        }
        for row in daily_progression
    ]
    return {
        "daily_progression": daily_progression,
        "daily_benchmarks": daily_benchmarks,
        "recent_performance": _recent_performance_rows(daily_progression),
        "weekly_scores": _weekly_score_rows(guild, normalized),
        "progression": daily_progression,
        "recent_form": _recent_performance_rows(daily_progression),
    }
