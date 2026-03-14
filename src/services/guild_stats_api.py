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
    "support": "support_bonus",
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
        "support_bonus",
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
    team_score = float(aggregate.team_score or 0.0)
    ffa_score = float(aggregate.ffa_score or 0.0)
    overall_score = float(aggregate.overall_score or 0.0)
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
            "Team score is normalized across the guild. Harder team lobbies and "
            "recent wins matter most, stacked guild games count less, losses "
            "subtract, and support bonus adds a visible secondary lift."
        ),
        "ffa": (
            "FFA score is normalized across the guild. Larger solo lobbies and "
            "recent wins matter more, while losses subtract mildly."
        ),
        "overall": (
            "Overall score blends normalized Team and FFA performance with a "
            "Team-first target and confidence damping, so tiny samples do not "
            "dominate the board."
        ),
        "support": (
            "Support view ranks the visible support bonus first and still shows "
            "exact troop, gold, and donation action totals from team games."
        ),
    }
    details = {
        "team": {
            "title": "Exact computation",
            "sections": [
                {
                    "title": "Team result raw",
                    "lines": [
                        "recency_weight = 0.4 + 0.6 * 0.5^(days_since_game / 45)",
                        "team_difficulty = sqrt(max(1, inferred_num_teams - 1))",
                        "win delta = team_difficulty * recency_weight / sqrt(guild_stack)",
                        "loss delta = -0.4 * team_difficulty * recency_weight * sqrt(guild_stack)",
                    ],
                },
                {
                    "title": "Support bonus",
                    "lines": [
                        "support volume uses log-scaled troops, gold, and donation actions",
                        "support bonus is normalized across players with positive support raw",
                        "team_score = 0.75 * team_result_index + 0.25 * support_bonus",
                    ],
                },
            ],
        },
        "ffa": {
            "title": "Exact computation",
            "sections": [
                {
                    "title": "FFA raw",
                    "lines": [
                        "ffa_difficulty = sqrt(max(1, total_player_count - 1))",
                        "win delta = ffa_difficulty * recency_weight",
                        "loss delta = -0.25 * ffa_difficulty * recency_weight",
                        "ffa_score is the normalized FFA raw rank",
                    ],
                }
            ],
        },
        "overall": {
            "title": "Exact computation",
            "sections": [
                {
                    "title": "Overall blend",
                    "lines": [
                        "Team and FFA are normalized separately before blending",
                        "base weights target 70% Team and 30% FFA",
                        "each mode is damped by confidence = min(1, games / 25)",
                        "overall_score = blended_mode_score * overall_confidence",
                    ],
                }
            ],
        },
        "support": {
            "title": "Exact computation",
            "sections": [
                {
                    "title": "Support ranking",
                    "lines": [
                        "support_bonus is the normalized support component used by Team score",
                        "support rank uses support bonus first and exact donation totals as extra context",
                    ],
                }
            ],
        },
    }
    return {
        "view": normalized_view,
        "summary": summaries[normalized_view],
        "details": details[normalized_view],
        "factors": {
            "team": [
                "Wins matter most.",
                "Harder lobbies count more.",
                "Stacked guild games count less.",
                "Support bonus stays visible.",
            ],
            "ffa": [
                "FFA ignores support metrics.",
                "Bigger solo lobbies count more.",
                "Losses subtract mildly.",
            ],
            "overall": [
                "Team and FFA are normalized separately.",
                "Small samples count less through confidence damping.",
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
