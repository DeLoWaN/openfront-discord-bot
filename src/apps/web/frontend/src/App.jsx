import { keepPreviousData, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  Link,
  NavLink,
  Navigate,
  Route,
  Routes,
  useParams,
  useSearchParams
} from "react-router-dom";
import { useEffect } from "react";

const guildContext = globalThis.window?.__GUILD_CONTEXT__ ?? {
  displayName: "Guild",
  clanTags: [],
  currentPath: "/"
};

const PRIMARY_PREFETCHES = [
  { key: ["home"], url: "/api/home" },
  { key: ["leaderboard", "team", "team_score", "desc"], url: "/api/leaderboards/team" },
  { key: ["recent-games", "all"], url: "/api/results/recent" },
  { key: ["weekly", "team"], url: "/api/weekly?scope=team&weeks=6" }
];

function fetchJson(url) {
  return fetch(url).then(async (response) => {
    if (!response.ok) {
      const payload = await response.text();
      throw new Error(payload || `Request failed: ${response.status}`);
    }
    return response.json();
  });
}

function useApiQuery(queryKey, url, options = {}) {
  return useQuery({
    queryKey,
    queryFn: () => fetchJson(url),
    placeholderData: keepPreviousData,
    staleTime: options.staleTime ?? 60_000,
    ...options
  });
}

function formatPercent(value) {
  return `${((Number(value) || 0) * 100).toFixed(1)}%`;
}

function formatDate(value) {
  if (!value) {
    return "Unknown";
  }
  return new Date(value).toLocaleString();
}

function shortDate(value) {
  if (!value) {
    return "?";
  }
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric"
  });
}

function movementLabel(movement) {
  if (!movement) {
    return "steady";
  }
  if (movement.kind === "new") {
    return "new";
  }
  if (movement.kind === "up") {
    return `+${movement.delta}`;
  }
  if (movement.kind === "down") {
    return `-${movement.delta}`;
  }
  return "=";
}

function NavPill({ to, children }) {
  return (
    <NavLink
      className={({ isActive }) => `nav-pill${isActive ? " is-active" : ""}`}
      to={to}
    >
      {children}
    </NavLink>
  );
}

function MetricGrid({ items }) {
  return (
    <div className="metric-grid">
      {items.map((item) => (
        <article className="metric-card" key={item.label}>
          <p className="eyebrow">{item.label}</p>
          <strong>{item.value}</strong>
          {item.note ? <span>{item.note}</span> : null}
        </article>
      ))}
    </div>
  );
}

function LoadingBlock({ label }) {
  return <div className="panel loading-panel">{label}</div>;
}

