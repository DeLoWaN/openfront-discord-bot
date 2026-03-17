from __future__ import annotations

from collections.abc import Mapping
from html import escape
import json
from numbers import Real
from pathlib import Path
import secrets
from typing import Any, Callable, cast

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from ...core.config import BotConfig
from ...data.shared.models import PlayerLink
from ...services.discord_oauth import DiscordOAuthClient, build_discord_authorize_url
from ...services.guild_engagement_api import (
    build_home_response,
    build_player_timeseries_response,
    build_recent_results_response,
)
from ...services.guild_stats_api import (
    SUPPORTED_VIEWS,
    build_leaderboard_response,
    build_player_profile_response,
    build_scoring_response,
)
from ...services.guild_combo_service import get_combo_detail, list_combo_rankings
from ...services.guild_sites import list_guild_clan_tags, resolve_guild_site_for_host
from ...services.player_linking import link_site_user_to_player
from ...services.site_auth import get_site_user, upsert_site_user_from_discord


LeaderboardRow = Mapping[str, object]
LeaderboardColumn = tuple[str, Callable[[LeaderboardRow], str]]
FRONTEND_DIST_DIR = Path(__file__).resolve().parent / "frontend_dist"
FAVICON_DATA_URI = (
    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
    "%3Crect width='64' height='64' rx='16' fill='%2318230f'/%3E"
    "%3Cpath d='M20 18h24v8H28v10h14v8H28v10h-8z' fill='%23f7f1e3'/%3E%3C/svg%3E"
)


def _format_table_value(value: object) -> str:
    if value is None:
        return "0"
    return escape(str(value))


def _format_percent(value: object) -> str:
    try:
        numeric_value = float(value) if isinstance(value, Real | str) else 0.0
        return escape(f"{numeric_value * 100:.1f}%")
    except (TypeError, ValueError):
        return "0.0%"


def _leaderboard_columns(view: str) -> tuple[LeaderboardColumn, ...]:
    if view == "team":
        return (
            ("Team Score", lambda row: _format_table_value(row["team_score"])),
            ("Wins", lambda row: _format_table_value(row["team_win_count"])),
            ("Win Rate", lambda row: _format_percent(row["team_win_rate"])),
            ("Games", lambda row: _format_table_value(row["team_game_count"])),
            ("Games 30d", lambda row: _format_table_value(row["team_recent_game_count_30d"])),
            ("Support Bonus", lambda row: _format_table_value(row["support_bonus"])),
            ("Role", lambda row: _format_table_value(row["role_label"])),
        )
    if view == "ffa":
        return (
            ("FFA Score", lambda row: _format_table_value(row["ffa_score"])),
            ("Wins", lambda row: _format_table_value(row["ffa_win_count"])),
            ("Win Rate", lambda row: _format_percent(row["ffa_win_rate"])),
            ("Games", lambda row: _format_table_value(row["ffa_game_count"])),
            ("Games 30d", lambda row: _format_table_value(row["ffa_recent_game_count_30d"])),
        )
    if view == "support":
        return (
            ("Support Bonus", lambda row: _format_table_value(row["support_bonus"])),
            (
                "Troops Donated",
                lambda row: _format_table_value(row["donated_troops_total"]),
            ),
            ("Gold Donated", lambda row: _format_table_value(row["donated_gold_total"])),
            (
                "Donation Actions",
                lambda row: _format_table_value(row["donation_action_count"]),
            ),
            (
                "Games 30d",
                lambda row: _format_table_value(row["support_recent_game_count_30d"]),
            ),
            ("Role", lambda row: _format_table_value(row["role_label"])),
        )
    raise ValueError(f"Unsupported leaderboard view: {view}")


def _render_scoring_details(scoring: Mapping[str, object]) -> str:
    details = scoring.get("details")
    if not isinstance(details, Mapping):
        return ""
    title = escape(str(details.get("title") or "Exact computation"))
    sections = details.get("sections")
    if not isinstance(sections, list):
        return f"<details><summary>{title}</summary></details>"

    section_markup = ""
    for section in sections:
        if not isinstance(section, Mapping):
            continue
        section_title = escape(str(section.get("title") or ""))
        lines = section.get("lines")
        if isinstance(lines, list):
            rendered_lines = "".join(
                f"<li>{escape(str(line))}</li>" for line in lines if str(line).strip()
            )
            lines_markup = f"<ul>{rendered_lines}</ul>" if rendered_lines else ""
        else:
            lines_markup = ""
        section_markup += f"<section><h3>{section_title}</h3>{lines_markup}</section>"
    return f"<details><summary>{title}</summary>{section_markup}</details>"


