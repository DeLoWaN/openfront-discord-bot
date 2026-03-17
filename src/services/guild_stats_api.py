from __future__ import annotations

from typing import Any

from ..data.shared.models import Guild, GuildPlayerAggregate
from .guild_badges import build_player_badge_catalog, list_player_badges
from .guild_combo_service import list_player_best_partners, list_player_combo_summaries
from .guild_engagement_api import (
    build_home_response,
    build_player_timeseries_response,
    build_recent_results_response,
)
from .guild_leaderboard import get_guild_player_profile, player_state_label
from .guild_sites import list_guild_clan_tags
from .openfront_ingestion import strip_tracked_clan_tag_prefix
from .player_linking import compute_linked_profile_stats
from .guild_weekly_rankings import build_player_weekly_summary

SUPPORTED_VIEWS = ("team", "ffa", "support")
DEFAULT_SORT_BY_VIEW = {
    "team": "team_score",
    "ffa": "ffa_score",
    "support": "support_bonus",
}
SORT_FIELDS_BY_VIEW = {
    "team": (
        "display_username",
        "team_score",
        "team_win_count",
        "team_game_count",
        "team_win_rate",
        "team_recent_game_count_30d",
        "support_bonus",
        "win_count",
        "game_count",
        "donated_troops_total",
        "donated_gold_total",
        "donation_action_count",
        "attack_troops_total",
        "last_team_game_at",
        "last_game_at",
    ),
    "ffa": (
        "display_username",
        "ffa_score",
        "ffa_win_count",
        "ffa_game_count",
        "ffa_win_rate",
        "ffa_recent_game_count_30d",
        "win_count",
        "game_count",
        "attack_troops_total",
        "last_ffa_game_at",
        "last_game_at",
    ),
    "support": (
        "display_username",
        "support_bonus",
        "donated_troops_total",
        "donated_gold_total",
        "donation_action_count",
        "team_game_count",
        "team_recent_game_count_30d",
        "team_score",
        "last_team_game_at",
        "last_game_at",
    ),
}
DEFAULT_ORDER = "desc"
COLUMNS_BY_VIEW = {
    "team": (
        {"key": "display_username", "label": "Player", "sortable": True, "sort_key": "display_username"},
        {"key": "team_score", "label": "Team Score", "sortable": True, "sort_key": "team_score"},
        {"key": "team_win_count", "label": "Wins", "sortable": True, "sort_key": "team_win_count"},
        {"key": "ratio", "label": "Ratio", "sortable": False},
        {"key": "win_rate", "label": "Win Rate", "sortable": True, "sort_key": "team_win_rate"},
        {"key": "team_game_count", "label": "Games", "sortable": True, "sort_key": "team_game_count"},
        {
            "key": "team_recent_game_count_30d",
            "label": "Games 30d",
            "sortable": True,
            "sort_key": "team_recent_game_count_30d",
        },
        {"key": "support_bonus", "label": "Support Bonus", "sortable": True, "sort_key": "support_bonus"},
        {"key": "role_label", "label": "Role", "sortable": False},
    ),
    "ffa": (
        {"key": "display_username", "label": "Player", "sortable": True, "sort_key": "display_username"},
        {"key": "ffa_score", "label": "FFA Score", "sortable": True, "sort_key": "ffa_score"},
        {"key": "ffa_win_count", "label": "Wins", "sortable": True, "sort_key": "ffa_win_count"},
        {"key": "ratio", "label": "Ratio", "sortable": False},
        {"key": "win_rate", "label": "Win Rate", "sortable": True, "sort_key": "ffa_win_rate"},
        {"key": "ffa_game_count", "label": "Games", "sortable": True, "sort_key": "ffa_game_count"},
        {
            "key": "ffa_recent_game_count_30d",
            "label": "Games 30d",
            "sortable": True,
            "sort_key": "ffa_recent_game_count_30d",
        },
    ),
    "support": (
        {"key": "display_username", "label": "Player", "sortable": True, "sort_key": "display_username"},
        {"key": "support_bonus", "label": "Support Bonus", "sortable": True, "sort_key": "support_bonus"},
        {
            "key": "donated_troops_total",
            "label": "Troops Donated",
            "sortable": True,
            "sort_key": "donated_troops_total",
        },
        {
            "key": "donated_gold_total",
            "label": "Gold Donated",
            "sortable": True,
            "sort_key": "donated_gold_total",
        },
        {
            "key": "donation_action_count",
            "label": "Donation Actions",
            "sortable": True,
            "sort_key": "donation_action_count",
        },
        {
            "key": "support_recent_game_count_30d",
            "label": "Games 30d",
            "sortable": True,
            "sort_key": "team_recent_game_count_30d",
        },
        {"key": "role_label", "label": "Role", "sortable": False},
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
        "ratio": f"{team_win_count}/{team_game_count}" if team_game_count else "0/0",
        "team_win_rate": round(team_win_rate, 4),
        "win_rate": round(team_win_rate, 4),
        "team_score": round(float(aggregate.team_score or 0.0), 2),
        "score": round(float(aggregate.team_score or 0.0), 2),
        "team_recent_game_count_30d": int(aggregate.team_recent_game_count_30d or 0),
        "games_30d": int(aggregate.team_recent_game_count_30d or 0),
        "ffa_win_count": ffa_win_count,
        "ffa_game_count": ffa_game_count,
        "ffa_ratio": f"{ffa_win_count}/{ffa_game_count}" if ffa_game_count else "0/0",
        "ffa_win_rate": round(ffa_win_rate, 4),
        "ffa_score": round(float(aggregate.ffa_score or 0.0), 2),
        "ffa_recent_game_count_30d": int(aggregate.ffa_recent_game_count_30d or 0),
        "donated_troops_total": aggregate.donated_troops_total,
        "donated_gold_total": aggregate.donated_gold_total,
        "donation_action_count": aggregate.donation_action_count,
        "attack_troops_total": aggregate.attack_troops_total,
        "attack_action_count": aggregate.attack_action_count,
        "support_bonus": round(float(aggregate.support_bonus or 0.0), 2),
        "support_recent_game_count_30d": int(aggregate.team_recent_game_count_30d or 0),
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
    order: str | None = None,
) -> dict[str, Any]:
    normalized_view = _normalized_view(view)
    tracked_tags = set(list_guild_clan_tags(guild))
    rows = [
        _row_payload(row, tracked_tags)
        for row in GuildPlayerAggregate.select().where(GuildPlayerAggregate.guild == guild)
    ]
    if normalized_view == "ffa":
        rows = [row for row in rows if int(row["ffa_game_count"] or 0) > 0]
    for row in rows:
        if normalized_view == "ffa":
            row["ratio"] = row["ffa_ratio"]
            row["win_rate"] = row["ffa_win_rate"]
            row["score"] = row["ffa_score"]
            row["games_30d"] = row["ffa_recent_game_count_30d"]
        elif normalized_view == "support":
            row["score"] = row["support_bonus"]
            row["win_rate"] = row["team_win_rate"]
            row["games_30d"] = row["team_recent_game_count_30d"]
    allowed_sorts = SORT_FIELDS_BY_VIEW[normalized_view]
    sort_field = sort_by if sort_by in allowed_sorts else DEFAULT_SORT_BY_VIEW[normalized_view]
    normalized_order = "asc" if str(order or "").lower() == "asc" else DEFAULT_ORDER
    rows.sort(
        key=lambda row: (
            row.get(sort_field) is None,
            row.get(sort_field),
            row["display_username"],
        ),
        reverse=normalized_order != "asc",
    )
    return {
        "view": normalized_view,
        "default_sort": DEFAULT_SORT_BY_VIEW[normalized_view],
        "default_order": DEFAULT_ORDER,
        "sort_by": sort_field,
        "order": normalized_order,
        "available_sorts": list(allowed_sorts),
        "columns": list(COLUMNS_BY_VIEW[normalized_view]),
        "rows": rows,
    }


def build_scoring_response(view: str) -> dict[str, Any]:
    normalized_view = _normalized_view(view)
    summaries = {
        "team": (
            "Team score is cumulative. Every Team game adds positive value, wins "
            "add more, larger Team lobbies count more, smaller teams count more, "
            "lower tracked guild presence on your team counts more, win rate only "
            "nudges the total, support bonus adds a visible lift, and recent "
            "activity is shown beside the score instead of changing it."
        ),
        "ffa": (
            "FFA score is separate from Team and stays cumulative. Every guild-"
            "relevant FFA game adds positive value, wins add more, larger "
            "lobbies count more, and recent activity is shown beside the score "
            "instead of decaying it."
        ),
        "support": (
            "Support ranks the visible support bonus first and still shows the "
            "exact troop, gold, and donation totals behind it. The bonus only "
            "adds to Team score; it never subtracts from frontliners."
        ),
    }
    details = {
        "team": {
            "title": "Exact computation",
            "sections": [
                {
                    "title": "Team core score",
                    "lines": [
                        "team_count_factor = 1 + 0.25 * log2(max(2, inferred_num_teams))",
                        "small_team_factor = 1 + 0.15 * log2(max(1, 6 / players_per_team))",
                        "guild_presence_factor = 1 + 0.25 * (1 - min(players_per_team, tracked_guild_teammates) / players_per_team)",
                        "difficulty_weight = team_count_factor * small_team_factor * guild_presence_factor",
                        "presence_points_per_game = 10 * difficulty_weight",
                        "win_bonus_points_per_win = 6 * difficulty_weight",
                        "core_team_score = (sum(presence) + sum(win_bonus)) * (0.85 + 0.30 * team_win_rate)",
                    ],
                },
                {
                    "title": "Support bonus",
                    "lines": [
                        "support_raw = log1p(troops / 100000) + 0.7 * log1p(gold / 100000) + 0.5 * log1p(donation_actions)",
                        "support_scaled = 25 * support_raw * (0.6 + 0.4 * support_share)",
                        "support_bonus = min(core_team_score * 0.20, support_scaled)",
                        "team_score = core_team_score + support_bonus",
                    ],
                },
                {
                    "title": "Recent activity metadata",
                    "lines": [
                        "team_recent_game_count_30d counts Team games in the last 30 days",
                        "last_team_game_at shows the latest observed Team game timestamp",
                        "recent activity is displayed beside the score and does not decay the score",
                    ],
                },
            ],
        },
        "ffa": {
            "title": "Exact computation",
            "sections": [
                {
                    "title": "FFA score",
                    "lines": [
                        "difficulty_weight = 1 + 0.20 * log2(max(2, total_player_count))",
                        "presence_points_per_game = 10 * difficulty_weight",
                        "win_bonus_points_per_win = 6 * difficulty_weight",
                        "ffa_score = (sum(presence) + sum(win_bonus)) * (0.85 + 0.30 * ffa_win_rate)",
                        "recent activity is exposed beside the score through last_ffa_game_at and ffa_recent_game_count_30d",
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
                        "support_bonus uses the same additive bonus value shown on Team rows",
                        "support rank sorts by support_bonus first, then donation totals for additional context",
                        "support recent activity uses the Team recent-game window because support only comes from Team games",
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
                "Every Team game adds positive score.",
                "Wins add extra score on top of participation.",
                "Bigger Team lobbies are worth more.",
                "Smaller players-per-team formats are worth more.",
                "Fewer tracked guild teammates on the same team are worth more.",
                "Support bonus stays visible and additive.",
            ],
            "ffa": [
                "FFA is scored separately from Team.",
                "Every guild-relevant FFA game adds positive score.",
                "Bigger FFA lobbies are worth more.",
                "Recent activity is context, not score decay.",
            ],
            "support": [
                "Support only comes from Team donation metrics.",
                "Support bonus is visible on Team and Support views.",
                "The bonus never subtracts points from frontliners.",
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
    badges = list_player_badges(guild, normalized_username)
    best_partners = list_player_best_partners(guild, normalized_username)
    combo_summaries = list_player_combo_summaries(guild, normalized_username)
    badge_catalog = build_player_badge_catalog(guild, normalized_username)
    weekly_summary = build_player_weekly_summary(guild, normalized_username, scope="team")
    response = {
        "player": player,
        "badges": badges,
        "badge_catalog": badge_catalog,
        "best_partners": best_partners,
        "combo_summaries": combo_summaries,
        "weekly_summary": weekly_summary,
        "sections": {
            "team": {
                "score": player["team_score"],
                "wins": player["team_win_count"],
                "games": player["team_game_count"],
                "score_note_label": "Wins / Games",
                "win_rate": player["team_win_rate"],
                "recent_games_30d": player["team_recent_game_count_30d"],
                "last_game_at": player["last_team_game_at"],
            },
            "ffa": {
                "score": player["ffa_score"],
                "wins": player["ffa_win_count"],
                "games": player["ffa_game_count"],
                "score_note_label": "Wins / Games",
                "win_rate": player["ffa_win_rate"],
                "recent_games_30d": player["ffa_recent_game_count_30d"],
                "last_game_at": player["last_ffa_game_at"],
            },
            "support": {
                "troops_donated": player["donated_troops_total"],
                "gold_donated": player["donated_gold_total"],
                "donation_actions": player["donation_action_count"],
                "support_bonus": player["support_bonus"],
                "role_label": player["role_label"],
                "recent_games_30d": player["support_recent_game_count_30d"],
                "last_game_at": player["last_team_game_at"],
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
