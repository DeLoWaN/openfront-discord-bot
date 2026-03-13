from __future__ import annotations

import httpx

from ..core.config import DiscordOAuthConfig

DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_ME_URL = "https://discord.com/api/users/@me"


def build_discord_authorize_url(config: DiscordOAuthConfig, state: str) -> str:
    params = httpx.QueryParams(
        {
            "client_id": config.client_id,
            "response_type": "code",
            "redirect_uri": config.redirect_uri,
            "scope": config.scope,
            "state": state,
            "prompt": "consent",
        }
    )
    return f"{DISCORD_AUTHORIZE_URL}?{params}"


class DiscordOAuthClient:
    def __init__(self, config: DiscordOAuthConfig):
        self.config = config

    async def exchange_code(self, code: str) -> dict[str, str]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DISCORD_TOKEN_URL,
                data={
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.config.redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return dict(response.json())

    async def fetch_user(self, access_token: str) -> dict[str, str]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                DISCORD_ME_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            return dict(response.json())