def _render_guild_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(title)}</title>
    <style>
      :root {{
        color-scheme: light;
        --paper: #f7f1e3;
        --ink: #18230f;
        --muted: #4f6f52;
        --accent: #6c584c;
        --accent-soft: #d9c5b2;
      }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background:
          radial-gradient(circle at top left, rgba(217, 197, 178, 0.85), transparent 38%),
          linear-gradient(180deg, #fffdf7, var(--paper));
        color: var(--ink);
      }}
      main {{
        max-width: 760px;
        margin: 0 auto;
        padding: 3rem 1.5rem 4rem;
      }}
      h1 {{
        margin-bottom: 0.5rem;
        font-size: clamp(2.4rem, 4vw, 4rem);
        letter-spacing: 0.02em;
      }}
      p {{
        color: var(--muted);
        line-height: 1.6;
      }}
      nav {{
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
        margin: 2rem 0;
      }}
      a {{
        color: var(--ink);
        text-decoration: none;
      }}
      .nav-link {{
        padding: 0.75rem 1rem;
        border: 1px solid rgba(24, 35, 15, 0.18);
        background: rgba(255, 255, 255, 0.7);
      }}
      .tags {{
        display: flex;
        gap: 0.75rem;
        flex-wrap: wrap;
        padding: 0;
        list-style: none;
      }}
      .tag {{
        padding: 0.45rem 0.8rem;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-weight: 700;
        letter-spacing: 0.08em;
      }}
    </style>
  </head>
  <body>
    <main>{body}</main>
  </body>
</html>"""


def _render_spa_shell(
    *,
    guild_display_name: str,
    clan_tags: list[str],
    current_path: str,
) -> str:
    assets_dir = FRONTEND_DIST_DIR / "assets"
    css_file = next(iter(sorted(assets_dir.glob("*.css"))), None) if assets_dir.exists() else None
    js_file = next(iter(sorted(assets_dir.glob("app*.js"))), None) if assets_dir.exists() else None
    css_href = f"/assets/{css_file.name}" if css_file else None
    js_href = f"/assets/{js_file.name}" if js_file else None
    context_json = json.dumps(
        {
            "displayName": guild_display_name,
            "clanTags": clan_tags,
            "currentPath": current_path,
        }
    )
    css_tag = f'<link rel="stylesheet" href="{css_href}" />' if css_href else ""
    js_tag = f'<script type="module" src="{js_href}"></script>' if js_href else ""
    tags_markup = "".join(f"<li>{escape(tag)}</li>" for tag in clan_tags)
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(guild_display_name)} Guild Stats</title>
    <link rel="icon" href="{FAVICON_DATA_URI}" />
    {css_tag}
  </head>
  <body>
    <div id="app-root">
      <main style="max-width: 980px; margin: 0 auto; padding: 2rem 1rem; font-family: Georgia, serif;">
        <p>OpenFront Guild Pulse</p>
        <h1>{escape(guild_display_name)}</h1>
        <nav style="display: flex; gap: 0.75rem; flex-wrap: wrap; margin: 1.5rem 0;">
          <a href="/">Home</a>
          <a href="/leaderboard">Leaderboard</a>
          <a href="/players">Players</a>
          <a href="/rosters">Rosters</a>
          <a href="/games">Recent games</a>
          <a href="/weekly">Weekly</a>
        </nav>
        <div style="display:none">
          <a href="/combos">Combos</a>
          <a href="/wins">Recent wins</a>
        </div>
        <p>Tracked clan tags</p>
        <ul>{tags_markup}</ul>
      </main>
    </div>
    <script>window.__GUILD_CONTEXT__ = {context_json};</script>
    {js_tag}
  </body>
</html>"""


