from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ...core.config import load_config
from ...core.openfront import OpenFrontClient
from ...services.historical_backfill import (
    create_backfill_run,
    discover_ffa_games,
    discover_team_games,
    hydrate_backfill_run,
    replay_backfill_run,
    track_backfill_run_rate_limits,
)
from ...services.openfront_ingestion import ingest_game_payload


@dataclass
class WorkerRuntime:
    name: str = "openfront-guild-stats-worker"
    client: OpenFrontClient = field(default_factory=OpenFrontClient)

    async def ingest_game_by_id(self, game_id: str) -> Any:
        payload = await self.client.fetch_game(game_id)
        return ingest_game_payload(payload)

    async def backfill(
        self,
        *,
        start: datetime,
        end: datetime,
        concurrency: int = 4,
        refresh_batch_size: int = 100,
        progress_every: int = 100,
    ) -> Any:
        run = create_backfill_run(start=start, end=end)
        with track_backfill_run_rate_limits(self.client, run.id):
            await asyncio.gather(
                discover_team_games(self.client, run.id),
                discover_ffa_games(self.client, run.id),
            )
            return await hydrate_backfill_run(
                self.client,
                run.id,
                concurrency=concurrency,
                refresh_batch_size=refresh_batch_size,
                progress_every=progress_every,
                track_rate_limits=False,
            )

    async def resume_backfill(
        self,
        run_id: int,
        *,
        concurrency: int = 4,
        refresh_batch_size: int = 100,
        progress_every: int = 100,
    ) -> Any:
        with track_backfill_run_rate_limits(self.client, run_id):
            await asyncio.gather(
                discover_team_games(self.client, run_id),
                discover_ffa_games(self.client, run_id),
            )
            return await hydrate_backfill_run(
                self.client,
                run_id,
                concurrency=concurrency,
                refresh_batch_size=refresh_batch_size,
                progress_every=progress_every,
                track_rate_limits=False,
            )

    async def replay_backfill(
        self,
        run_id: int,
        *,
        refresh_batch_size: int = 100,
    ) -> Any:
        return replay_backfill_run(
            run_id,
            refresh_batch_size=refresh_batch_size,
        )


def create_worker() -> WorkerRuntime:
    config = load_config()
    client = (
        OpenFrontClient(bypass_config=config.openfront)
        if config.openfront is not None
        else OpenFrontClient()
    )
    return WorkerRuntime(client=client)
