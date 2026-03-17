from __future__ import annotations

from pathlib import Path

OPENFRONT_ORIGIN = "https://openfront.io"
OPENFRONT_PROD_WORKERS = 20
OPENFRONT_REPO_DIR = Path(__file__).resolve().parents[2].parent / "OpenFrontIO"
OPENFRONT_MAPS_DIR = OPENFRONT_REPO_DIR / "map-generator" / "assets" / "maps"


def _simple_hash(value: str) -> int:
    hashed = 0
    for character in str(value):
        hashed = (hashed << 5) - hashed + ord(character)
        hashed &= 0xFFFFFFFF
    if hashed & 0x80000000:
        hashed = -((~hashed + 1) & 0xFFFFFFFF)
    return abs(hashed)


def build_openfront_replay_link(game_id: str) -> str:
    worker_index = _simple_hash(game_id) % OPENFRONT_PROD_WORKERS
    return f"{OPENFRONT_ORIGIN}/w{worker_index}/game/{game_id}"


def normalize_map_asset_name(map_name: str | None) -> str | None:
    raw_name = str(map_name or "").strip().lower()
    if not raw_name:
        return None
    normalized = "".join(character for character in raw_name if character not in " .()")
    return normalized or None


def build_map_thumbnail_url(map_name: str | None) -> str | None:
    normalized = normalize_map_asset_name(map_name)
    if not normalized:
        return None
    asset_dir = OPENFRONT_MAPS_DIR / normalized
    if not (asset_dir / "image.png").exists():
        return None
    return f"{OPENFRONT_ORIGIN}/maps/{normalized}/thumbnail.webp"
