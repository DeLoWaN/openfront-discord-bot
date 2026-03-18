from __future__ import annotations

import asyncio
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from ..data.shared.models import (
    GameParticipant,
    Guild,
    GuildClanTag,
    GuildPlayerAggregate,
    ObservedGame,
)

_CLAN_TAG_RE = re.compile(r"\[([A-Za-z0-9]+)\]")
_LEADING_CLAN_TAG_RE = re.compile(r"^\s*\[([A-Za-z0-9]+)\]\s*(.*)$")
_TEAM_ROLE_LABEL_MIN_GAMES = 5
_TEAM_ROLE_LABEL_DOMINANT_SHARE = 0.55
_ACTIVE_TEAM_ROLE_LABELS = ("Frontliner", "Hybrid", "Backliner")


@dataclass(frozen=True)
class ClanTagResolution:
    effective_tag: str | None
    source: str


@dataclass(frozen=True)
class GameIngestionSummary:
    game_id: str | None
    matched_guild_ids: set[int]
    participant_count: int


@dataclass(frozen=True)
class BackfillSummary:
    games_seen: int
    games_ingested: int
    affected_guild_ids: set[int]


def normalize_username(username: str | None) -> str:
    return str(username or "").strip().lower()


def strip_tracked_clan_tag_prefix(
    username: str | None,
    tracked_tags: Iterable[str] | None,
) -> str:
    raw_username = str(username or "").strip()
    if not raw_username:
        return ""
    tracked_tag_set = {
        str(tag).strip().upper()
        for tag in (tracked_tags or [])
        if str(tag).strip()
    }
    if not tracked_tag_set:
        return raw_username
    match = _LEADING_CLAN_TAG_RE.match(raw_username)
    if match is None:
        return raw_username
    if match.group(1).upper() not in tracked_tag_set:
        return raw_username
    stripped_username = match.group(2).strip()
    return stripped_username or raw_username


def normalize_observed_username(
    username: str | None,
    tracked_tags: Iterable[str] | None,
) -> str:
    return normalize_username(strip_tracked_clan_tag_prefix(username, tracked_tags))


def resolve_effective_clan_tag(
    raw_clan_tag: str | None,
    username: str | None,
) -> ClanTagResolution:
    if raw_clan_tag and str(raw_clan_tag).strip():
        return ClanTagResolution(str(raw_clan_tag).strip().upper(), "api")
    match = _CLAN_TAG_RE.search(str(username or ""))
    if match:
        return ClanTagResolution(match.group(1).upper(), "username")
    return ClanTagResolution(None, "missing")


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        raw = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


def _parse_epoch_millis(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=timezone.utc).replace(
            tzinfo=None
        )
    return None


def _extract_game_id(payload: dict[str, Any]) -> str | None:
    info = payload.get("info", payload)
    for key in ("gameID", "gameId", "game", "id"):
        value = info.get(key) or payload.get(key)
        if value:
            return str(value)
    return None


def _extract_game_type(info: dict[str, Any]) -> str:
    config = info.get("config", {})
    return str(config.get("gameType") or info.get("gameType") or "").upper()


def _extract_game_players(info: dict[str, Any]) -> list[dict[str, Any]]:
    players = info.get("players")
    if isinstance(players, list):
        return [player for player in players if isinstance(player, dict)]
    return []


def _safe_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _field_int(value: Any) -> int:
    return int(value)


def _field_str(value: Any) -> str:
    return str(value)


def _extract_turn_metrics(payload: dict[str, Any]) -> dict[str, dict[str, int]]:
    turns = payload.get("turns")
    if not isinstance(turns, list):
        return {}

    metrics: dict[str, dict[str, int]] = {}
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        intents = turn.get("intents")
        if not isinstance(intents, list):
            continue
        for intent in intents:
            if not isinstance(intent, dict):
                continue
            client_id = str(intent.get("clientID") or "").strip()
            if not client_id:
                continue
            client_metrics = metrics.setdefault(
                client_id,
                {
                    "attack_troops_total": 0,
                    "attack_action_count": 0,
                    "donated_troops_total": 0,
                    "donated_gold_total": 0,
                    "donation_action_count": 0,
                },
            )
            intent_type = str(intent.get("type") or "").strip()
            if intent_type == "attack":
                client_metrics["attack_troops_total"] += _safe_int(intent.get("troops"))
                client_metrics["attack_action_count"] += 1
            elif intent_type == "donate_troops":
                client_metrics["donated_troops_total"] += _safe_int(intent.get("troops"))
                client_metrics["donation_action_count"] += 1
            elif intent_type == "donate_gold":
                client_metrics["donated_gold_total"] += _safe_int(intent.get("gold"))
                client_metrics["donation_action_count"] += 1
    return metrics


