from __future__ import annotations

from typing import Sequence

__all__ = ["main"]


def main(argv: Sequence[str] | None = None) -> int:
    from .guild_sites import main as guild_sites_main

    return guild_sites_main(argv)
