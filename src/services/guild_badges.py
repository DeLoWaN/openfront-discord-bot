from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from ..data.shared.models import (
    GameParticipant,
    Guild,
    GuildPlayerAggregate,
    GuildPlayerBadge,
    ObservedGame,
)
from .guild_combo_service import COMBO_CONFIRMATION_GAMES, collect_valid_combo_events, format_title
from .openfront_ingestion import _is_ffa_mode, _is_team_mode, normalize_username

BADGE_LEVELS = ("Bronze", "Silver", "Gold")
BADGE_CATALOG: dict[str, dict[str, Any]] = {
    "team-grinder": {
        "label": "Team Grinder",
        "category": "milestone",
        "description": "Play a large volume of Team games for the guild.",
        "levels": {"Bronze": 10, "Silver": 25, "Gold": 50},
    },
    "field-marshal": {
        "label": "Field Marshal",
        "category": "milestone",
        "description": "Accumulate Team wins for the guild.",
        "levels": {"Bronze": 5, "Silver": 15, "Gold": 30},
    },
    "lone-wolf": {
        "label": "Lone Wolf",
        "category": "milestone",
        "description": "Win public FFA games while representing the guild.",
        "levels": {"Bronze": 1, "Silver": 3, "Gold": 7},
    },
    "quartermaster": {
        "label": "Quartermaster",
        "category": "support",
        "description": "Donate heavily through troops or repeated support actions.",
    },
    "war-chest": {
        "label": "War Chest",
        "category": "support",
        "description": "Donate a large amount of gold to allied teammates.",
    },
    "frontline-engine": {
        "label": "Frontline Engine",
        "category": "performance",
        "description": "Accumulate a major volume of attacking troops.",
    },
    "big-game-hunter": {
        "label": "Big Game Hunter",
        "category": "performance",
        "description": "Win in large Team or FFA lobbies.",
    },
    "hot-streak": {
        "label": "Hot Streak",
        "category": "performance",
        "description": "Win three guild-tracked games in a row.",
    },
    "versatile": {
        "label": "Versatile",
        "category": "performance",
        "description": "Win in both Team and FFA.",
    },
    "cartographer": {
        "label": "Cartographer",
        "category": "map",
        "description": "Win on three different maps.",
    },
    "marathon": {
        "label": "Marathon",
        "category": "performance",
        "description": "Win a long game lasting at least 30 minutes.",
    },
    "duo-specialist": {
        "label": "Duo Specialist",
        "category": "combo",
        "description": "Reach a confirmed guild duo roster.",
    },
    "trio-specialist": {
        "label": "Trio Specialist",
        "category": "combo",
        "description": "Reach a confirmed guild trio roster.",
    },
    "quad-specialist": {
        "label": "Quad Specialist",
        "category": "combo",
        "description": "Reach a confirmed guild quad roster.",
    },
}


