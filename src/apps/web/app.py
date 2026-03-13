from __future__ import annotations

from collections.abc import Mapping
from html import escape
from numbers import Real
import secrets
from typing import Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from ...core.config import BotConfig
from ...data.shared.models import PlayerLink
from ...services.discord_oauth import DiscordOAuthClient, build_discord_authorize_url
from ...services.guild_stats_api import (
    SUPPORTED_VIEWS,
    build_leaderboard_response,
    build_player_profile_response,
    build_scoring_response,
)
from ...services.guild_sites import list_guild_clan_tags, resolve_guild_site_for_host
from ...services.player_linking import link_site_user_to_player
from ...services.site_auth import get_site_user, upsert_site_user_from_discord


LeaderboardRow = Mapping[str, object]
LeaderboardColumn = tuple[str, Callable[[LeaderboardRow], str]]


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
            (
                "Troops Donated",
                lambda row: _format_table_value(row["donated_troops_total"]),
            ),
            ("Support Bonus", lambda row: _format_table_value(row["support_bonus"])),
            ("Role", lambda row: _format_table_value(row["role_label"])),
        )
    if view == "ffa":
        return (
            ("FFA Score", lambda row: _format_table_value(row["ffa_score"])),
            ("Wins", lambda row: _format_table_value(row["ffa_win_count"])),
            ("Win Rate", lambda row: _format_percent(row["ffa_win_rate"])),
            ("Games", lambda row: _format_table_value(row["ffa_game_count"])),
        )
    if view == "overall":
        return (
            ("Overall Score", lambda row: _format_table_value(row["overall_score"])),
            ("Team Score", lambda row: _format_table_value(row["team_score"])),
            ("FFA Score", lambda row: _format_table_value(row["ffa_score"])),
            ("Team Games", lambda row: _format_table_value(row["team_game_count"])),
            ("FFA Games", lambda row: _format_table_value(row["ffa_game_count"])),
        )
    if view == "support":
        return (
            (
                "Troops Donated",
                lambda row: _format_table_value(row["donated_troops_total"]),
            ),
            ("Gold Donated", lambda row: _format_table_value(row["donated_gold_total"])),
            (
                "Donation Actions",
                lambda row: _format_table_value(row["donation_action_count"]),
            ),
            ("Support Bonus", lambda row: _format_table_value(row["support_bonus"])),
            ("Team Games", lambda row: _format_table_value(row["team_game_count"])),
            ("Role", lambda row: _format_table_value(row["role_label"])),
        )
    raise ValueError(f"Unsupported leaderboard view: {view}")


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


