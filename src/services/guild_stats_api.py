from __future__ import annotations

from typing import Any

from ..data.shared.models import Guild, GuildPlayerAggregate
from .guild_sites import list_guild_clan_tags
from .guild_leaderboard import get_guild_player_profile, player_state_label
from .openfront_ingestion import strip_tracked_clan_tag_prefix
from .player_linking import compute_linked_profile_stats

SUPPORTED_VIEWS = ("team", "ffa", "overall", "support")
DEFAULT_SORT_BY_VIEW = {
    "team": "team_score",
    "ffa": "ffa_score",
    "overall": "overall_score",
    "support": "donated_troops_total",
}
SORT_FIELDS_BY_VIEW = {
    "team": (
        "team_score",
        "team_win_count",
        "team_game_count",
        "team_win_rate",
        "win_count",
        "game_count",
        "donated_troops_total",
        "donated_gold_total",
        "donation_action_count",
        "support_bonus",
        "attack_troops_total",
        "last_game_at",
    ),
    "ffa": (
        "ffa_score",
        "ffa_win_count",
        "ffa_game_count",
        "ffa_win_rate",
        "win_count",
        "game_count",
        "attack_troops_total",
        "last_game_at",
    ),
    "overall": (
        "overall_score",
        "team_score",
        "ffa_score",
        "team_win_count",
        "ffa_win_count",
        "win_count",
        "game_count",
        "last_game_at",
    ),
    "support": (
        "donated_troops_total",
        "donated_gold_total",
        "donation_action_count",
        "support_bonus",
        "team_game_count",
        "team_score",
        "last_game_at",
    ),
}


def _normalized_view(view: str) -> str:
    normalized = str(view or "").strip().lower()
    if normalized not in SUPPORTED_VIEWS:
        raise ValueError(f"Unsupported leaderboard view: {view}")
    return normalized


def _legacy_team_game_count(aggregate: GuildPlayerAggregate) -> int:
    if aggregate.team_game_count:
        return aggregate.team_game_count
    return aggregate.game_count


def _legacy_team_win_count(aggregate: GuildPlayerAggregate) -> int:
    if aggregate.team_win_count:
        return aggregate.team_win_count
    return aggregate.win_count


def _overall_score_value(
    aggregate: GuildPlayerAggregate,
    *,
    team_score: float,
    ffa_score: float,
    team_game_count: int,
    ffa_game_count: int,
) -> float:
    if aggregate.overall_score:
        return float(aggregate.overall_score)
    if team_game_count and not ffa_game_count:
        return float(team_score)
    if ffa_game_count and not team_game_count:
        return float(ffa_score)
    if team_game_count and ffa_game_count:
        return round((team_score * 0.7) + (ffa_score * 0.3), 2)
    return 0.0


def _row_payload(
    aggregate: GuildPlayerAggregate,
    tracked_tags: set[str] | None = None,
) -> dict[str, Any]:
    team_game_count = _legacy_team_game_count(aggregate)
    team_win_count = _legacy_team_win_count(aggregate)
    ffa_game_count = aggregate.ffa_game_count
    ffa_win_count = aggregate.ffa_win_count
    team_win_rate = team_win_count / team_game_count if team_game_count else 0.0
    ffa_win_rate = ffa_win_count / ffa_game_count if ffa_game_count else 0.0
    team_score = aggregate.team_score or float(team_win_count * 100)
    ffa_score = aggregate.ffa_score or float(ffa_win_count * 100)
    overall_score = _overall_score_value(
        aggregate,
        team_score=team_score,
        ffa_score=ffa_score,
        team_game_count=team_game_count,
        ffa_game_count=ffa_game_count,
    )
    display_username = strip_tracked_clan_tag_prefix(
        aggregate.display_username,
        tracked_tags or set(),
    )
    return {
        "normalized_username": aggregate.normalized_username,
        "display_username": display_username,
        "state": player_state_label(aggregate),
        "last_observed_clan_tag": aggregate.last_observed_clan_tag,
        "win_count": aggregate.win_count,
        "game_count": aggregate.game_count,
        "team_win_count": team_win_count,
        "team_game_count": team_game_count,
        "team_win_rate": round(team_win_rate, 4),
        "ffa_win_count": ffa_win_count,
        "ffa_game_count": ffa_game_count,
        "ffa_win_rate": round(ffa_win_rate, 4),
        "team_score": round(team_score, 2),
        "ffa_score": round(ffa_score, 2),
        "overall_score": round(overall_score, 2),
        "donated_troops_total": aggregate.donated_troops_total,
        "donated_gold_total": aggregate.donated_gold_total,
        "donation_action_count": aggregate.donation_action_count,
        "attack_troops_total": aggregate.attack_troops_total,
        "attack_action_count": aggregate.attack_action_count,
        "support_bonus": round(float(aggregate.support_bonus or 0.0), 2),
        "role_label": aggregate.role_label or "Flexible",
        "last_game_at": aggregate.last_game_at.isoformat()
        if aggregate.last_game_at
        else None,
        "last_team_game_at": aggregate.last_team_game_at.isoformat()
        if aggregate.last_team_game_at
        else None,
        "last_ffa_game_at": aggregate.last_ffa_game_at.isoformat()
        if aggregate.last_ffa_game_at
        else None,
    }


