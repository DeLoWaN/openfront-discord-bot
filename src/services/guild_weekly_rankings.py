from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..data.shared.models import Guild, GuildWeeklyPlayerScore
from .openfront_ingestion import normalize_username

WEEKLY_SCOPES = ("team", "ffa", "support")


def utc_week_start(value: datetime) -> datetime:
    normalized = (
        value.astimezone(timezone.utc).replace(tzinfo=None)
        if value.tzinfo
        else value.replace(tzinfo=None)
    )
    return (normalized - timedelta(days=normalized.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )


def current_utc_week_start() -> datetime:
    return utc_week_start(datetime.now(timezone.utc))


def _week_key(value: datetime) -> str:
    return utc_week_start(value).date().isoformat()


def _movement_payload(current_rank: int | None, previous_rank: int | None) -> dict[str, Any]:
    if current_rank is None:
        return {"kind": "absent", "delta": None, "label": "Absent"}
    if previous_rank is None:
        return {"kind": "new", "delta": None, "label": "New"}
    delta = previous_rank - current_rank
    if delta > 0:
        return {"kind": "up", "delta": delta, "label": f"Up {delta}"}
    if delta < 0:
        return {"kind": "down", "delta": abs(delta), "label": f"Down {abs(delta)}"}
    return {"kind": "steady", "delta": 0, "label": "Steady"}


def _scope_or_default(scope: str) -> str:
    normalized = normalize_username(scope)
    if normalized not in WEEKLY_SCOPES:
        raise ValueError(f"Unsupported weekly scope: {scope}")
    return normalized


def _ranked_rows(
    guild: Guild,
    scope: str,
    week_start_key: str,
) -> list[GuildWeeklyPlayerScore]:
    rows = list(
        GuildWeeklyPlayerScore.select()
        .where(
            (GuildWeeklyPlayerScore.guild == guild)
            & (GuildWeeklyPlayerScore.scope == scope)
            & (GuildWeeklyPlayerScore.week_start == week_start_key)
        )
    )
    rows.sort(
        key=lambda row: (
            float(row.score or 0.0),
            float(row.win_rate or 0.0),
            int(row.games or 0),
            row.display_username,
        ),
        reverse=True,
    )
    return rows


def build_weekly_rankings_response(
    guild: Guild,
    *,
    scope: str,
    weeks: int = 6,
) -> dict[str, Any]:
    normalized_scope = _scope_or_default(scope)
    total_weeks = max(1, min(int(weeks or 6), 12))
    current_week = current_utc_week_start()
    week_keys = [
        (current_week - timedelta(days=7 * offset)).date().isoformat()
        for offset in range(total_weeks)
    ]
    current_rows = _ranked_rows(guild, normalized_scope, week_keys[0])
    previous_rows = _ranked_rows(guild, normalized_scope, week_keys[1]) if len(week_keys) > 1 else []
    previous_ranks = {
        row.normalized_username: index + 1 for index, row in enumerate(previous_rows)
    }

    all_rows = list(
        GuildWeeklyPlayerScore.select().where(
            (GuildWeeklyPlayerScore.guild == guild)
            & (GuildWeeklyPlayerScore.scope == normalized_scope)
            & (GuildWeeklyPlayerScore.week_start.in_(week_keys))
        )
    )
    history_by_player: dict[str, dict[str, GuildWeeklyPlayerScore]] = {}
    for row in all_rows:
        history_by_player.setdefault(row.normalized_username, {})[row.week_start] = row

    rows_payload = []
    for index, row in enumerate(current_rows[:10]):
        history = history_by_player.get(row.normalized_username, {})
        trend = [
            round(float(history.get(week_key).score or 0.0), 2)
            if history.get(week_key) is not None
            else 0.0
            for week_key in reversed(week_keys)
        ]
        rows_payload.append(
            {
                "rank": index + 1,
                "normalized_username": row.normalized_username,
                "display_username": row.display_username,
                "score": round(float(row.score or 0.0), 2),
                "wins": int(row.wins or 0),
                "games": int(row.games or 0),
                "ratio": f"{int(row.wins or 0)}/{int(row.games or 0)}",
                "win_rate": round(float(row.win_rate or 0.0), 4),
                "movement": _movement_payload(index + 1, previous_ranks.get(row.normalized_username)),
                "history": trend,
            }
        )

    movers = [row for row in rows_payload if row["movement"]["kind"] in {"up", "down", "new"}]
    movers.sort(
        key=lambda row: (
            row["movement"]["delta"] is None,
            int(row["movement"]["delta"] or 0),
            row["score"],
        ),
        reverse=True,
    )

    return {
        "scope": normalized_scope,
        "current_week_start": week_keys[0],
        "weeks": list(reversed(week_keys)),
        "rows": rows_payload,
        "movers": movers[:5],
    }


def build_player_weekly_summary(
    guild: Guild,
    normalized_username: str,
    *,
    scope: str = "team",
) -> dict[str, Any]:
    normalized_scope = _scope_or_default(scope)
    player_key = normalize_username(normalized_username)
    current_week = current_utc_week_start().date().isoformat()
    previous_week = (current_utc_week_start() - timedelta(days=7)).date().isoformat()
    current_rows = _ranked_rows(guild, normalized_scope, current_week)
    previous_rows = _ranked_rows(guild, normalized_scope, previous_week)
    current_rank = next(
        (index + 1 for index, row in enumerate(current_rows) if row.normalized_username == player_key),
        None,
    )
    previous_rank = next(
        (index + 1 for index, row in enumerate(previous_rows) if row.normalized_username == player_key),
        None,
    )
    current_row = next(
        (row for row in current_rows if row.normalized_username == player_key),
        None,
    )
    return {
        "scope": normalized_scope,
        "week_start": current_week,
        "rank": current_rank,
        "movement": _movement_payload(current_rank, previous_rank),
        "score": round(float(current_row.score or 0.0), 2) if current_row else 0.0,
        "wins": int(current_row.wins or 0) if current_row else 0,
        "games": int(current_row.games or 0) if current_row else 0,
        "win_rate": round(float(current_row.win_rate or 0.0), 4) if current_row else 0.0,
    }