async def _fetch_game_payload(
    client: Any,
    game_id: str,
    *,
    include_turns: bool,
) -> dict[str, Any]:
    try:
        return await client.fetch_game(game_id, include_turns=include_turns)
    except TypeError:
        return await client.fetch_game(game_id)


def _extract_winner_client_ids(
    info: dict[str, Any], players: list[dict[str, Any]]
) -> set[str]:
    winners_raw = info.get("winner")
    if not isinstance(winners_raw, list):
        return set()
    player_ids = {
        str(player.get("clientID"))
        for player in players
        if player.get("clientID") not in (None, "")
    }
    return {str(item) for item in winners_raw if str(item) in player_ids}


def _tracked_guilds_by_tag() -> dict[str, list[Guild]]:
    tag_map: dict[str, list[Guild]] = {}
    query = GuildClanTag.select(GuildClanTag, Guild).join(Guild)
    for row in query:
        tag_map.setdefault(row.tag_text.upper(), []).append(row.guild)
    return tag_map


def _tracked_tags_by_guild_id() -> dict[int, set[str]]:
    tracked_tags: dict[int, set[str]] = {}
    for row in GuildClanTag.select():
        tracked_tags.setdefault(row.guild_id, set()).add(row.tag_text.upper())
    return tracked_tags


def _upsert_observed_game(payload: dict[str, Any]) -> ObservedGame:
    info = payload.get("info", payload)
    config = info.get("config", {})
    game_id = _extract_game_id(payload)
    if not game_id:
        raise ValueError("Observed game payload is missing a game id")
    game = ObservedGame.get_or_none(ObservedGame.openfront_game_id == game_id)
    if game is None:
        game = ObservedGame.create(
            openfront_game_id=game_id,
            game_type=_extract_game_type(info),
            map_name=config.get("gameMap"),
            mode_name=config.get("gameMode"),
            player_teams=config.get("playerTeams"),
            num_teams=info.get("numTeams"),
            total_player_count=info.get("totalPlayerCount")
            or config.get("maxPlayers"),
            started_at=_parse_epoch_millis(info.get("start"))
            or _parse_iso_datetime(info.get("start")),
            ended_at=_parse_epoch_millis(info.get("end"))
            or _parse_iso_datetime(info.get("end")),
            duration_seconds=info.get("duration"),
            raw_payload=json.dumps(payload),
        )
    else:
        game.game_type = _extract_game_type(info)
        game.map_name = config.get("gameMap")
        game.mode_name = config.get("gameMode")
        game.player_teams = config.get("playerTeams")
        game.num_teams = info.get("numTeams")
        game.total_player_count = info.get("totalPlayerCount") or config.get("maxPlayers")
        game.started_at = _parse_epoch_millis(info.get("start")) or _parse_iso_datetime(
            info.get("start")
        )
        game.ended_at = _parse_epoch_millis(info.get("end")) or _parse_iso_datetime(
            info.get("end")
        )
        game.duration_seconds = info.get("duration")
        game.raw_payload = json.dumps(payload)
        game.save()
    return game


