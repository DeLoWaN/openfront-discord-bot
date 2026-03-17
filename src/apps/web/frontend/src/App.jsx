import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
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

const guildContext = globalThis.window?.__GUILD_CONTEXT__ ?? {
  displayName: "Guild",
  clanTags: [],
  currentPath: "/"
};

function fetchJson(url) {
  return fetch(url).then(async (response) => {
    if (!response.ok) {
      const payload = await response.text();
      throw new Error(payload || `Request failed: ${response.status}`);
    }
    return response.json();
  });
}

function useApiQuery(queryKey, url) {
  return useQuery({
    queryKey,
    queryFn: () => fetchJson(url)
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

function Layout({ title, subtitle, children }) {
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
          <NavPill to="/combos">Combos</NavPill>
          <NavPill to="/wins">Recent Wins</NavPill>
        </nav>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}

function PlayerLink({ player }) {
  return <Link to={`/players/${player.normalized_username}`}>{player.display_username}</Link>;
}

function ComboRoster({ combo }) {
  return combo.members.map((member) => member.display_username).join(" / ");
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
  return (
    <Layout
      title={data.guild.display_name}
      subtitle="Track guild momentum, watch combos mature, and keep recent wins and badges visible."
    >
      <section className="panel">
        <div className="section-heading">
          <h2>Competitive Pulse</h2>
          <p>Leaders, active grinders, and support anchors in one glance.</p>
        </div>
        <div className="pulse-grid">
          <div>
            <h3>Leaders</h3>
            <ul className="list-card">
              {data.competitive_pulse.leaders.map((row) => (
                <li key={row.normalized_username}>
                  <PlayerLink player={row} />
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
                  <PlayerLink player={row} />
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
                  <PlayerLink player={row} />
                  <span>{row.support_bonus}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Combo Podiums</h2>
          <p>Confirmed duos, trios, and quads ranked only on raw win rate.</p>
        </div>
        <div className="combo-grid">
          {["duo", "trio", "quad"].map((formatSlug) => {
            const combos = data.combo_podiums[formatSlug];
            return (
              <article className="combo-card" key={formatSlug}>
                <div className="card-header">
                  <h3>{formatSlug === "duo" ? "Duos" : formatSlug === "trio" ? "Trios" : "Quads"}</h3>
                  <Link to={`/combos/${formatSlug}`}>Open</Link>
                </div>
                {combos.length ? (
                  <ul className="combo-list">
                    {combos.map((combo) => (
                      <li key={combo.roster_key}>
                        <Link to={`/combos/${formatSlug}/${encodeURIComponent(combo.roster_key)}`}>
                          {ComboRoster({ combo })}
                        </Link>
                        <span>{formatPercent(combo.win_rate)} • {combo.games_together} games</span>
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
            <h2>Pending Combo Watch</h2>
            <p>Track rosters that are still climbing toward confirmation.</p>
          </div>
          <MetricGrid
            items={Object.entries(data.pending_combo_teaser.counts).map(([label, value]) => ({
              label,
              value
            }))}
          />
        </div>
        <div>
          <div className="section-heading">
            <h2>Latest Guild Wins</h2>
            <p>Fresh wins stay visible. Old archive depth does not dominate.</p>
          </div>
          {data.recent_wins_preview.length ? (
            <ul className="list-card">
              {data.recent_wins_preview.map((item) => (
                <li key={item.openfront_game_id}>
                  <a href={item.replay_link} rel="noreferrer" target="_blank">
                    {item.map_name || "Unknown map"}
                  </a>
                  <span>{item.mode}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="quiet-copy">No recent wins yet.</p>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Recent Badges</h2>
          <p>Recently unlocked achievements, ordered by the time they were earned.</p>
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
          <p className="quiet-copy">Badge activity will appear here after the next earned unlock.</p>
        )}
      </section>
    </Layout>
  );
}

function LeaderboardPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const view = searchParams.get("view") || "team";
  const leaderboardQuery = useApiQuery(["leaderboard", view], `/api/leaderboards/${view}`);
  const scoringQuery = useApiQuery(["scoring", view], `/api/scoring/${view}`);

  if (leaderboardQuery.isLoading || scoringQuery.isLoading) {
    return <LoadingBlock label="Loading leaderboard..." />;
  }
  if (leaderboardQuery.isError || scoringQuery.isError) {
    return <EmptyState title="Leaderboard unavailable" body="The leaderboard could not be loaded." />;
  }
  const rows = leaderboardQuery.data.rows;
  const scoring = scoringQuery.data;
  return (
    <Layout
      title="Leaderboard"
      subtitle="Cumulative Team, FFA, and Support views with recent activity kept visible beside the score."
    >
      <section className="panel">
        <div className="tab-row">
          {["team", "ffa", "support"].map((item) => (
            <button
              className={`tab-button${item === view ? " is-active" : ""}`}
              key={item}
              onClick={() => setSearchParams({ view: item })}
              type="button"
            >
              {item.toUpperCase()}
            </button>
          ))}
        </div>
        <p className="quiet-copy">{scoring.summary}</p>
        <div className="leaderboard-table">
          <div className="leaderboard-row leaderboard-head">
            <span>Player</span>
            <span>Primary</span>
            <span>Wins</span>
            <span>Games</span>
            <span>Recent</span>
          </div>
          {rows.map((row) => (
            <div className="leaderboard-row" key={row.normalized_username}>
              <span>
                <PlayerLink player={row} /> <em>{row.state}</em>
              </span>
              <span>{view === "team" ? row.team_score : view === "ffa" ? row.ffa_score : row.support_bonus}</span>
              <span>{view === "ffa" ? row.ffa_win_count : view === "support" ? row.donation_action_count : row.team_win_count}</span>
              <span>{view === "ffa" ? row.ffa_game_count : view === "support" ? row.team_game_count : row.team_game_count}</span>
              <span>{view === "ffa" ? row.ffa_recent_game_count_30d : row.team_recent_game_count_30d}</span>
            </div>
          ))}
        </div>
      </section>
    </Layout>
  );
}

function PlayersPage() {
  const leaderboardQuery = useApiQuery(["players-index"], "/api/leaderboards/team");

  if (leaderboardQuery.isLoading) {
    return <LoadingBlock label="Loading players..." />;
  }
  if (leaderboardQuery.isError) {
    return <EmptyState title="Players unavailable" body={leaderboardQuery.error.message} />;
  }
  return (
    <Layout
      title="Players"
      subtitle="Public guild profiles stay visible whether a player linked their account or not."
    >
      <section className="panel">
        <div className="player-grid">
          {leaderboardQuery.data.rows.map((player) => (
            <article className="player-card" key={player.normalized_username}>
              <p className="eyebrow">{player.state}</p>
              <h2>{player.display_username}</h2>
              <MetricGrid
                items={[
                  { label: "Team Score", value: player.team_score },
                  { label: "FFA Score", value: player.ffa_score },
                  { label: "Support", value: player.support_bonus }
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

function CombosPage() {
  const { formatSlug = "duo", rosterKey } = useParams();
  const normalizedFormat = formatSlug || "duo";
  const rankingsQuery = useApiQuery(["combos", normalizedFormat], `/api/combos/${normalizedFormat}`);
  const detailQuery = useApiQuery(
    ["combo-detail", normalizedFormat, rosterKey],
    rosterKey
      ? `/api/combos/${normalizedFormat}/${encodeURIComponent(rosterKey)}`
      : `/api/combos/${normalizedFormat}`
  );

  if (rankingsQuery.isLoading) {
    return <LoadingBlock label="Loading combos..." />;
  }
  if (rankingsQuery.isError) {
    return <EmptyState title="Combos unavailable" body={rankingsQuery.error.message} />;
  }
  const data = rankingsQuery.data;
  const detail = rosterKey && detailQuery.data?.combo ? detailQuery.data : null;
  return (
    <Layout
      title="Combos"
      subtitle="Confirmed rosters stay separate from pending samples, with strict full-guild validation only."
    >
      <section className="panel">
        <div className="tab-row">
          {["duo", "trio", "quad"].map((item) => (
            <NavLink className={`tab-button${item === normalizedFormat ? " is-active" : ""}`} key={item} to={`/combos/${item}`}>
              {item === "duo" ? "Duos" : item === "trio" ? "Trios" : "Quads"}
            </NavLink>
          ))}
        </div>
        <div className="split-panel">
          <div>
            <h2>Confirmed</h2>
            {data.confirmed.length ? (
              <ul className="combo-list">
                {data.confirmed.map((combo) => (
                  <li key={combo.roster_key}>
                    <Link to={`/combos/${normalizedFormat}/${encodeURIComponent(combo.roster_key)}`}>
                      {ComboRoster({ combo })}
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
            {data.pending.length ? (
              <ul className="combo-list">
                {data.pending.map((combo) => (
                  <li key={combo.roster_key}>
                    <Link to={`/combos/${normalizedFormat}/${encodeURIComponent(combo.roster_key)}`}>
                      {ComboRoster({ combo })}
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
            <h2>{ComboRoster({ combo: detail.combo })}</h2>
            <p>{detail.combo.status === "confirmed" ? "Confirmed" : "Pending"} {detail.combo.title}</p>
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
                <strong>{entry.map_name || "Unknown map"}</strong>
                <span>{entry.did_win ? "Win" : "Loss"}</span>
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

function WinsPage() {
  const winsQuery = useApiQuery(["recent-wins"], "/api/results/recent");

  if (winsQuery.isLoading) {
    return <LoadingBlock label="Loading recent wins..." />;
  }
  if (winsQuery.isError) {
    return <EmptyState title="Recent wins unavailable" body={winsQuery.error.message} />;
  }
  return (
    <Layout
      title="Recent Wins"
      subtitle="Only the freshest Team and FFA wins matter here. This page is intentionally recent, not archival."
    >
      <section className="panel">
        <div className="win-feed">
          {winsQuery.data.items.map((item) => (
            <article className="win-card" key={item.openfront_game_id}>
              <p className="eyebrow">{item.mode}</p>
              <h2>{item.map_name || "Unknown map"}</h2>
              <p>{item.format_label}</p>
              <span>{formatDate(item.ended_at)}</span>
              <div className="player-chip-row">
                {item.players.map((player) => (
                  <Link className="tag-chip" key={`${item.openfront_game_id}-${player.normalized_username}`} to={`/players/${player.normalized_username}`}>
                    {player.display_username}
                  </Link>
                ))}
              </div>
              <a href={item.replay_link} rel="noreferrer" target="_blank">
                Watch replay
              </a>
            </article>
          ))}
        </div>
      </section>
    </Layout>
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
  const latestProgress = timeseries.progression.map((entry, index) => ({
    index: index + 1,
    teamScore: entry.team_score,
    ffaScore: entry.ffa_score
  }));
  const recentForm = timeseries.recent_form.map((entry, index) => ({
    index: index + 1,
    outcome: entry.did_win ? 1 : 0
  }));

  return (
    <Layout
      title={profile.player.display_username}
      subtitle="Individual mastery, social combos, and recent form on one page."
    >
      <section className="panel">
        <MetricGrid
          items={[
            { label: "Team Score", value: profile.sections.team.score, note: `${profile.sections.team.wins}/${profile.sections.team.games}` },
            { label: "FFA Score", value: profile.sections.ffa.score, note: `${profile.sections.ffa.wins}/${profile.sections.ffa.games}` },
            { label: "Support Bonus", value: profile.sections.support.support_bonus, note: profile.sections.support.role_label }
          ]}
        />
      </section>

      <section className="panel split-panel">
        <div>
          <div className="section-heading">
            <h2>Badges</h2>
            <p>Code-defined achievements with persisted award dates.</p>
          </div>
          {profile.badges.length ? (
            <div className="badge-grid">
              {profile.badges.map((badge) => (
                <article className="badge-card" key={`${badge.badge_code}-${badge.badge_level || "base"}`}>
                  <strong>{badge.label}</strong>
                  <span>{badge.badge_level || "Unlocked"}</span>
                </article>
              ))}
            </div>
          ) : (
            <p className="quiet-copy">No badge earned yet.</p>
          )}
        </div>
        <div>
          <div className="section-heading">
            <h2>Best Partners</h2>
            <p>Guild teammates with the strongest shared sample so far.</p>
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
            <p className="quiet-copy">Partner data will appear after valid combos are observed.</p>
          )}
        </div>
      </section>

      <section className="panel split-panel">
        <div>
          <div className="section-heading">
            <h2>Progression</h2>
            <p>Cumulative score keeps the long view visible.</p>
          </div>
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={latestProgress}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(79, 111, 82, 0.2)" />
                <XAxis dataKey="index" />
                <YAxis />
                <Tooltip />
                <Line dataKey="teamScore" dot={false} stroke="#6c584c" strokeWidth={3} />
                <Line dataKey="ffaScore" dot={false} stroke="#4f6f52" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div>
          <div className="section-heading">
            <h2>Recent Form</h2>
            <p>Recent results live beside score instead of changing its meaning.</p>
          </div>
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={recentForm}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(79, 111, 82, 0.2)" />
                <XAxis dataKey="index" />
                <YAxis ticks={[0, 1]} />
                <Tooltip />
                <Bar dataKey="outcome" fill="#b86f52" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <h2>Top Combos</h2>
          <p>Confirmed and pending combo summaries connected to this player.</p>
        </div>
        {profile.combo_summaries.length ? (
          <div className="combo-grid">
            {profile.combo_summaries.map((combo) => (
              <article className="combo-card" key={combo.roster_key}>
                <p className="eyebrow">{combo.status}</p>
                <strong>{ComboRoster({ combo })}</strong>
                <span>{combo.title}</span>
              </article>
            ))}
          </div>
        ) : (
          <p className="quiet-copy">Combo summaries will appear after valid full-guild roster games are ingested.</p>
        )}
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
      <Route element={<Navigate replace to="/combos/duo" />} path="/combos" />
      <Route element={<CombosPage />} path="/combos/:formatSlug" />
      <Route element={<CombosPage />} path="/combos/:formatSlug/:rosterKey" />
      <Route element={<WinsPage />} path="/wins" />
    </Routes>
  );
}