def create_app(
    config: BotConfig | None = None,
    *,
    discord_oauth_client: DiscordOAuthClient | None = None,
    openfront_client: Any | None = None,
) -> FastAPI:
    app = FastAPI(title="openfront-guild-stats")
    cast(Any, app).name = "openfront-guild-stats"
    oauth_config = config.discord_oauth if config else None
    app.add_middleware(
        SessionMiddleware,
        secret_key=(oauth_config.session_secret if oauth_config else "dev-session-secret"),
    )
    app.state.config = config
    app.state.openfront_client = openfront_client
    app.state.discord_oauth_client = (
        discord_oauth_client
        or (DiscordOAuthClient(oauth_config) if oauth_config else None)
    )
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="spa-assets")

    def resolve_request_guild(request: Request) -> Any:
        guild = resolve_guild_site_for_host(request.headers.get("host"))
        if guild is None:
            raise HTTPException(status_code=404, detail="Guild site not found")
        return guild

    def current_site_user(request: Request):
        site_user_id = request.session.get("site_user_id")
        return get_site_user(site_user_id)

    def resolve_leaderboard_view(view: str):
        normalized = str(view or "").strip().lower() or "team"
        if normalized not in SUPPORTED_VIEWS:
            raise HTTPException(status_code=404, detail=f"Unsupported leaderboard view: {view}")
        return normalized

    def render_public_shell(request: Request, guild: Any) -> HTMLResponse:
        return HTMLResponse(
            _render_spa_shell(
                guild_display_name=guild.display_name,
                clan_tags=list_guild_clan_tags(guild),
                current_path=request.url.path,
            )
        )

    @app.get("/", response_class=HTMLResponse)
    async def guild_home(request: Request) -> HTMLResponse:
        guild = resolve_request_guild(request)
        return render_public_shell(request, guild)

    @app.get("/auth/discord/login")
    async def discord_login(request: Request):
        if not oauth_config:
            raise HTTPException(status_code=503, detail="Discord OAuth is not configured")
        state = secrets.token_urlsafe(16)
        request.session["discord_oauth_state"] = state
        return RedirectResponse(build_discord_authorize_url(oauth_config, state))

    @app.get("/auth/discord/callback")
    async def discord_callback(request: Request, code: str, state: str):
        if not oauth_config or app.state.discord_oauth_client is None:
            raise HTTPException(status_code=503, detail="Discord OAuth is not configured")
        if request.session.get("discord_oauth_state") != state:
            raise HTTPException(status_code=400, detail="Invalid OAuth state")
        token_payload = await app.state.discord_oauth_client.exchange_code(code)
        access_token = (
            token_payload.get("access_token")
            if isinstance(token_payload, dict)
            else None
        )
        if not access_token:
            raise HTTPException(status_code=502, detail="Discord OAuth token exchange failed")
        discord_user = await app.state.discord_oauth_client.fetch_user(access_token)
        site_user = upsert_site_user_from_discord(discord_user)
        request.session["site_user_id"] = site_user.id
        return RedirectResponse("/account", status_code=302)

    @app.get("/account", response_class=HTMLResponse)
    async def account_page(request: Request) -> HTMLResponse:
        guild = resolve_request_guild(request)
        site_user = current_site_user(request)
        if site_user is None:
            body = """
            <header>
              <h1>Account</h1>
              <p>Sign in with Discord to link an OpenFront player id.</p>
            </header>
            <nav><a class="nav-link" href="/auth/discord/login">Sign in with Discord</a></nav>
            """
            return HTMLResponse(_render_guild_page(f"{guild.display_name} account", body), status_code=401)
        current_link = PlayerLink.get_or_none(PlayerLink.site_user == site_user)
        linked_label = current_link.player.openfront_player_id if current_link else "Not linked yet"
        body = f"""
        <header>
          <p>{escape(guild.display_name)}</p>
          <h1>Account</h1>
          <p>Signed in as {escape(site_user.discord_username)}</p>
        </header>
        <nav>
          <a class="nav-link" href="/">Guild home</a>
          <a class="nav-link" href="/leaderboard">Leaderboard</a>
        </nav>
        <section>
          <p><strong>Linked OpenFront player:</strong> {escape(linked_label)}</p>
        </section>
        """
        return HTMLResponse(_render_guild_page(f"{guild.display_name} account", body))

    @app.post("/account/link")
    async def account_link(request: Request, player_id: str):
        site_user = current_site_user(request)
        if site_user is None:
            raise HTTPException(status_code=401, detail="Sign in required")
        if app.state.openfront_client is None:
            raise HTTPException(status_code=503, detail="OpenFront client unavailable")
        await link_site_user_to_player(site_user, player_id, app.state.openfront_client)
        return RedirectResponse("/account", status_code=303)

    @app.get("/api/leaderboards/{view}")
    async def guild_leaderboard_api(
        request: Request,
        view: str,
        sort: str | None = None,
        sort_by: str | None = None,
        order: str | None = None,
    ):
        guild = resolve_request_guild(request)
        try:
            payload = build_leaderboard_response(
                guild,
                resolve_leaderboard_view(view),
                sort_by=sort_by or sort,
                order=order,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JSONResponse(payload)

    @app.get("/api/scoring/{view}")
    async def guild_scoring_api(request: Request, view: str):
        _guild = resolve_request_guild(request)
        try:
            payload = build_scoring_response(resolve_leaderboard_view(view))
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JSONResponse(payload)

    @app.get("/api/players/{normalized_username}")
    async def guild_player_profile_api(request: Request, normalized_username: str):
        guild = resolve_request_guild(request)
        payload = await build_player_profile_response(
            guild,
            normalized_username,
            openfront_client=app.state.openfront_client,
        )
        if payload is None:
            raise HTTPException(status_code=404, detail="Guild player not found")
        return JSONResponse(payload)

    @app.get("/api/players/{normalized_username}/timeseries")
    async def guild_player_timeseries_api(request: Request, normalized_username: str):
        guild = resolve_request_guild(request)
        profile = await build_player_profile_response(
            guild,
            normalized_username,
            openfront_client=app.state.openfront_client,
        )
        if profile is None:
            raise HTTPException(status_code=404, detail="Guild player not found")
        return JSONResponse(build_player_timeseries_response(guild, normalized_username))

    @app.get("/api/home")
    async def guild_home_api(request: Request):
        guild = resolve_request_guild(request)
        return JSONResponse(build_home_response(guild))

    @app.get("/api/rosters/{format_slug}")
    @app.get("/api/combos/{format_slug}")
    async def guild_combo_rankings_api(request: Request, format_slug: str):
        guild = resolve_request_guild(request)
        try:
            payload = list_combo_rankings(guild, format_slug)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JSONResponse(payload)

    @app.get("/api/rosters/{format_slug}/{roster_key:path}")
    @app.get("/api/combos/{format_slug}/{roster_key:path}")
    async def guild_combo_detail_api(
        request: Request,
        format_slug: str,
        roster_key: str,
    ):
        guild = resolve_request_guild(request)
        payload = get_combo_detail(guild, format_slug, roster_key)
        if payload is None:
            raise HTTPException(status_code=404, detail="Guild combo not found")
        return JSONResponse(payload)

    @app.get("/api/results/recent")
    async def guild_recent_results_api(request: Request, limit: int = 20):
        guild = resolve_request_guild(request)
        return JSONResponse(build_recent_results_response(guild, limit=limit))

    @app.get("/api/weekly")
    async def guild_weekly_api(request: Request, scope: str = "team", weeks: int = 6):
        from ...services.guild_weekly_rankings import build_weekly_rankings_response

        guild = resolve_request_guild(request)
        try:
            payload = build_weekly_rankings_response(guild, scope=scope, weeks=weeks)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return JSONResponse(payload)

    @app.get("/leaderboard", response_class=HTMLResponse)
    async def guild_leaderboard_placeholder(
        request: Request,
        view: str = "team",
        sort: str | None = None,
    ) -> HTMLResponse:
        guild = resolve_request_guild(request)
        _ = resolve_leaderboard_view(view)
        _ = sort
        return render_public_shell(request, guild)

    @app.get("/players", response_class=HTMLResponse)
    async def guild_players_placeholder(request: Request) -> HTMLResponse:
        guild = resolve_request_guild(request)
        return render_public_shell(request, guild)

    @app.get("/rosters", response_class=HTMLResponse)
    async def guild_rosters_page(request: Request) -> HTMLResponse:
        guild = resolve_request_guild(request)
        return render_public_shell(request, guild)

    @app.get("/rosters/{format_slug}", response_class=HTMLResponse)
    @app.get("/rosters/{format_slug}/{roster_key:path}", response_class=HTMLResponse)
    async def guild_combo_detail_page(
        request: Request,
        format_slug: str | None = None,
        roster_key: str | None = None,
    ) -> HTMLResponse:
        guild = resolve_request_guild(request)
        _ = format_slug
        _ = roster_key
        return render_public_shell(request, guild)

    @app.get("/games", response_class=HTMLResponse)
    async def guild_games_page(request: Request) -> HTMLResponse:
        guild = resolve_request_guild(request)
        return render_public_shell(request, guild)

    @app.get("/weekly", response_class=HTMLResponse)
    async def guild_weekly_page(request: Request) -> HTMLResponse:
        guild = resolve_request_guild(request)
        return render_public_shell(request, guild)

    @app.get("/combos", response_class=HTMLResponse)
    @app.get("/combos/{path:path}", response_class=HTMLResponse)
    async def guild_combos_alias(request: Request, path: str | None = None):
        guild = resolve_request_guild(request)
        _ = path
        return render_public_shell(request, guild)

    @app.get("/wins", response_class=HTMLResponse)
    async def guild_wins_alias(request: Request):
        guild = resolve_request_guild(request)
        return render_public_shell(request, guild)

    @app.get("/players/{normalized_username}", response_class=HTMLResponse)
    async def guild_player_profile(
        request: Request,
        normalized_username: str,
    ) -> HTMLResponse:
        guild = resolve_request_guild(request)
        profile = await build_player_profile_response(
            guild,
            normalized_username,
            openfront_client=app.state.openfront_client,
        )
        if profile is None:
            raise HTTPException(status_code=404, detail="Guild player not found")
        return render_public_shell(request, guild)

    return app
