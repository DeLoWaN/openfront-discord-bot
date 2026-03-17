from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from ..data.shared.models import (
    GameParticipant,
    Guild,
    GuildComboAggregate,
    GuildComboMember,
    ObservedGame,
)
from .guild_sites import list_guild_clan_tags
from .openfront_links import build_openfront_replay_link
from .openfront_ingestion import (
    _infer_players_per_team,
    _is_team_mode,
    normalize_username,
    strip_tracked_clan_tag_prefix,
)

COMBO_FORMAT_SIZES = {
    "duo": 2,
    "trio": 3,
    "quad": 4,
}
COMBO_CONFIRMATION_GAMES = 5


@dataclass(frozen=True)
class ComboEvent:
    format_slug: str
    roster_key: str
    members: tuple[tuple[str, str, int | None], ...]
    did_win: bool
    game_time: datetime | None
    openfront_game_id: str
    map_name: str | None
    mode_name: str | None
    player_teams: str | None
    duration_seconds: int | None


def _combo_format_slug(game: ObservedGame) -> str | None:
    players_per_team = _infer_players_per_team(
        num_teams=game.num_teams,
        player_teams=game.player_teams,
        total_player_count=game.total_player_count,
    )
    for format_slug, expected_size in COMBO_FORMAT_SIZES.items():
        if players_per_team == expected_size:
            return format_slug
    return None


def format_title(format_slug: str) -> str:
    return {
        "duo": "Duos",
        "trio": "Trios",
        "quad": "Quads",
    }.get(format_slug, format_slug.title())


def _player_payloads_for_game(game: ObservedGame) -> dict[str, dict[str, Any]]:
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


def _stats_all_zero(stats: Any) -> bool:
    if not isinstance(stats, dict) or not stats:
        return True
    for value in stats.values():
        if isinstance(value, list):
            if any(str(item or "0") not in {"0", "0.0", ""} for item in value):
                return False
        elif str(value or "0") not in {"0", "0.0", ""}:
            return False
    return True


def _looks_non_spawned(
    participant: GameParticipant,
    player_payload: dict[str, Any] | None,
) -> bool:
    if int(participant.attack_troops_total or 0) > 0:
        return False
    if int(participant.attack_action_count or 0) > 0:
        return False
    if int(participant.donated_troops_total or 0) > 0:
        return False
    if int(participant.donated_gold_total or 0) > 0:
        return False
    if int(participant.donation_action_count or 0) > 0:
        return False
    stats = player_payload.get("stats") if isinstance(player_payload, dict) else None
    return _stats_all_zero(stats)


def _resolved_roster(
    roster: list[GameParticipant],
    expected_size: int,
) -> list[GameParticipant] | None:
    if len(roster) == expected_size:
        return roster
    if len(roster) < expected_size:
        return None
    player_payloads = _player_payloads_for_game(roster[0].game)
    filtered = [
        row
        for row in roster
        if not _looks_non_spawned(row, player_payloads.get(str(row.client_id or "")))
    ]
    if len(filtered) == expected_size:
        return filtered
    return None


def collect_valid_combo_events(
    guild: Guild,
    participants: list[GameParticipant] | None = None,
) -> list[ComboEvent]:
    tracked_tags = set(list_guild_clan_tags(guild))
    source_rows = participants or list(
        GameParticipant.select(GameParticipant, ObservedGame)
        .join(ObservedGame)
        .where(GameParticipant.guild == guild)
        .order_by(ObservedGame.started_at, ObservedGame.ended_at, GameParticipant.id)
    )
    grouped: dict[tuple[int, str, str], list[GameParticipant]] = defaultdict(list)
    for participant in source_rows:
        if not _is_team_mode(participant.game.mode_name):
            continue
        format_slug = _combo_format_slug(participant.game)
        effective_tag = str(participant.effective_clan_tag or "").strip().upper()
        if not format_slug or not effective_tag:
            continue
        grouped[(participant.game_id, effective_tag, format_slug)].append(participant)

    events: list[ComboEvent] = []
    for (_game_id, _effective_tag, format_slug), roster in grouped.items():
        expected_size = COMBO_FORMAT_SIZES[format_slug]
        resolved_roster = _resolved_roster(roster, expected_size)
        if resolved_roster is None:
            continue
        sorted_roster = sorted(resolved_roster, key=lambda row: row.normalized_username)
        members = tuple(
            (
                row.normalized_username,
                strip_tracked_clan_tag_prefix(row.raw_username, tracked_tags),
                row.player_id,
            )
            for row in sorted_roster
        )
        game = sorted_roster[0].game
        game_time = game.ended_at or game.started_at
        events.append(
            ComboEvent(
                format_slug=format_slug,
                roster_key="|".join(member[0] for member in members),
                members=members,
                did_win=any(bool(row.did_win) for row in sorted_roster),
                game_time=game_time,
                openfront_game_id=game.openfront_game_id,
                map_name=game.map_name,
                mode_name=game.mode_name,
                player_teams=game.player_teams,
                duration_seconds=game.duration_seconds,
            )
        )
    events.sort(
        key=lambda event: (
            event.game_time is None,
            event.game_time or datetime.min,
            event.openfront_game_id,
        )
    )
    return events