def ingest_game_payload(
    payload: dict[str, Any],
    *,
    refresh_aggregates: bool = True,
) -> GameIngestionSummary:
    info = payload.get("info", payload)
    if _extract_game_type(info) != "PUBLIC":
        return GameIngestionSummary(_extract_game_id(payload), set(), 0)

    players = _extract_game_players(info)
    if not players:
        return GameIngestionSummary(_extract_game_id(payload), set(), 0)

    tracked_guilds = _tracked_guilds_by_tag()
    tracked_tags_by_guild_id = _tracked_tags_by_guild_id()
    turn_metrics = _extract_turn_metrics(payload)
    matched_rows: list[dict[str, Any]] = []
    matched_guild_ids: set[int] = set()
    winner_client_ids = _extract_winner_client_ids(info, players)

    for player in players:
        username = str(player.get("username") or "").strip()
        resolution = resolve_effective_clan_tag(player.get("clanTag"), username)
        if not resolution.effective_tag:
            continue
        guilds = tracked_guilds.get(resolution.effective_tag, [])
        if not guilds:
            continue
        metrics = turn_metrics.get(str(player.get("clientID") or "").strip(), {})
        for guild in guilds:
            normalized_username = normalize_observed_username(
                username,
                tracked_tags_by_guild_id.get(_field_int(guild.id), set()),
            )
            if not normalized_username:
                continue
            matched_guild_ids.add(_field_int(guild.id))
            matched_rows.append(
                {
                    "guild": guild,
                    "raw_username": username,
                    "normalized_username": normalized_username,
                    "raw_clan_tag": (
                        str(player.get("clanTag")).strip().upper()
                        if player.get("clanTag")
                        else None
                    ),
                    "effective_clan_tag": resolution.effective_tag,
                    "clan_tag_source": resolution.source,
                    "client_id": str(player.get("clientID") or ""),
                    "did_win": 1
                    if str(player.get("clientID") or "") in winner_client_ids
                    else 0,
                    "attack_troops_total": int(metrics.get("attack_troops_total", 0)),
                    "attack_action_count": int(metrics.get("attack_action_count", 0)),
                    "donated_troops_total": int(metrics.get("donated_troops_total", 0)),
                    "donated_gold_total": int(metrics.get("donated_gold_total", 0)),
                    "donation_action_count": int(metrics.get("donation_action_count", 0)),
                }
            )

    if not matched_rows:
        return GameIngestionSummary(_extract_game_id(payload), set(), 0)

    game = _upsert_observed_game(payload)
    GameParticipant.delete().where(GameParticipant.game == game).execute()
    for row in matched_rows:
        GameParticipant.create(game=game, **row)

    if refresh_aggregates:
        for guild_id in matched_guild_ids:
            refresh_guild_player_aggregates(guild_id)

    return GameIngestionSummary(
        _field_str(game.openfront_game_id),
        matched_guild_ids,
        len(matched_rows),
    )


def _is_team_mode(mode_name: str | None) -> bool:
    return str(mode_name or "").strip().lower() == "team"


def _is_ffa_mode(mode_name: str | None) -> bool:
    return str(mode_name or "").strip().lower() == "free for all"


def _infer_team_count(
    *,
    num_teams: Any,
    player_teams: Any,
    total_player_count: Any,
) -> int | None:
    explicit_num_teams = _safe_int(num_teams)
    if explicit_num_teams > 1:
        return explicit_num_teams

    if isinstance(player_teams, (int, float)):
        numeric_teams = int(player_teams)
        return numeric_teams if numeric_teams > 1 else None

    label = str(player_teams or "").strip()
    if not label:
        return None
    if label.isdigit():
        numeric_teams = int(label)
        return numeric_teams if numeric_teams > 1 else None

    named_team_sizes = {"duos": 2, "trios": 3, "quads": 4}
    players_per_team = named_team_sizes.get(label.lower())
    total_players = _safe_int(total_player_count)
    if players_per_team and total_players > 0 and total_players % players_per_team == 0:
        inferred_num_teams = total_players // players_per_team
        return inferred_num_teams if inferred_num_teams > 1 else None

    return None