function EmptyState({ title, body }) {
  return (
    <div className="panel empty-panel">
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}

function usePrimaryPrefetch() {
  const queryClient = useQueryClient();

  useEffect(() => {
    PRIMARY_PREFETCHES.forEach((item) => {
      queryClient.prefetchQuery({
        queryKey: item.key,
        queryFn: () => fetchJson(item.url),
        staleTime: 60_000
      });
    });
  }, [queryClient]);
}

function Layout({ title, subtitle, children }) {
  usePrimaryPrefetch();

  return (
    <div className="shell">
      <div className="backdrop" />
      <header className="hero">
        <div>
          <p className="hero-kicker">OpenFront Guild Pulse</p>
          <h1>{title}</h1>
          <p className="hero-copy">{subtitle}</p>
          <div className="tag-row">
            {(guildContext.clanTags || []).map((tag) => (
              <span className="tag-chip" key={tag}>
                {tag}
              </span>
            ))}
          </div>
        </div>
        <nav className="main-nav" aria-label="Primary">
          <NavPill to="/">Home</NavPill>
          <NavPill to="/leaderboard">Leaderboard</NavPill>
          <NavPill to="/players">Players</NavPill>
          <NavPill to="/rosters">Rosters</NavPill>
          <NavPill to="/games">Recent Games</NavPill>
          <NavPill to="/weekly">Weekly</NavPill>
        </nav>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}

function PlayerProfileLink({ player }) {
  return <Link to={`/players/${player.normalized_username}`}>{player.display_username}</Link>;
}

function rosterLabel(roster) {
  return roster.members.map((member) => member.display_username).join(" / ");
}

function HomePage() {
  const homeQuery = useApiQuery(["home"], "/api/home");

  if (homeQuery.isLoading) {
    return <LoadingBlock label="Loading guild dashboard..." />;
  }
  if (homeQuery.isError) {
    return <EmptyState title="Dashboard unavailable" body={homeQuery.error.message} />;
  }

  const data = homeQuery.data;
  const podiums = data.roster_podiums || data.combo_podiums;
  const weeklyPulse = data.weekly_pulse || { rows: [], movers: [], scope: "team" };
  const latestGames = data.latest_games_preview || data.recent_wins_preview || [];
  const pendingTeaser = data.pending_roster_teaser || data.pending_combo_teaser || { counts: {} };

  return (
    <Layout
      title={data.guild.display_name}
      subtitle="Track guild momentum, compare rosters, and keep weekly competition visible."
    >
      <section className="panel">
        <div className="section-heading">
          <h2>Competitive Pulse</h2>
          <p>Ranks stay visible so the hierarchy reads instantly.</p>
        </div>
        <div className="pulse-grid">
          <div>
            <h3>Leaders</h3>
            <ul className="list-card">
              {data.competitive_pulse.leaders.map((row) => (
                <li key={row.normalized_username}>
                  <span className="rank-pill">#{row.rank}</span>
                  <PlayerProfileLink player={row} />
                  <span>{row.team_score}</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Most Active</h3>
            <ul className="list-card">
              {data.competitive_pulse.most_active.map((row) => (
                <li key={row.normalized_username}>
                  <span className="rank-pill">#{row.rank}</span>
                  <PlayerProfileLink player={row} />
                  <span>{row.team_recent_game_count_30d} games</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Support Spotlight</h3>
            <ul className="list-card">
              {data.competitive_pulse.support_spotlight.map((row) => (
                <li key={row.normalized_username}>
                  <span className="rank-pill">#{row.rank}</span>
                  <PlayerProfileLink player={row} />
                  <span>{row.support_bonus}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Roster Podiums</h2>
          <p>Confirmed duos, trios, and quads stay ranked on raw win rate.</p>
        </div>
        <div className="combo-grid">
          {["duo", "trio", "quad"].map((formatSlug) => {
            const rows = podiums[formatSlug] || [];
            return (
              <article className="combo-card" key={formatSlug}>
                <div className="card-header">
                  <h3>{formatSlug === "duo" ? "Duos" : formatSlug === "trio" ? "Trios" : "Quads"}</h3>
                  <Link to={`/rosters/${formatSlug}`}>Open</Link>
                </div>
                {rows.length ? (
                  <ul className="combo-list">
                    {rows.map((row) => (
                      <li key={row.roster_key}>
                        <Link to={`/rosters/${formatSlug}/${encodeURIComponent(row.roster_key)}`}>
                          {rosterLabel(row)}
                        </Link>
                        <span>{formatPercent(row.win_rate)} • {row.games_together} games</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="quiet-copy">No confirmed roster yet.</p>
                )}
              </article>
            );
          })}
        </div>
      </section>

      <section className="panel split-panel">
        <div>
          <div className="section-heading">
            <h2>Weekly Pulse</h2>
            <p>Current week leaders and movers. Full breakdown lives on the Weekly page.</p>
          </div>
          {weeklyPulse.rows.length ? (
            <ul className="list-card">
              {weeklyPulse.rows.map((row) => (
                <li key={row.normalized_username}>
                  <span className="rank-pill">#{row.rank}</span>
                  <PlayerProfileLink player={row} />
                  <span>{row.score} ({movementLabel(row.movement)})</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="quiet-copy">No weekly activity yet.</p>
          )}
        </div>
        <div>
          <div className="section-heading">
            <h2>Latest Guild Games</h2>
            <p>Result, date, map, and team distribution stay visible at a glance.</p>
          </div>
          {latestGames.length ? (
            <ul className="list-card">
              {latestGames.map((item) => (
                <li key={item.openfront_game_id}>
                  <div>
                    <strong>{item.map_name || "Unknown map"}</strong>
                    <div className="quiet-copy">{item.team_distribution} • {shortDate(item.ended_at)}</div>
                  </div>
                  <span className={`result-pill result-pill-${item.result}`}>{item.result}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="quiet-copy">No recent games yet.</p>
          )}
        </div>
      </section>

      <section className="panel split-panel">
        <div>
          <div className="section-heading">
            <h2>Pending Rosters</h2>
            <p>Raw counts by format while waiting for the five-game threshold.</p>
          </div>
          <MetricGrid
            items={Object.entries(pendingTeaser.counts).map(([label, value]) => ({
              label,
              value
            }))}
          />
        </div>
        <div>
          <div className="section-heading">
            <h2>Recent Badges</h2>
            <p>Latest unlocks across the guild.</p>
          </div>
          {data.recent_badges.length ? (
            <div className="badge-grid">
              {data.recent_badges.map((badge) => (
                <article className="badge-card" key={`${badge.normalized_username}-${badge.badge_code}-${badge.badge_level || "base"}`}>
                  <p className="eyebrow">{badge.display_username || badge.normalized_username}</p>
                  <strong>{badge.label}</strong>
                  <span>{badge.badge_level || "Unlocked"}</span>
                </article>
              ))}
            </div>
          ) : (
            <p className="quiet-copy">Badge activity will appear here after the next unlock.</p>
          )}
        </div>
      </section>
    </Layout>
  );
}

function SortableHeader({ column, currentSort, onSort }) {
  const sortKey = column.sort_key || column.key;
  const isActive = currentSort.sortBy === sortKey;
  const direction = isActive ? currentSort.order : null;
  return (
    <button
      className={`sort-button${isActive ? " is-active" : ""}`}
      disabled={column.sortable === false}
      onClick={() => onSort(column)}
      type="button"
    >
      {column.label}
      {direction === "asc" ? " +" : direction === "desc" ? " -" : ""}
    </button>
  );
}

function scoringBullets(view) {
  if (view === "team") {
    return [
      "+ more teams -> more difficulty",
      "+ fewer players per team -> more difficulty",
      "+ fewer tracked guild teammates -> more difficulty",
      "+ wins add on top of participation",
      "+ support stays additive",
      "- recent activity does not decay score"
    ];
  }
  if (view === "ffa") {
    return [
      "+ larger lobbies -> more difficulty",
      "+ wins add on top of participation",
      "- recent activity does not decay score"
    ];
  }
  return [
    "+ support sorts by bonus first",
    "+ donation totals stay visible",
    "- support never subtracts from frontliners"
  ];
}

function LeaderboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const view = searchParams.get("view") || "team";
  const sortBy = searchParams.get("sort_by") || (view === "team" ? "team_score" : view === "ffa" ? "ffa_score" : "support_bonus");
  const order = searchParams.get("order") || "desc";
  const leaderboardQuery = useApiQuery(
    ["leaderboard", view, sortBy, order],
    `/api/leaderboards/${view}?sort_by=${encodeURIComponent(sortBy)}&order=${encodeURIComponent(order)}`
  );
  const scoringQuery = useApiQuery(["scoring", view], `/api/scoring/${view}`);

  if (leaderboardQuery.isLoading || scoringQuery.isLoading) {
    return <LoadingBlock label="Loading leaderboard..." />;
  }
  if (leaderboardQuery.isError || scoringQuery.isError) {
    return <EmptyState title="Leaderboard unavailable" body="The leaderboard could not be loaded." />;
  }

  const { rows, columns } = leaderboardQuery.data;

  function updateView(nextView) {
    setSearchParams({ view: nextView });
  }

  function updateSort(column) {
    if (column.sortable === false) {
      return;
    }
    const backendSortKey = column.sort_key || column.key;
    const nextOrder = sortBy === backendSortKey && order === "desc" ? "asc" : "desc";
    setSearchParams({ view, sort_by: backendSortKey, order: nextOrder });
  }

  return (
    <Layout
      title="Leaderboard"
      subtitle="Sortable Team, FFA, and Support views with explicit score semantics."
    >
      <section className="panel">
        <div className="tab-row">
          {["team", "ffa", "support"].map((item) => (
            <button
              className={`tab-button${item === view ? " is-active" : ""}`}
              key={item}
              onClick={() => updateView(item)}
              type="button"
            >
              {item.toUpperCase()}
            </button>
          ))}
        </div>
        <details className="scoring-details">
          <summary>Score explainer</summary>
          <p className="quiet-copy">{scoringQuery.data.summary}</p>
          <ul className="scoring-list">
            {scoringBullets(view).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </details>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.key}>
                    <SortableHeader
                      column={column}
                      currentSort={{ sortBy, order }}
                      onSort={updateSort}
                    />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.normalized_username}>
                  {columns.map((column) => {
                    if (column.key === "display_username") {
                      return (
                        <td key={`${row.normalized_username}-${column.key}`}>
                          <div className="table-player">
                            <PlayerProfileLink player={row} />
                            <span className="quiet-copy">{row.state}</span>
                          </div>
                        </td>
                      );
                    }
                    if (column.key === "ratio") {
                      return <td key={`${row.normalized_username}-${column.key}`}>{row.ratio}</td>;
                    }
                    if (column.key === "win_rate") {
                      return <td key={`${row.normalized_username}-${column.key}`}>{formatPercent(row.win_rate)}</td>;
                    }
                    return <td key={`${row.normalized_username}-${column.key}`}>{row[column.key]}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="quiet-copy">Weekly movers now live on the dedicated Weekly page.</p>
      </section>
    </Layout>
  );
}

function PlayersPage() {
  const playersQuery = useApiQuery(["players-index"], "/api/leaderboards/team");

  if (playersQuery.isLoading) {
    return <LoadingBlock label="Loading players..." />;
  }
  if (playersQuery.isError) {
    return <EmptyState title="Players unavailable" body={playersQuery.error.message} />;
  }

  return (
    <Layout
      title="Players"
      subtitle="Guild profiles with score, badges, partners, and weekly contribution."
    >
      <section className="panel">
        <div className="player-grid">
          {playersQuery.data.rows.map((player) => (
            <article className="player-card" key={player.normalized_username}>
              <p className="eyebrow">{player.state}</p>
              <h2>{player.display_username}</h2>
              <MetricGrid
                items={[
                  { label: "Team Score", value: player.team_score, note: `${player.ratio} • ${formatPercent(player.team_win_rate)}` },
                  { label: "FFA Score", value: player.ffa_score, note: `${player.ffa_ratio} • ${formatPercent(player.ffa_win_rate)}` },
                  { label: "Support", value: player.support_bonus, note: `${player.team_recent_game_count_30d} games 30d` }
                ]}
              />
              <Link to={`/players/${player.normalized_username}`}>Open profile</Link>
            </article>
          ))}
        </div>
      </section>
    </Layout>
  );
}

function RostersPage() {
  const { formatSlug = "duo", rosterKey } = useParams();
  const normalizedFormat = formatSlug || "duo";
  const rankingsQuery = useApiQuery(["rosters", normalizedFormat], `/api/rosters/${normalizedFormat}`);
  const detailQuery = useApiQuery(
    ["roster-detail", normalizedFormat, rosterKey],
    rosterKey ? `/api/rosters/${normalizedFormat}/${encodeURIComponent(rosterKey)}` : `/api/rosters/${normalizedFormat}`,
    { enabled: Boolean(rosterKey) }
  );

  if (rankingsQuery.isLoading) {
    return <LoadingBlock label="Loading rosters..." />;
  }
  if (rankingsQuery.isError) {
    return <EmptyState title="Rosters unavailable" body={rankingsQuery.error.message} />;
  }

  const data = rankingsQuery.data;
  const detail = detailQuery.data?.combo ? detailQuery.data : null;
  const confirmed = data.confirmed || [];
  const pending = data.pending || [];

  return (
    <Layout
      title="Rosters"
      subtitle="Confirmed and pending guild duos, trios, and quads with strict confidence rules."
    >
      <section className="panel">
        <div className="tab-row">
          {["duo", "trio", "quad"].map((item) => (
            <NavLink className={`tab-button${item === normalizedFormat ? " is-active" : ""}`} key={item} to={`/rosters/${item}`}>
              {item === "duo" ? "Duos" : item === "trio" ? "Trios" : "Quads"}
            </NavLink>
          ))}
        </div>
        <div className="split-panel">
          <div>
            <h2>Confirmed</h2>
            {confirmed.length ? (
              <ul className="combo-list">
                {confirmed.map((combo) => (
                  <li key={combo.roster_key}>
                    <Link to={`/rosters/${normalizedFormat}/${encodeURIComponent(combo.roster_key)}`}>
                      {rosterLabel(combo)}
                    </Link>
                    <span>{formatPercent(combo.win_rate)} • {combo.games_together} games</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="quiet-copy">No confirmed roster in this format yet.</p>
            )}
          </div>
          <div>
            <h2>Pending</h2>
            {pending.length ? (
              <ul className="combo-list">
                {pending.map((combo) => (
                  <li key={combo.roster_key}>
                    <Link to={`/rosters/${normalizedFormat}/${encodeURIComponent(combo.roster_key)}`}>
                      {rosterLabel(combo)}
                    </Link>
                    <span>{combo.games_together} / 5 games</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="quiet-copy">No pending roster in this format.</p>
            )}
          </div>
        </div>
      </section>
      {detail ? (
        <section className="panel">
          <div className="section-heading">
            <h2>{rosterLabel(detail.combo)}</h2>
            <p>{detail.combo.status} • {detail.combo.title}</p>
          </div>
          <MetricGrid
            items={[
              { label: "Win Rate", value: formatPercent(detail.combo.win_rate) },
              { label: "Games", value: detail.combo.games_together },
              { label: "Wins", value: detail.combo.wins_together }
            ]}
          />
          <div className="timeline">
            {detail.history.map((entry) => (
              <article className={`timeline-item${entry.did_win ? " is-win" : " is-loss"}`} key={entry.openfront_game_id}>
                <div>
                  <strong>{entry.map_name || "Unknown map"}</strong>
                  <div className="quiet-copy">{entry.mode_name}</div>
                </div>
                <span className={`result-pill result-pill-${entry.did_win ? "win" : "loss"}`}>
                  {entry.did_win ? "win" : "loss"}
                </span>
                <a href={entry.replay_link} rel="noreferrer" target="_blank">
                  Replay
                </a>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </Layout>
  );
}

function WinnerGroups({ winnerPlayers }) {
  const guildWinners = winnerPlayers?.guild || [];
  const otherWinners = winnerPlayers?.other || [];
  return (
    <div className="winner-groups">
      <div>
        <p className="eyebrow">Guild winners</p>
        <div className="player-chip-row">
          {guildWinners.length ? guildWinners.map((player) => (
            <span className="tag-chip" key={`guild-${player.client_id}`}>{player.display_username}</span>
          )) : <span className="quiet-copy">None</span>}
        </div>
      </div>
      <div>
        <p className="eyebrow">Other winners</p>
        <div className="player-chip-row">
          {otherWinners.length ? otherWinners.map((player) => (
            <span className="tag-chip" key={`other-${player.client_id}`}>{player.display_username}</span>
          )) : <span className="quiet-copy">None</span>}
        </div>
      </div>
    </div>
  );
}

function GamesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const layout = searchParams.get("layout") || "card";
  const resultFilter = searchParams.get("result") || "all";
  const gamesQuery = useApiQuery(
    ["recent-games", resultFilter],
    resultFilter === "all" ? "/api/results/recent" : `/api/results/recent?result=${resultFilter}`
  );

  if (gamesQuery.isLoading) {
    return <LoadingBlock label="Loading recent games..." />;
  }
  if (gamesQuery.isError) {
    return <EmptyState title="Recent games unavailable" body={gamesQuery.error.message} />;
  }

  const items = gamesQuery.data.items;

  return (
    <Layout
      title="Recent Games"
      subtitle="Latest guild games with result, roster context, winners, and replay access."
    >
      <section className="panel">
        <div className="toolbar-row">
          <div className="tab-row">
            {["card", "list"].map((item) => (
              <button
                className={`tab-button${item === layout ? " is-active" : ""}`}
                key={item}
                onClick={() => setSearchParams({ layout: item, result: resultFilter })}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
          <div className="tab-row">
            {["all", "win", "loss"].map((item) => (
              <button
                className={`tab-button${item === resultFilter ? " is-active" : ""}`}
                key={item}
                onClick={() => setSearchParams({ layout, result: item })}
                type="button"
              >
                {item}
              </button>
            ))}
          </div>
        </div>
        {layout === "list" ? (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Map</th>
                  <th>Date</th>
                  <th>Result</th>
                  <th>Mode</th>
                  <th>Teams</th>
                  <th>Replay</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.openfront_game_id}>
                    <td>{item.map_name || "Unknown map"}</td>
                    <td>{formatDate(item.ended_at)}</td>
                    <td>{item.result}</td>
                    <td>{item.mode}</td>
                    <td>{item.team_distribution}</td>
                    <td><a href={item.replay_link} rel="noreferrer" target="_blank">Replay</a></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="win-feed">
            {items.map((item) => (
              <article className="win-card" key={item.openfront_game_id}>
                {item.map_thumbnail_url ? (
                  <img alt={item.map_name || "Map"} className="map-thumb" src={item.map_thumbnail_url} />
                ) : null}
                <p className="eyebrow">{item.mode}</p>
                <h2>{item.map_name || "Unknown map"}</h2>
                <p>{item.team_distribution || item.format_label || ""}</p>
                <span>{formatDate(item.ended_at)}</span>
                <span className={`result-pill result-pill-${item.result || "win"}`}>{item.result || "win"}</span>
                <div>
                  <p className="eyebrow">Guild side</p>
                  <div className="player-chip-row">
                    {(item.guild_team_players || []).map((player) => (
                      <Link className="tag-chip" key={`${item.openfront_game_id}-${player.normalized_username}`} to={`/players/${player.normalized_username}`}>
                        {player.display_username}
                      </Link>
                    ))}
                  </div>
                </div>
                <WinnerGroups winnerPlayers={item.winner_players} />
                <a href={item.replay_link} rel="noreferrer" target="_blank">
                  Watch replay
                </a>
              </article>
            ))}
          </div>
        )}
      </section>
    </Layout>
  );
}

function WeeklyPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const scope = searchParams.get("scope") || "team";
  const weeklyQuery = useApiQuery(
    ["weekly", scope],
    `/api/weekly?scope=${scope}&weeks=6`
  );

  if (weeklyQuery.isLoading) {
    return <LoadingBlock label="Loading weekly competition..." />;
  }
  if (weeklyQuery.isError) {
    return <EmptyState title="Weekly view unavailable" body={weeklyQuery.error.message} />;
  }

  const data = weeklyQuery.data;

  return (
    <Layout
      title="Weekly"
      subtitle="Current-week leaders, movers versus last week, and six-week trends."
    >
      <section className="panel">
        <div className="tab-row">
          {["team", "ffa", "support"].map((item) => (
            <button
              className={`tab-button${item === scope ? " is-active" : ""}`}
              key={item}
              onClick={() => setSearchParams({ scope: item })}
              type="button"
            >
              {item.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="split-panel">
          <div>
            <h2>Top 10</h2>
            <ul className="list-card">
              {data.rows.map((row) => (
                <li key={row.normalized_username}>
                  <span className="rank-pill">#{row.rank}</span>
                  <PlayerProfileLink player={row} />
                  <span>{row.score} ({movementLabel(row.movement)})</span>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2>Movers</h2>
            {data.movers.length ? (
              <ul className="list-card">
                {data.movers.map((row) => (
                  <li key={`mover-${row.normalized_username}`}>
                    <PlayerProfileLink player={row} />
                    <span>{movementLabel(row.movement)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="quiet-copy">No movers yet this week.</p>
            )}
          </div>
        </div>
      </section>
      <section className="panel">
        <div className="section-heading">
          <h2>Six-Week Trend</h2>
          <p>Current top 10 across the last six UTC weeks.</p>
        </div>
        <div className="history-matrix">
          {data.rows.map((row) => (
            <article className="history-row" key={`history-${row.normalized_username}`}>
              <strong>{row.display_username}</strong>
              <div className="history-chips">
                {row.history.map((value, index) => (
                  <span className="history-chip" key={`${row.normalized_username}-${index}`}>
                    {value}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </Layout>
  );
}

function BadgeCard({ badge }) {
  const classes = `badge-card${badge.is_locked ? " is-locked" : ""}`;
  return (
    <article className={classes} title={badge.description || ""}>
      <strong>{badge.label}</strong>
      {badge.levels ? (
        <div className="level-row">
          {badge.levels.map((level) => (
            <span className={`level-pill${level.earned ? " is-earned" : ""}`} key={level.name}>
              {level.name}
            </span>
          ))}
        </div>
      ) : (
        <span>{badge.is_locked ? "Locked" : "Unlocked"}</span>
      )}
    </article>
  );
}

function PlayerProfilePage() {
  const { normalizedUsername } = useParams();
  const profileQuery = useApiQuery(["player", normalizedUsername], `/api/players/${normalizedUsername}`);
  const timeseriesQuery = useApiQuery(["timeseries", normalizedUsername], `/api/players/${normalizedUsername}/timeseries`);

  if (profileQuery.isLoading || timeseriesQuery.isLoading) {
    return <LoadingBlock label="Loading player profile..." />;
  }
  if (profileQuery.isError || timeseriesQuery.isError) {
    return <EmptyState title="Player unavailable" body="The player profile could not be loaded." />;
  }

  const profile = profileQuery.data;
  const timeseries = timeseriesQuery.data;
  const badgeCatalog = profile.badge_catalog || (profile.badges || []).map((badge) => ({
    ...badge,
    is_locked: false
  }));
  const dailyBenchmarks = timeseries.daily_benchmarks || [];
  const dailyProgression = timeseries.daily_progression || timeseries.progression || [];
  const recentPerformanceRows = timeseries.recent_performance || timeseries.recent_form || [];
  const weeklyScoreRows = timeseries.weekly_scores || [];
  const benchmarksByDate = Object.fromEntries(
    dailyBenchmarks.map((item) => [item.date, item])
  );
  const progressionData = dailyProgression.map((item, index) => ({
    date: item.date || item.ended_at || String(index + 1),
    playerScore: item.score ?? item.team_score ?? index + 1,
    guildMedian: benchmarksByDate[item.date || item.ended_at]?.median_score ?? 0,
    guildLeader: benchmarksByDate[item.date || item.ended_at]?.leader_score ?? 0
  }));
  const recentPerformance = recentPerformanceRows.map((item, index) => ({
    date: item.date || item.ended_at || String(index + 1),
    scoreDelta: item.score_delta ?? item.outcome ?? 0,
    rollingWinRate: Number((((item.rolling_win_rate ?? item.outcome) || 0) * 100).toFixed(1))
  }));
  const weeklyScores = weeklyScoreRows.map((item) => ({
    week: item.week_start,
    team: item.team,
    ffa: item.ffa,
    support: item.support
  }));

  return (
    <Layout
      title={profile.player.display_username}
      subtitle="Score progression, complete badge catalog, partners, and weekly contribution."
    >
      <section className="panel">
        <MetricGrid
          items={[
            {
              label: "Team Score",
              value: profile.sections.team.score,
              note: `${profile.sections.team.score_note_label}: ${profile.sections.team.wins}/${profile.sections.team.games}`
            },
            {
              label: "FFA Score",
              value: profile.sections.ffa.score,
              note: `${profile.sections.ffa.score_note_label}: ${profile.sections.ffa.wins}/${profile.sections.ffa.games}`
            },
            {
              label: "Weekly Team",
              value: profile.weekly_summary?.score || 0,
              note: `rank ${profile.weekly_summary?.rank || "-"} • ${movementLabel(profile.weekly_summary?.movement)}`
            }
          ]}
        />
      </section>

      <section className="panel split-panel">
        <div>
          <div className="section-heading">
            <h2>Badge Catalog</h2>
            <p>Unlocked and locked badges, with descriptions on hover.</p>
          </div>
          <div className="badge-grid">
            {badgeCatalog.map((badge) => (
              <BadgeCard badge={badge} key={badge.badge_code} />
            ))}
          </div>
        </div>
        <div>
          <div className="section-heading">
            <h2>Best Partners</h2>
            <p>Most effective guild teammates by shared results.</p>
          </div>
          {profile.best_partners.length ? (
            <ul className="list-card">
              {profile.best_partners.map((partner) => (
                <li key={partner.normalized_username}>
                  <Link to={`/players/${partner.normalized_username}`}>{partner.display_username}</Link>
                  <span>{formatPercent(partner.win_rate)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="quiet-copy">Partner data will appear after valid rosters are observed.</p>
          )}
        </div>
      </section>

      <section className="panel split-panel">
        <div>
          <div className="section-heading">
            <h2>Progression</h2>
            <p>Player score over time, alongside guild median and leader.</p>
          </div>
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={progressionData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(79, 111, 82, 0.2)" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line dataKey="playerScore" dot={false} name="Player" stroke="#8c4f34" strokeWidth={3} />
                <Line dataKey="guildMedian" dot={false} name="Guild median" stroke="#4f6f52" strokeWidth={2} />
                <Line dataKey="guildLeader" dot={false} name="Guild leader" stroke="#17241c" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <div className="section-heading">
            <h2>Recent Performance</h2>
            <p>Daily score earned and rolling win rate, both against dates.</p>
          </div>
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={recentPerformance}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(79, 111, 82, 0.2)" />
                <XAxis dataKey="date" />
                <YAxis yAxisId="left" />
                <YAxis domain={[0, 100]} orientation="right" yAxisId="right" />
                <Tooltip />
                <Bar dataKey="scoreDelta" fill="#d9c5b2" name="Daily score" yAxisId="left" />
                <Line dataKey="rollingWinRate" dot={false} name="Rolling win rate %" stroke="#8c4f34" strokeWidth={3} yAxisId="right" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="panel split-panel">
        <div>
          <div className="section-heading">
            <h2>Weekly Contribution</h2>
            <p>Six-week trend for Team, FFA, and Support scope.</p>
          </div>
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={weeklyScores}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(79, 111, 82, 0.2)" />
                <XAxis dataKey="week" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="team" fill="#8c4f34" name="Team" />
                <Bar dataKey="ffa" fill="#4f6f52" name="FFA" />
                <Bar dataKey="support" fill="#d9c5b2" name="Support" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <div className="section-heading">
            <h2>Top Rosters</h2>
            <p>Best confirmed and pending rosters connected to this player.</p>
          </div>
          {profile.combo_summaries.length ? (
            <div className="combo-grid">
              {profile.combo_summaries.map((combo) => (
                <article className="combo-card" key={combo.roster_key}>
                  <p className="eyebrow">{combo.status}</p>
                  <strong>{rosterLabel(combo)}</strong>
                  <span>{combo.title}</span>
                </article>
              ))}
            </div>
          ) : (
            <p className="quiet-copy">Roster summaries will appear after valid guild rosters are ingested.</p>
          )}
        </div>
      </section>
    </Layout>
  );
}

export function App() {
  return (
    <Routes>
      <Route element={<HomePage />} path="/" />
      <Route element={<LeaderboardPage />} path="/leaderboard" />
      <Route element={<PlayersPage />} path="/players" />
      <Route element={<PlayerProfilePage />} path="/players/:normalizedUsername" />
      <Route element={<Navigate replace to="/rosters/duo" />} path="/rosters" />
      <Route element={<RostersPage />} path="/rosters/:formatSlug" />
      <Route element={<RostersPage />} path="/rosters/:formatSlug/:rosterKey" />
      <Route element={<GamesPage />} path="/games" />
      <Route element={<WeeklyPage />} path="/weekly" />
      <Route element={<Navigate replace to="/rosters/duo" />} path="/combos" />
      <Route element={<RostersPage />} path="/combos/:formatSlug" />
      <Route element={<RostersPage />} path="/combos/:formatSlug/:rosterKey" />
      <Route element={<Navigate replace to="/games" />} path="/wins" />
    </Routes>
  );
}