def refresh_guild_combo_aggregates(
    guild: Guild,
    *,
    participants: list[GameParticipant] | None = None,
) -> list[GuildComboAggregate]:
    combo_ids = GuildComboAggregate.select(GuildComboAggregate.id).where(
        GuildComboAggregate.guild == guild
    )
    GuildComboMember.delete().where(GuildComboMember.combo.in_(combo_ids)).execute()
    GuildComboAggregate.delete().where(GuildComboAggregate.guild == guild).execute()

    events = collect_valid_combo_events(guild, participants)
    aggregated: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        key = (event.format_slug, event.roster_key)
        current = aggregated.setdefault(
            key,
            {
                "members": event.members,
                "games_together": 0,
                "wins_together": 0,
                "first_game_at": event.game_time,
                "last_game_at": event.game_time,
                "last_win_at": event.game_time if event.did_win else None,
            },
        )
        current["games_together"] += 1
        current["wins_together"] += int(event.did_win)
        first_game_at = current.get("first_game_at")
        if first_game_at is None or (
            event.game_time is not None and event.game_time < first_game_at
        ):
            current["first_game_at"] = event.game_time
        last_game_at = current.get("last_game_at")
        if last_game_at is None or (
            event.game_time is not None and event.game_time >= last_game_at
        ):
            current["last_game_at"] = event.game_time
        if event.did_win:
            last_win_at = current.get("last_win_at")
            if last_win_at is None or (
                event.game_time is not None and event.game_time >= last_win_at
            ):
                current["last_win_at"] = event.game_time

    created: list[GuildComboAggregate] = []
    for (format_slug, roster_key), payload in aggregated.items():
        games_together = int(payload["games_together"])
        wins_together = int(payload["wins_together"])
        combo = GuildComboAggregate.create(
            guild=guild,
            format_slug=format_slug,
            roster_key=roster_key,
            games_together=games_together,
            wins_together=wins_together,
            win_rate=round(wins_together / games_together, 4) if games_together else 0.0,
            is_confirmed=1 if games_together >= COMBO_CONFIRMATION_GAMES else 0,
            first_game_at=payload["first_game_at"],
            last_game_at=payload["last_game_at"],
            last_win_at=payload["last_win_at"],
        )
        for slot_index, (normalized_username, display_username, player_id) in enumerate(
            payload["members"]
        ):
            GuildComboMember.create(
                combo=combo,
                player=player_id,
                normalized_username=normalized_username,
                display_username=display_username,
                slot_index=slot_index,
            )
        created.append(combo)
    return created


def _members_for_combos(combos: list[GuildComboAggregate]) -> dict[int, list[GuildComboMember]]:
    if not combos:
        return {}
    combo_ids = [combo.id for combo in combos]
    members_by_combo: dict[int, list[GuildComboMember]] = defaultdict(list)
    query = (
        GuildComboMember.select()
        .where(GuildComboMember.combo.in_(combo_ids))
        .order_by(GuildComboMember.combo_id, GuildComboMember.slot_index)
    )
    for row in query:
        members_by_combo[row.combo_id].append(row)
    return members_by_combo


def _combo_sort_key(combo: GuildComboAggregate) -> tuple[float, int, int, datetime, str]:
    return (
        float(combo.win_rate or 0.0),
        int(combo.games_together or 0),
        int(combo.wins_together or 0),
        combo.last_win_at or datetime.min,
        combo.roster_key,
    )


def _pending_sort_key(combo: GuildComboAggregate) -> tuple[int, float, datetime, str]:
    return (
        int(combo.games_together or 0),
        float(combo.win_rate or 0.0),
        combo.last_game_at or datetime.min,
        combo.roster_key,
    )


def _serialize_combo(
    combo: GuildComboAggregate,
    members_by_combo: dict[int, list[GuildComboMember]],
) -> dict[str, Any]:
    members = members_by_combo.get(combo.id, [])
    return {
        "format": combo.format_slug,
        "title": format_title(combo.format_slug),
        "roster_key": combo.roster_key,
        "members": [
            {
                "normalized_username": member.normalized_username,
                "display_username": member.display_username,
            }
            for member in members
        ],
        "games_together": int(combo.games_together or 0),
        "wins_together": int(combo.wins_together or 0),
        "win_rate": round(float(combo.win_rate or 0.0), 4),
        "status": "confirmed" if combo.is_confirmed else "pending",
        "first_game_at": combo.first_game_at.isoformat() if combo.first_game_at else None,
        "last_game_at": combo.last_game_at.isoformat() if combo.last_game_at else None,
        "last_win_at": combo.last_win_at.isoformat() if combo.last_win_at else None,
    }