def _award_rows_for_player(
    guild: Guild,
    normalized_username: str,
    player_id: int | None,
    awarded: list[dict[str, Any]],
    seen: set[tuple[str, str | None]],
    *,
    badge_code: str,
    badge_level: str | None,
    earned_at: datetime | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if earned_at is None:
        return
    key = (badge_code, badge_level)
    if key in seen:
        return
    seen.add(key)
    awarded.append(
        {
            "guild": guild,
            "player": player_id,
            "normalized_username": normalized_username,
            "badge_code": badge_code,
            "badge_level": badge_level,
            "earned_at": earned_at,
            "metadata_json": json.dumps(metadata) if metadata else None,
        }
    )


def _participant_game_time(participant: GameParticipant) -> datetime | None:
    return participant.game.ended_at or participant.game.started_at


def refresh_guild_player_badges(
    guild: Guild,
    *,
    participants: list[GameParticipant] | None = None,
) -> list[GuildPlayerBadge]:
    GuildPlayerBadge.delete().where(GuildPlayerBadge.guild == guild).execute()
    rows = participants or list(
        GameParticipant.select(GameParticipant, ObservedGame)
        .join(ObservedGame)
        .where(GameParticipant.guild == guild)
        .order_by(ObservedGame.started_at, ObservedGame.ended_at, GameParticipant.id)
    )
    rows = sorted(
        rows,
        key=lambda participant: (
            _participant_game_time(participant) is None,
            _participant_game_time(participant) or datetime.min,
            participant.id,
        ),
    )
    state_by_player: dict[str, dict[str, Any]] = {}
    awards: list[dict[str, Any]] = []
    seen_awards: dict[str, set[tuple[str, str | None]]] = defaultdict(set)

    for participant in rows:
        normalized_username = participant.normalized_username
        current = state_by_player.setdefault(
            normalized_username,
            {
                "player_id": participant.player_id,
                "team_games": 0,
                "team_wins": 0,
                "ffa_wins": 0,
                "donated_troops_total": 0,
                "donated_gold_total": 0,
                "donation_action_count": 0,
                "attack_troops_total": 0,
                "consecutive_wins": 0,
                "won_maps": set(),
            },
        )
        if participant.player_id and not current["player_id"]:
            current["player_id"] = participant.player_id
        game_time = _participant_game_time(participant)
        did_win = bool(participant.did_win)
        if _is_team_mode(participant.game.mode_name):
            current["team_games"] += 1
            current["team_wins"] += int(did_win)
        elif _is_ffa_mode(participant.game.mode_name):
            current["ffa_wins"] += int(did_win)
        current["donated_troops_total"] += int(participant.donated_troops_total or 0)
        current["donated_gold_total"] += int(participant.donated_gold_total or 0)
        current["donation_action_count"] += int(participant.donation_action_count or 0)
        current["attack_troops_total"] += int(participant.attack_troops_total or 0)
        current["consecutive_wins"] = current["consecutive_wins"] + 1 if did_win else 0
        if did_win and participant.game.map_name:
            current["won_maps"].add(participant.game.map_name)

        for level in BADGE_LEVELS:
            threshold = BADGE_CATALOG["team-grinder"]["levels"][level]
            if current["team_games"] >= threshold:
                _award_rows_for_player(
                    guild,
                    normalized_username,
                    current["player_id"],
                    awards,
                    seen_awards[normalized_username],
                    badge_code="team-grinder",
                    badge_level=level,
                    earned_at=game_time,
                )
            threshold = BADGE_CATALOG["field-marshal"]["levels"][level]
            if current["team_wins"] >= threshold:
                _award_rows_for_player(
                    guild,
                    normalized_username,
                    current["player_id"],
                    awards,
                    seen_awards[normalized_username],
                    badge_code="field-marshal",
                    badge_level=level,
                    earned_at=game_time,
                )
            threshold = BADGE_CATALOG["lone-wolf"]["levels"][level]
            if current["ffa_wins"] >= threshold:
                _award_rows_for_player(
                    guild,
                    normalized_username,
                    current["player_id"],
                    awards,
                    seen_awards[normalized_username],
                    badge_code="lone-wolf",
                    badge_level=level,
                    earned_at=game_time,
                )

        if (
            current["donation_action_count"] >= 5
            or current["donated_troops_total"] >= 100_000
        ):
            _award_rows_for_player(
                guild,
                normalized_username,
                current["player_id"],
                awards,
                seen_awards[normalized_username],
                badge_code="quartermaster",
                badge_level=None,
                earned_at=game_time,
            )
        if current["donated_gold_total"] >= 250_000:
            _award_rows_for_player(
                guild,
                normalized_username,
                current["player_id"],
                awards,
                seen_awards[normalized_username],
                badge_code="war-chest",
                badge_level=None,
                earned_at=game_time,
            )
        if current["attack_troops_total"] >= 500_000:
            _award_rows_for_player(
                guild,
                normalized_username,
                current["player_id"],
                awards,
                seen_awards[normalized_username],
                badge_code="frontline-engine",
                badge_level=None,
                earned_at=game_time,
            )
        if did_win and (
            (_is_team_mode(participant.game.mode_name) and int(participant.game.num_teams or 0) >= 10)
            or (_is_ffa_mode(participant.game.mode_name) and int(participant.game.total_player_count or 0) >= 16)
        ):
            _award_rows_for_player(
                guild,
                normalized_username,
                current["player_id"],
                awards,
                seen_awards[normalized_username],
                badge_code="big-game-hunter",
                badge_level=None,
                earned_at=game_time,
            )
        if current["consecutive_wins"] >= 3:
            _award_rows_for_player(
                guild,
                normalized_username,
                current["player_id"],
                awards,
                seen_awards[normalized_username],
                badge_code="hot-streak",
                badge_level=None,
                earned_at=game_time,
            )
        if current["team_wins"] >= 1 and current["ffa_wins"] >= 1:
            _award_rows_for_player(
                guild,
                normalized_username,
                current["player_id"],
                awards,
                seen_awards[normalized_username],
                badge_code="versatile",
                badge_level=None,
                earned_at=game_time,
            )
        if len(current["won_maps"]) >= 3:
            _award_rows_for_player(
                guild,
                normalized_username,
                current["player_id"],
                awards,
                seen_awards[normalized_username],
                badge_code="cartographer",
                badge_level=None,
                earned_at=game_time,
            )
        if did_win and int(participant.game.duration_seconds or 0) >= 1_800:
            _award_rows_for_player(
                guild,
                normalized_username,
                current["player_id"],
                awards,
                seen_awards[normalized_username],
                badge_code="marathon",
                badge_level=None,
                earned_at=game_time,
            )

    combo_counts_by_player: dict[tuple[str, str], int] = defaultdict(int)
    combo_badges = {
        "duo": "duo-specialist",
        "trio": "trio-specialist",
        "quad": "quad-specialist",
    }
    for event in collect_valid_combo_events(guild, rows):
        for normalized_username, _display_username, player_id in event.members:
            key = (normalized_username, f"{event.format_slug}:{event.roster_key}")
            combo_counts_by_player[key] += 1
            if combo_counts_by_player[key] != COMBO_CONFIRMATION_GAMES:
                continue
            badge_code = combo_badges[event.format_slug]
            _award_rows_for_player(
                guild,
                normalized_username,
                player_id,
                awards,
                seen_awards[normalized_username],
                badge_code=badge_code,
                badge_level=None,
                earned_at=event.game_time,
                metadata={
                    "format": event.format_slug,
                    "roster_key": event.roster_key,
                    "title": format_title(event.format_slug),
                },
            )

    created: list[GuildPlayerBadge] = []
    for payload in sorted(
        awards,
        key=lambda row: (
            row["earned_at"],
            row["normalized_username"],
            row["badge_code"],
            row["badge_level"] or "",
        ),
    ):
        created.append(GuildPlayerBadge.create(**payload))
    return created


def _badge_definition(badge_code: str) -> dict[str, Any]:
    return BADGE_CATALOG.get(
        badge_code,
        {"label": badge_code.replace("-", " ").title(), "category": "misc"},
    )


def serialize_badge_award(
    award: GuildPlayerBadge,
    *,
    display_username: str | None = None,
) -> dict[str, Any]:
    definition = _badge_definition(award.badge_code)
    metadata = json.loads(award.metadata_json) if award.metadata_json else None
    return {
        "badge_code": award.badge_code,
        "label": definition["label"],
        "category": definition["category"],
        "badge_level": award.badge_level,
        "earned_at": award.earned_at.isoformat(),
        "normalized_username": award.normalized_username,
        "display_username": display_username,
        "metadata": metadata,
    }


def list_player_badges(guild: Guild, normalized_username: str) -> list[dict[str, Any]]:
    normalized = normalize_username(normalized_username)
    awards = list(
        GuildPlayerBadge.select()
        .where(
            (GuildPlayerBadge.guild == guild)
            & (GuildPlayerBadge.normalized_username == normalized)
        )
        .order_by(GuildPlayerBadge.earned_at.desc(), GuildPlayerBadge.badge_code)
    )
    return [serialize_badge_award(award) for award in awards]


def list_recent_badge_awards(guild: Guild, *, limit: int = 6) -> list[dict[str, Any]]:
    display_names = {
        row.normalized_username: row.display_username
        for row in GuildPlayerAggregate.select().where(GuildPlayerAggregate.guild == guild)
    }
    query = (
        GuildPlayerBadge.select()
        .where(GuildPlayerBadge.guild == guild)
        .order_by(GuildPlayerBadge.earned_at.desc(), GuildPlayerBadge.badge_code)
        .limit(limit)
    )
    return [
        serialize_badge_award(
            award,
            display_username=display_names.get(award.normalized_username),
        )
        for award in query
    ]


def build_player_badge_catalog(
    guild: Guild,
    normalized_username: str,
) -> list[dict[str, Any]]:
    awards = list_player_badges(guild, normalized_username)
    awards_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for award in awards:
        awards_by_code[award["badge_code"]].append(award)

    catalog = []
    for badge_code, definition in BADGE_CATALOG.items():
        badge_awards = awards_by_code.get(badge_code, [])
        if "levels" in definition:
            earned_levels = {
                str(award["badge_level"]): award for award in badge_awards if award.get("badge_level")
            }
            levels = []
            for level_name, threshold in definition["levels"].items():
                levels.append(
                    {
                        "name": level_name,
                        "threshold": threshold,
                        "earned": level_name in earned_levels,
                        "earned_at": earned_levels.get(level_name, {}).get("earned_at"),
                    }
                )
            catalog.append(
                {
                    "badge_code": badge_code,
                    "label": definition["label"],
                    "category": definition["category"],
                    "description": definition.get("description"),
                    "is_locked": not any(level["earned"] for level in levels),
                    "levels": levels,
                }
            )
            continue
        earned_award = badge_awards[0] if badge_awards else None
        catalog.append(
            {
                "badge_code": badge_code,
                "label": definition["label"],
                "category": definition["category"],
                "description": definition.get("description"),
                "is_locked": earned_award is None,
                "earned_at": earned_award.get("earned_at") if earned_award else None,
            }
        )
    return catalog