def build_leaderboard_response(
    guild: Guild,
    view: str,
    *,
    sort_by: str | None = None,
) -> dict[str, Any]:
    normalized_view = _normalized_view(view)
    tracked_tags = set(list_guild_clan_tags(guild))
    rows = [
        _row_payload(row, tracked_tags)
        for row in GuildPlayerAggregate.select().where(GuildPlayerAggregate.guild == guild)
    ]
    allowed_sorts = SORT_FIELDS_BY_VIEW[normalized_view]
    sort_field = sort_by if sort_by in allowed_sorts else DEFAULT_SORT_BY_VIEW[normalized_view]
    rows.sort(
        key=lambda row: (row.get(sort_field) is None, row.get(sort_field), row["display_username"]),
        reverse=True,
    )
    return {
        "view": normalized_view,
        "default_sort": DEFAULT_SORT_BY_VIEW[normalized_view],
        "sort_by": sort_field,
        "available_sorts": list(allowed_sorts),
        "rows": rows,
    }


def build_scoring_response(view: str) -> dict[str, Any]:
    normalized_view = _normalized_view(view)
    summaries = {
        "team": (
            "Team score rewards winning team games, gives more weight to recent "
            "results, treats matches with more teams as more difficult so more "
            "teams count more, and adds a limited support bonus from troop and "
            "gold donations."
        ),
        "ffa": (
            "FFA score rewards solo results only. It ignores support metrics and "
            "focuses on Free For All performance."
        ),
        "overall": (
            "Overall score combines separately normalized Team and FFA "
            "performance, stays Team-first, reduces the impact of a mode "
            "when the player has only a small sample, and falls back to the "
            "played mode when the other mode has no games."
        ),
        "support": (
            "Support view focuses on exact troop and gold donations plus related "
            "support actions in team games."
        ),
    }
    return {
        "view": normalized_view,
        "summary": summaries[normalized_view],
        "overall_summary": (
            "Overall targets 70% Team and 30% FFA when both modes have "
            "meaningful samples, and otherwise falls back to the mode the "
            "player actually played."
        ),
        "factors": {
            "team": [
                "Wins matter most.",
                "Recent matches matter more.",
                "Matches with more teams count more.",
                "Support adds a limited bonus.",
            ],
            "ffa": [
                "FFA ignores support metrics.",
                "Solo results matter most.",
            ],
            "overall": [
                "Team and FFA are normalized separately.",
                "Small samples count less.",
                "If one mode has no games, Overall falls back to the other mode.",
                "The target mix is 70% Team and 30% FFA.",
            ],
        },
    }


async def build_player_profile_response(
    guild: Guild,
    normalized_username: str,
    *,
    openfront_client: Any | None = None,
) -> dict[str, Any] | None:
    aggregate = get_guild_player_profile(guild, normalized_username)
    if aggregate is None:
        return None

    player = _row_payload(aggregate, set(list_guild_clan_tags(guild)))
    response = {
        "player": player,
        "sections": {
            "team": {
                "score": player["team_score"],
                "wins": player["team_win_count"],
                "games": player["team_game_count"],
                "win_rate": player["team_win_rate"],
            },
            "ffa": {
                "score": player["ffa_score"],
                "wins": player["ffa_win_count"],
                "games": player["ffa_game_count"],
                "win_rate": player["ffa_win_rate"],
            },
            "overall": {"score": player["overall_score"]},
            "support": {
                "troops_donated": player["donated_troops_total"],
                "gold_donated": player["donated_gold_total"],
                "donation_actions": player["donation_action_count"],
                "support_bonus": player["support_bonus"],
                "role_label": player["role_label"],
            },
        },
    }

    if aggregate.player_id and openfront_client is not None:
        linked_stats = await compute_linked_profile_stats(
            aggregate.player,
            guild,
            openfront_client,
        )
        response["linked"] = {
            "guild_win_count": linked_stats.guild_win_count,
            "guild_game_count": linked_stats.guild_game_count,
            "global_public_wins": linked_stats.global_public_wins,
            "aliases": linked_stats.aliases,
        }
    return response