def list_combo_rankings(guild: Guild, format_slug: str) -> dict[str, Any]:
    normalized_format = normalize_username(format_slug)
    if normalized_format not in COMBO_FORMAT_SIZES:
        raise ValueError(f"Unsupported combo format: {format_slug}")
    combos = list(
        GuildComboAggregate.select().where(
            (GuildComboAggregate.guild == guild)
            & (GuildComboAggregate.format_slug == normalized_format)
        )
    )
    members_by_combo = _members_for_combos(combos)
    confirmed = sorted(
        [combo for combo in combos if combo.is_confirmed],
        key=_combo_sort_key,
        reverse=True,
    )
    pending = sorted(
        [combo for combo in combos if not combo.is_confirmed],
        key=_pending_sort_key,
        reverse=True,
    )
    return {
        "format": normalized_format,
        "title": format_title(normalized_format),
        "confirmed": [_serialize_combo(combo, members_by_combo) for combo in confirmed],
        "pending": [_serialize_combo(combo, members_by_combo) for combo in pending],
    }


def get_combo_detail(
    guild: Guild,
    format_slug: str,
    roster_key: str,
) -> dict[str, Any] | None:
    normalized_format = normalize_username(format_slug)
    combo = GuildComboAggregate.get_or_none(
        (GuildComboAggregate.guild == guild)
        & (GuildComboAggregate.format_slug == normalized_format)
        & (GuildComboAggregate.roster_key == roster_key)
    )
    if combo is None:
        return None
    members_by_combo = _members_for_combos([combo])
    history = [
        {
            "ended_at": event.game_time.isoformat() if event.game_time else None,
            "did_win": event.did_win,
            "openfront_game_id": event.openfront_game_id,
            "map_name": event.map_name,
            "mode_name": event.mode_name,
            "replay_link": build_openfront_replay_link(event.openfront_game_id),
        }
        for event in collect_valid_combo_events(guild)
        if event.format_slug == normalized_format and event.roster_key == roster_key
    ]
    history.sort(
        key=lambda event: (
            event["ended_at"] is None,
            event["ended_at"] or "",
            event["openfront_game_id"],
        ),
        reverse=True,
    )
    return {
        "combo": _serialize_combo(combo, members_by_combo),
        "history": history,
    }


def list_player_combo_summaries(
    guild: Guild,
    normalized_username: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    normalized = normalize_username(normalized_username)
    memberships = list(
        GuildComboMember.select(GuildComboMember, GuildComboAggregate)
        .join(GuildComboAggregate)
        .where(
            (GuildComboAggregate.guild == guild)
            & (GuildComboMember.normalized_username == normalized)
        )
    )
    if not memberships:
        return []
    combo_ids = [membership.combo_id for membership in memberships]
    combos = list(
        GuildComboAggregate.select().where(GuildComboAggregate.id.in_(combo_ids))
    )
    members_by_combo = _members_for_combos(combos)
    ordered = sorted(
        combos,
        key=lambda combo: (
            int(combo.is_confirmed or 0),
            float(combo.win_rate or 0.0),
            int(combo.games_together or 0),
            combo.last_game_at or datetime.min,
        ),
        reverse=True,
    )
    return [_serialize_combo(combo, members_by_combo) for combo in ordered[:limit]]


def list_player_best_partners(
    guild: Guild,
    normalized_username: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    normalized = normalize_username(normalized_username)
    memberships = list(
        GuildComboMember.select(GuildComboMember, GuildComboAggregate)
        .join(GuildComboAggregate)
        .where(
            (GuildComboAggregate.guild == guild)
            & (GuildComboMember.normalized_username == normalized)
        )
    )
    if not memberships:
        return []
    combo_ids = [membership.combo_id for membership in memberships]
    combos = {
        combo.id: combo
        for combo in GuildComboAggregate.select().where(GuildComboAggregate.id.in_(combo_ids))
    }
    members_by_combo = _members_for_combos(list(combos.values()))
    partners: dict[str, dict[str, Any]] = {}
    for combo_id, combo in combos.items():
        for member in members_by_combo.get(combo_id, []):
            if member.normalized_username == normalized:
                continue
            current = partners.setdefault(
                member.normalized_username,
                {
                    "normalized_username": member.normalized_username,
                    "display_username": member.display_username,
                    "games_together": 0,
                    "wins_together": 0,
                },
            )
            current["games_together"] += int(combo.games_together or 0)
            current["wins_together"] += int(combo.wins_together or 0)
    rows = list(partners.values())
    for row in rows:
        games_together = int(row["games_together"] or 0)
        wins_together = int(row["wins_together"] or 0)
        row["win_rate"] = round(wins_together / games_together, 4) if games_together else 0.0
    rows.sort(
        key=lambda row: (
            row["win_rate"],
            row["games_together"],
            row["wins_together"],
            row["display_username"],
        ),
        reverse=True,
    )
    return rows[:limit]


def combo_counts_by_format(guild: Guild) -> dict[str, dict[str, int]]:
    counts = {
        format_slug: {"confirmed": 0, "pending": 0}
        for format_slug in COMBO_FORMAT_SIZES
    }
    query = GuildComboAggregate.select().where(GuildComboAggregate.guild == guild)
    for combo in query:
        bucket = counts.setdefault(combo.format_slug, {"confirmed": 0, "pending": 0})
        bucket["confirmed" if combo.is_confirmed else "pending"] += 1
    return counts