def _infer_players_per_team(
    *,
    num_teams: Any,
    player_teams: Any,
    total_player_count: Any,
) -> int | None:
    if isinstance(player_teams, (int, float)):
        numeric_team_size = int(player_teams)
        return numeric_team_size if numeric_team_size > 0 else None

    label = str(player_teams or "").strip()
    if label.isdigit():
        numeric_team_size = int(label)
        return numeric_team_size if numeric_team_size > 0 else None

    named_team_sizes = {"duos": 2, "trios": 3, "quads": 4}
    named_team_size = named_team_sizes.get(label.lower())
    if named_team_size:
        return named_team_size

    inferred_num_teams = _infer_team_count(
        num_teams=num_teams,
        player_teams=player_teams,
        total_player_count=total_player_count,
    )
    total_players = _safe_int(total_player_count)
    if inferred_num_teams and total_players > 0 and total_players % inferred_num_teams == 0:
        players_per_team = total_players // inferred_num_teams
        return players_per_team if players_per_team > 0 else None
    return None


def _team_difficulty_weight(
    inferred_num_teams: int | None,
    *,
    players_per_team: int | None = None,
    tracked_guild_teammates: int | None = None,
) -> float:
    team_count = inferred_num_teams if inferred_num_teams and inferred_num_teams > 1 else 2
    team_count_factor = 1.0 + (0.25 * math.log2(max(2, team_count)))
    if not players_per_team or players_per_team <= 0:
        return team_count_factor
    small_team_factor = 1.0 + (0.15 * math.log2(max(1.0, 6.0 / players_per_team)))
    tracked_presence = max(0, min(players_per_team, int(tracked_guild_teammates or 0)))
    guild_presence_factor = 1.0 + (
        0.25 * (1.0 - (tracked_presence / players_per_team))
    )
    return team_count_factor * small_team_factor * guild_presence_factor


def _team_game_points(
    *,
    inferred_num_teams: int | None,
    players_per_team: int | None = None,
    tracked_guild_teammates: int | None = None,
    did_win: bool,
) -> float:
    difficulty_weight = _team_difficulty_weight(
        inferred_num_teams,
        players_per_team=players_per_team,
        tracked_guild_teammates=tracked_guild_teammates,
    )
    points = 10.0 * difficulty_weight
    if did_win:
        points += 6.0 * difficulty_weight
    return points


def _win_rate_multiplier(win_count: int, game_count: int) -> float:
    if game_count <= 0:
        return 0.0
    win_rate = max(0.0, min(1.0, win_count / game_count))
    return 0.85 + (0.30 * win_rate)


def _support_share(
    *,
    donated_troops_total: int,
    donated_gold_total: int,
    donation_action_count: int,
    attack_troops_total: int,
) -> float:
    denominator = donated_troops_total + attack_troops_total
    if denominator > 0:
        return donated_troops_total / denominator
    if donated_troops_total > 0 or donated_gold_total > 0 or donation_action_count > 0:
        return 1.0
    return 0.0


def _compute_support_bonus(payload: dict[str, Any], core_team_score: float) -> float:
    if core_team_score <= 0.0:
        return 0.0

    donated_troops_total = _field_int(payload.get("donated_troops_total") or 0)
    donated_gold_total = _field_int(payload.get("donated_gold_total") or 0)
    donation_action_count = _field_int(payload.get("donation_action_count") or 0)
    attack_troops_total = _field_int(payload.get("attack_troops_total") or 0)
    if donated_troops_total <= 0 and donated_gold_total <= 0 and donation_action_count <= 0:
        return 0.0

    support_raw = math.log1p(max(donated_troops_total, 0) / 100_000.0)
    support_raw += 0.7 * math.log1p(max(donated_gold_total, 0) / 100_000.0)
    support_raw += 0.5 * math.log1p(max(donation_action_count, 0))
    support_scaled = 25.0 * support_raw * (
        0.6
        + (
            0.4
            * _support_share(
                donated_troops_total=donated_troops_total,
                donated_gold_total=donated_gold_total,
                donation_action_count=donation_action_count,
                attack_troops_total=attack_troops_total,
            )
        )
    )
    return min(core_team_score * 0.20, support_scaled)


def _player_payload_map(game: ObservedGame | None) -> dict[str, dict[str, Any]]:
    if game is None or not game.raw_payload:
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
        return False
    for value in stats.values():
        if isinstance(value, list):
            if any(str(item or "0") not in {"0", "0.0", ""} for item in value):
                return False
        elif str(value or "0") not in {"0", "0.0", ""}:
            return False
    return True


