from __future__ import annotations

from ..data.shared.models import Guild, GuildPlayerAggregate
from .openfront_ingestion import normalize_username


def list_guild_leaderboard(guild: Guild) -> list[GuildPlayerAggregate]:
    query = (
        GuildPlayerAggregate.select()
        .where(GuildPlayerAggregate.guild == guild)
        .order_by(
            GuildPlayerAggregate.win_count.desc(),
            GuildPlayerAggregate.game_count.desc(),
            GuildPlayerAggregate.display_username,
        )
    )
    return list(query)


def get_guild_player_profile(
    guild: Guild,
    normalized_username: str,
) -> GuildPlayerAggregate | None:
    return GuildPlayerAggregate.get_or_none(
        (GuildPlayerAggregate.guild == guild)
        & (
            GuildPlayerAggregate.normalized_username
            == normalize_username(normalized_username)
        )
    )


def player_state_label(aggregate: GuildPlayerAggregate) -> str:
    return "Linked" if aggregate.player_id else "Observed"