def create_app(
    config: BotConfig | None = None,
    *,
    discord_oauth_client=None,
    openfront_client=None,
) -> FastAPI:
    app = FastAPI(title="openfront-guild-stats")
    app.name = "openfront-guild-stats"
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

    def resolve_request_guild(request: Request):
        guild = resolve_guild_site_for_host(request.headers.get("host"))
        if guild is None:
            raise HTTPException(status_code=404, detail="Guild site not found")
        return guild

    def current_site_user(request: Request):
        site_user_id = request.session.get("site_user_id")
        return get_site_user(site_user_id)

    def resolve_leaderboard_view(view: str):
        try:
            return str(view or "").strip().lower() or "team"
        except Exception as exc:  # pragma: no cover - defensive fallback
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/", response_class=HTMLResponse)
    async def guild_home(request: Request) -> HTMLResponse:
        guild = resolve_request_guild(request)
        clan_tags = list_guild_clan_tags(guild)
        leaderboard_links = "".join(
            (
                f'<a class="nav-link" href="/leaderboard?view={escape(view)}">'
                f'{escape(view.title())} Leaderboard</a>'
            )
            for view in SUPPORTED_VIEWS
        )
        tags_markup = "".join(
            f'<li class="tag">{escape(tag)}</li>' for tag in clan_tags
        ) or '<li class="tag">No clan tags configured</li>'
        body = f"""
        <header>
          <p>OpenFront Guild Site</p>
          <h1>{escape(guild.display_name)}</h1>
          <p>Tracked clan tags for this guild are listed below. Public stats on this site are scoped to this guild only.</p>
        </header>
        <nav>
          <a class="nav-link" href="/leaderboard">Leaderboard</a>
          <a class="nav-link" href="/players">Players</a>
        </nav>
        <section>
          <h2>Competitive Views</h2>
          <nav>{leaderboard_links}</nav>
        </section>
        <section>
          <h2>Tracked Clan Tags</h2>
          <ul class="tags">{tags_markup}</ul>
        </section>
        """
        return HTMLResponse(_render_guild_page(guild.display_name, body))

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
    async def guild_leaderboard_api(request: Request, view: str, sort: str | None = None):
        guild = resolve_request_guild(request)
        try:
            payload = build_leaderboard_response(guild, resolve_leaderboard_view(view), sort_by=sort)
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

    @app.get("/leaderboard", response_class=HTMLResponse)
    async def guild_leaderboard_placeholder(
        request: Request,
        view: str = "team",
        sort: str | None = None,
    ) -> HTMLResponse:
        guild = resolve_request_guild(request)
        resolved_view = resolve_leaderboard_view(view)
        leaderboard = build_leaderboard_response(guild, resolved_view, sort_by=sort)
        scoring = build_scoring_response(resolved_view)
        nav_links = "".join(
            f'<a class="nav-link" href="/leaderboard?view={escape(item)}">{escape(item.title())}</a>'
            for item in SUPPORTED_VIEWS
        )
        columns = _leaderboard_columns(resolved_view)
        header_labels = ("Player", *(label for label, _ in columns))
        header_cells = "".join(f"<th>{escape(label)}</th>" for label in header_labels)
        rows = "".join(
            "<tr>"
            f'<td><a href="/players/{escape(entry["normalized_username"])}">{escape(entry["display_username"])}</a> <strong>{escape(entry["state"])}</strong></td>'
            + "".join(f"<td>{render_value(entry)}</td>" for _, render_value in columns)
            + "</tr>"
            for entry in leaderboard["rows"]
        ) or (
            "<tr>"
            f'<td colspan="{len(columns) + 1}">No guild players have been aggregated yet.</td>'
            "</tr>"
        )
        body = f"""
        <header>
          <p>{escape(guild.display_name)}</p>
          <h1>Leaderboard</h1>
          <p>{escape(scoring["summary"])}</p>
        </header>
        <nav>
          <a class="nav-link" href="/">Back to guild home</a>
          <a class="nav-link" href="/players">Browse players</a>
          {nav_links}
        </nav>
        <section>
          <p><strong>How scoring works:</strong> {escape(scoring["overall_summary"])}</p>
        </section>
        <table>
          <thead>
            <tr>{header_cells}</tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        """
        return HTMLResponse(_render_guild_page(f"{guild.display_name} leaderboard", body))

    @app.get("/players", response_class=HTMLResponse)
    async def guild_players_placeholder(request: Request) -> HTMLResponse:
        guild = resolve_request_guild(request)
        leaderboard = build_leaderboard_response(guild, "team")
        player_links = "".join(
            f'<li><a class="nav-link" href="/players/{escape(entry["normalized_username"])}">{escape(entry["display_username"])}</a> <strong>{escape(entry["state"])}</strong></li>'
            for entry in leaderboard["rows"]
        ) or "<li>No public guild player profiles are available yet.</li>"
        body = f"""
        <header>
          <p>{escape(guild.display_name)}</p>
          <h1>Players</h1>
          <p>Public player profiles reflect stored guild-scoped aggregates.</p>
        </header>
        <nav>
          <a class="nav-link" href="/">Back to guild home</a>
          <a class="nav-link" href="/leaderboard">Leaderboard</a>
        </nav>
        <ul>{player_links}</ul>
        """
        return HTMLResponse(_render_guild_page(f"{guild.display_name} players", body))

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
        player = profile["player"]
        sections = profile["sections"]
        state_label = str(player["state"])
        descriptor = "Linked player" if state_label == "Linked" else "Observed player"
        linked_sections = ""
        linked_stats = profile.get("linked")
        if linked_stats is not None:
            linked_sections = f"""
            <section>
              <h2>Linked guild stats</h2>
              <p><strong>Linked guild wins:</strong> {linked_stats["guild_win_count"]}</p>
              <p><strong>Linked guild games:</strong> {linked_stats["guild_game_count"]}</p>
            </section>
            <section>
              <h2>Global OpenFront wins</h2>
              <p><strong>Global OpenFront wins:</strong> {linked_stats["global_public_wins"]}</p>
            </section>
            """
        body = f"""
        <header>
          <p>{escape(guild.display_name)}</p>
          <h1>{escape(player["display_username"])}</h1>
          <p>{descriptor} profile</p>
        </header>
        <nav>
          <a class="nav-link" href="/leaderboard">Leaderboard</a>
          <a class="nav-link" href="/players">All players</a>
        </nav>
        <section>
          <p><strong>State:</strong> {state_label}</p>
          <p><strong>Tracked alias key:</strong> {escape(player["normalized_username"])}</p>
        </section>
        <section>
          <h2>Team</h2>
          <p><strong>Score:</strong> {sections["team"]["score"]}</p>
          <p><strong>Wins:</strong> {sections["team"]["wins"]}</p>
          <p><strong>Games:</strong> {sections["team"]["games"]}</p>
          <p><strong>Win rate:</strong> {sections["team"]["win_rate"]}</p>
        </section>
        <section>
          <h2>FFA</h2>
          <p><strong>Score:</strong> {sections["ffa"]["score"]}</p>
          <p><strong>Wins:</strong> {sections["ffa"]["wins"]}</p>
          <p><strong>Games:</strong> {sections["ffa"]["games"]}</p>
          <p><strong>Win rate:</strong> {sections["ffa"]["win_rate"]}</p>
        </section>
        <section>
          <h2>Overall</h2>
          <p><strong>Score:</strong> {sections["overall"]["score"]}</p>
          <p><strong>Guild wins:</strong> {player["win_count"]}</p>
          <p><strong>Guild games:</strong> {player["game_count"]}</p>
        </section>
        <section>
          <h2>Support</h2>
          <p><strong>Troops donated:</strong> {sections["support"]["troops_donated"]}</p>
          <p><strong>Gold donated:</strong> {sections["support"]["gold_donated"]}</p>
          <p><strong>Donation actions:</strong> {sections["support"]["donation_actions"]}</p>
          <p><strong>Support bonus:</strong> {sections["support"]["support_bonus"]}</p>
          <p><strong>Role:</strong> {escape(sections["support"]["role_label"])}</p>
        </section>
        <section>
          <p><strong>Last observed clan tag:</strong> {escape(str(player["last_observed_clan_tag"] or "-"))}</p>
        </section>
        {linked_sections}
        """
        return HTMLResponse(
            _render_guild_page(
                f'{guild.display_name} player {player["display_username"]}',
                body,
            )
        )

    return app