def _participant_is_no_spawn(
    participant: GameParticipant,
    player_payload: dict[str, Any] | None = None,
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


def _ffa_difficulty_weight(total_player_count: int | None) -> float:
    player_count = total_player_count if total_player_count and total_player_count > 1 else 2
    return 1.0 + (0.20 * math.log2(max(2, player_count)))


def _ffa_game_points(*, total_player_count: int | None, did_win: bool) -> float:
    difficulty_weight = _ffa_difficulty_weight(total_player_count)
    points = 10.0 * difficulty_weight
    if did_win:
        points += 6.0 * difficulty_weight
    return points


def _is_recent_game(
    game_time: datetime | None,
    *,
    cutoff: datetime,
) -> bool:
    return bool(game_time and game_time >= cutoff)


def _compute_team_game_role(
    *,
    donated_troops_total: int,
    donation_action_count: int,
    attack_troops_total: int,
    attack_action_count: int,
) -> str:
    donated_troops_total = int(donated_troops_total)
    donation_action_count = int(donation_action_count)
    attack_troops_total = int(attack_troops_total)
    attack_action_count = int(attack_action_count)
    denominator = donated_troops_total + attack_troops_total
    support_share = donated_troops_total / denominator if denominator > 0 else 0.0

    if donation_action_count > 0 and support_share >= 0.45:
        return "Backliner"
    if donation_action_count > 0 and attack_action_count > 0:
        return "Hybrid"
    if donation_action_count > 0 and attack_action_count == 0:
        return "Backliner"
    if attack_troops_total > 0 or attack_action_count > 0:
        return "Frontliner"
    return "Flexible"


def _compute_role_label(payload: dict[str, Any]) -> str:
    team_game_count = int(payload.get("team_game_count") or 0)
    if team_game_count < _TEAM_ROLE_LABEL_MIN_GAMES:
        return "Flexible"

    role_counts = payload.get("_team_role_counts") or {}
    active_games = sum(int(role_counts.get(label, 0) or 0) for label in _ACTIVE_TEAM_ROLE_LABELS)
    if active_games <= 0:
        return "Flexible"

    frontliner_share = int(role_counts.get("Frontliner", 0) or 0) / active_games
    backliner_share = int(role_counts.get("Backliner", 0) or 0) / active_games

    if frontliner_share >= _TEAM_ROLE_LABEL_DOMINANT_SHARE:
        return "Frontliner"
    if backliner_share >= _TEAM_ROLE_LABEL_DOMINANT_SHARE:
        return "Backliner"
    return "Hybrid"


def _initial_team_role_counts() -> dict[str, int]:
    return {label: 0 for label in (*_ACTIVE_TEAM_ROLE_LABELS, "Flexible")}


def _record_team_game_role(payload: dict[str, Any], participant: GameParticipant) -> None:
    team_role_counts = payload.setdefault("_team_role_counts", _initial_team_role_counts())
    game_role = _compute_team_game_role(
        donated_troops_total=_field_int(participant.donated_troops_total),
        donation_action_count=_field_int(participant.donation_action_count),
        attack_troops_total=_field_int(participant.attack_troops_total),
        attack_action_count=_field_int(participant.attack_action_count),
    )
    team_role_counts[game_role] = int(team_role_counts.get(game_role, 0) or 0) + 1


def _tracked_team_presence_counts(
    participants: list[GameParticipant],
) -> dict[tuple[int, str], int]:
    counts: dict[tuple[int, str], int] = {}
    for participant in participants:
        if not _is_team_mode(participant.game.mode_name):
            continue
        effective_tag = str(participant.effective_clan_tag or "").strip().upper()
        if not effective_tag:
            continue
        key = (participant.game_id, effective_tag)
        counts[key] = counts.get(key, 0) + 1
    return counts


def refresh_guild_player_aggregates(
    guild_id: int | Guild,
    *,
    now: datetime | None = None,
) -> list[GuildPlayerAggregate]:
    guild = guild_id if isinstance(guild_id, Guild) else Guild.get_by_id(guild_id)
    tracked_tags = _tracked_tags_by_guild_id().get(_field_int(guild.id), set())
    reference_now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    recent_cutoff = reference_now - timedelta(days=30)
    GuildPlayerAggregate.delete().where(GuildPlayerAggregate.guild == guild).execute()
    participants = list(
        GameParticipant.select(GameParticipant, ObservedGame)
        .join(ObservedGame)
        .where(GameParticipant.guild == guild)
        .order_by(ObservedGame.started_at, ObservedGame.ended_at, GameParticipant.id)
    )
    tracked_team_presence = _tracked_team_presence_counts(participants)
    player_payloads_by_game = {
        participant.game_id: _player_payload_map(participant.game) for participant in participants
    }

    grouped: dict[str, dict[str, Any]] = {}
    for participant in participants:
        key = participant.normalized_username
        game_time = participant.game.ended_at or participant.game.started_at
        current = grouped.setdefault(
            key,
            {
                "player": participant.player,
                "display_username": strip_tracked_clan_tag_prefix(
                    participant.raw_username,
                    tracked_tags,
                ),
                "normalized_username": participant.normalized_username,
                "last_observed_clan_tag": participant.effective_clan_tag,
                "win_count": 0,
                "game_count": 0,
                "team_win_count": 0,
                "team_game_count": 0,
                "ffa_win_count": 0,
                "ffa_game_count": 0,
                "donated_troops_total": 0,
                "donated_gold_total": 0,
                "donation_action_count": 0,
                "attack_troops_total": 0,
                "attack_action_count": 0,
                "support_bonus": 0.0,
                "team_score": 0.0,
                "ffa_score": 0.0,
                "role_label": None,
                "team_recent_game_count_30d": 0,
                "ffa_recent_game_count_30d": 0,
                "last_team_game_at": None,
                "last_ffa_game_at": None,
                "last_game_at": game_time,
                "_team_presence_score": 0.0,
                "_team_result_score": 0.0,
                "_ffa_presence_score": 0.0,
                "_ffa_result_score": 0.0,
                "_team_role_counts": _initial_team_role_counts(),
            },
        )
        current["win_count"] += int(bool(participant.did_win))
        current["game_count"] += 1
        current["donated_troops_total"] += participant.donated_troops_total
        current["donated_gold_total"] += participant.donated_gold_total
        current["donation_action_count"] += participant.donation_action_count
        current["attack_troops_total"] += participant.attack_troops_total
        current["attack_action_count"] += participant.attack_action_count
        if participant.player_id and not current["player"]:
            current["player"] = participant.player
        if game_time and (
            current["last_game_at"] is None or game_time >= current["last_game_at"]
        ):
            current["display_username"] = strip_tracked_clan_tag_prefix(
                participant.raw_username,
                tracked_tags,
            )
            current["last_observed_clan_tag"] = participant.effective_clan_tag
            current["last_game_at"] = game_time

        if _is_team_mode(participant.game.mode_name):
            current["team_game_count"] += 1
            current["team_win_count"] += int(bool(participant.did_win))
            is_no_spawn = _participant_is_no_spawn(
                participant,
                player_payloads_by_game.get(participant.game_id, {}).get(
                    str(participant.client_id or "")
                ),
            )
            inferred_num_teams = _infer_team_count(
                num_teams=participant.game.num_teams,
                player_teams=participant.game.player_teams,
                total_player_count=participant.game.total_player_count,
            )
            players_per_team = _infer_players_per_team(
                num_teams=participant.game.num_teams,
                player_teams=participant.game.player_teams,
                total_player_count=participant.game.total_player_count,
            )
            tracked_guild_teammates = tracked_team_presence.get(
                (participant.game_id, str(participant.effective_clan_tag or "").upper()),
                1,
            )
            difficulty_weight = _team_difficulty_weight(
                inferred_num_teams,
                players_per_team=players_per_team,
                tracked_guild_teammates=tracked_guild_teammates,
            )
            if not is_no_spawn:
                current["_team_presence_score"] += 10.0 * difficulty_weight
                if participant.did_win:
                    current["_team_result_score"] += 6.0 * difficulty_weight
                _record_team_game_role(current, participant)
            if _is_recent_game(game_time, cutoff=recent_cutoff):
                current["team_recent_game_count_30d"] += 1
            if game_time and (
                current["last_team_game_at"] is None
                or game_time >= current["last_team_game_at"]
            ):
                current["last_team_game_at"] = game_time
        elif _is_ffa_mode(participant.game.mode_name):
            current["ffa_game_count"] += 1
            current["ffa_win_count"] += int(bool(participant.did_win))
            difficulty_weight = _ffa_difficulty_weight(participant.game.total_player_count)
            current["_ffa_presence_score"] += 10.0 * difficulty_weight
            if participant.did_win:
                current["_ffa_result_score"] += 6.0 * difficulty_weight
            if _is_recent_game(game_time, cutoff=recent_cutoff):
                current["ffa_recent_game_count_30d"] += 1
            if game_time and (
                current["last_ffa_game_at"] is None
                or game_time >= current["last_ffa_game_at"]
            ):
                current["last_ffa_game_at"] = game_time

    payloads = list(grouped.values())
    created: list[GuildPlayerAggregate] = []
    for payload in payloads:
        team_game_count = int(payload["team_game_count"])
        team_win_count = int(payload["team_win_count"])
        ffa_game_count = int(payload["ffa_game_count"])
        ffa_win_count = int(payload["ffa_win_count"])

        core_team_score = 0.0
        if team_game_count > 0:
            core_team_score = (
                float(payload["_team_presence_score"] or 0.0)
                + float(payload["_team_result_score"] or 0.0)
            ) * _win_rate_multiplier(team_win_count, team_game_count)
        payload["support_bonus"] = round(_compute_support_bonus(payload, core_team_score), 2)
        payload["team_score"] = round(core_team_score + payload["support_bonus"], 2)

        ffa_score = 0.0
        if ffa_game_count > 0:
            ffa_score = (
                float(payload["_ffa_presence_score"] or 0.0)
                + float(payload["_ffa_result_score"] or 0.0)
            ) * _win_rate_multiplier(ffa_win_count, ffa_game_count)
        payload["ffa_score"] = round(ffa_score, 2)
        payload["role_label"] = _compute_role_label(payload)

        payload.pop("_team_presence_score", None)
        payload.pop("_team_result_score", None)
        payload.pop("_ffa_presence_score", None)
        payload.pop("_ffa_result_score", None)
        payload.pop("_team_role_counts", None)
        created.append(GuildPlayerAggregate.create(guild=guild, **payload))

    from .guild_badges import refresh_guild_player_badges
    from .guild_combo_service import refresh_guild_combo_aggregates
    from .guild_read_models import refresh_guild_read_models

    refresh_guild_combo_aggregates(guild, participants=participants)
    refresh_guild_player_badges(guild, participants=participants)
    refresh_guild_read_models(guild, participants=participants)
    return created


async def backfill_public_games_async(
    client: Any,
    *,
    start: datetime,
    end: datetime,
) -> BackfillSummary:
    games = list(await client.fetch_public_games(start, end))
    affected_guild_ids: set[int] = set()
    games_ingested = 0

    for summary in games:
        game_id = _extract_game_id(summary)
        if not game_id:
            continue
        include_turns = str(summary.get("mode") or "").strip().lower() == "team"
        payload = await _fetch_game_payload(
            client,
            game_id,
            include_turns=include_turns,
        )
        ingestion_summary = ingest_game_payload(payload, refresh_aggregates=False)
        if ingestion_summary.matched_guild_ids:
            games_ingested += 1
            affected_guild_ids.update(ingestion_summary.matched_guild_ids)

    for guild_id in affected_guild_ids:
        refresh_guild_player_aggregates(guild_id)

    return BackfillSummary(
        games_seen=len(games),
        games_ingested=games_ingested,
        affected_guild_ids=affected_guild_ids,
    )


def backfill_public_games(
    client: Any,
    *,
    start: datetime,
    end: datetime,
) -> BackfillSummary:
    return asyncio.run(backfill_public_games_async(client, start=start, end=end))
