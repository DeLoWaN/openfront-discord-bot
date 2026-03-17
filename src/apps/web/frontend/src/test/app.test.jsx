import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "../App";

function renderApp(pathname = "/") {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false
      }
    }
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[pathname]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  window.__GUILD_CONTEXT__ = {
    displayName: "North Guild",
    clanTags: ["NU"],
    currentPath: "/"
  };
  global.fetch = vi.fn((input) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.endsWith("/api/home")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            guild: { display_name: "North Guild", clan_tags: ["NU"] },
            competitive_pulse: {
              leaders: [{ rank: 1, normalized_username: "ace", display_username: "Ace", team_score: 300 }],
              most_active: [{ rank: 1, normalized_username: "ace", display_username: "Ace", team_recent_game_count_30d: 6, team_score: 300 }],
              support_spotlight: [
                { rank: 1, normalized_username: "bolt", display_username: "Bolt", support_bonus: 12 },
                { rank: 2, normalized_username: "cedar", display_username: "Cedar", support_bonus: 8 }
              ]
            },
            roster_podiums: {
              duo: [{ roster_key: "ace|bolt", members: [{ display_username: "Ace" }, { display_username: "Bolt" }], win_rate: 0.8, games_together: 5 }],
              trio: [],
              quad: []
            },
            pending_roster_teaser: { counts: { duo: 1, trio: 0, quad: 0 }, featured: [] },
            latest_games_preview: [
              {
                openfront_game_id: "game-1",
                map_name: "Europe",
                result: "win",
                team_distribution: "6 teams of 2 (Duos)",
                ended_at: "2026-03-15T12:00:00"
              }
            ],
            weekly_pulse: {
              scope: "team",
              rows: [{ rank: 1, normalized_username: "ace", display_username: "Ace", score: 120, movement: { kind: "up", delta: 2 } }],
              movers: [{ normalized_username: "ace", display_username: "Ace", movement: { kind: "up", delta: 2 } }]
            },
            recent_badges: [{ normalized_username: "ace", display_username: "Ace", badge_code: "team-grinder", label: "Team Grinder", badge_level: "Bronze" }]
          }),
          { status: 200 }
        )
      );
    }
    if (url.includes("/api/rosters/duo/ace%7Cbolt")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            combo: {
              roster_key: "ace|bolt",
              status: "confirmed",
              title: "Duos",
              members: [{ display_username: "Ace" }, { display_username: "Bolt" }],
              win_rate: 0.8,
              games_together: 5,
              wins_together: 4
            },
            history: [{ openfront_game_id: "duo-1", map_name: "Europe", did_win: true, mode_name: "Team", replay_link: "https://openfront.io/w17/game/duo-1" }]
          }),
          { status: 200 }
        )
      );
    }
    if (url.endsWith("/api/rosters/duo")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            confirmed: [{ roster_key: "ace|bolt", members: [{ display_username: "Ace" }, { display_username: "Bolt" }], win_rate: 0.8, games_together: 5 }],
            pending: [{ roster_key: "cedar|drift", members: [{ display_username: "Cedar" }, { display_username: "Drift" }], games_together: 2, win_rate: 1 }]
          }),
          { status: 200 }
        )
      );
    }
    if (url.includes("/api/leaderboards/team")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            columns: [
              { key: "display_username", label: "Player", sort_key: "display_username" },
              { key: "score", label: "Score", sort_key: "team_score" },
              { key: "ratio", label: "Ratio", sortable: false },
              { key: "win_rate", label: "Win Rate", sort_key: "team_win_rate" },
              { key: "team_game_count", label: "Games", sort_key: "team_game_count" },
              { key: "games_30d", label: "Games 30d", sort_key: "team_recent_game_count_30d" },
              { key: "support_bonus", label: "Support", sort_key: "support_bonus" }
            ],
            rows: [
              {
                normalized_username: "ace",
                display_username: "Ace",
                state: "Observed",
                score: 300,
                ratio: "4/5",
                win_rate: 0.8,
                team_game_count: 5,
                games_30d: 5,
                support_bonus: 12,
                team_score: 300,
                team_win_rate: 0.8,
                team_recent_game_count_30d: 5
              }
            ]
          }),
          { status: 200 }
        )
      );
    }
    if (url.includes("/api/scoring/team")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            summary: "Team score summary"
          }),
          { status: 200 }
        )
      );
    }
    if (url.startsWith("/api/results/recent")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [
              {
                openfront_game_id: "game-1",
                map_name: "Europe",
                mode: "Team",
                result: "win",
                team_distribution: "6 teams of 2 (Duos)",
                ended_at: "2026-03-15T12:00:00",
                replay_link: "https://openfront.io/w17/game/game-1",
                guild_team_players: [{ normalized_username: "ace", display_username: "Ace" }],
                winner_players: {
                  guild: [{ client_id: "a1", display_username: "Ace" }],
                  other: [{ client_id: "b1", display_username: "Enemy" }]
                },
                map_thumbnail_url: "https://openfront.io/maps/europe/thumbnail.webp"
              }
            ]
          }),
          { status: 200 }
        )
      );
    }
    if (url.includes("/api/weekly?scope=team")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            scope: "team",
            weeks: ["2026-02-09", "2026-02-16", "2026-02-23", "2026-03-02", "2026-03-09", "2026-03-16"],
            rows: [{ rank: 1, normalized_username: "ace", display_username: "Ace", score: 120, movement: { kind: "up", delta: 2 }, history: [10, 20, 40, 50, 80, 120] }],
            movers: [{ normalized_username: "ace", display_username: "Ace", movement: { kind: "up", delta: 2 } }]
          }),
          { status: 200 }
        )
      );
    }
    if (url.includes("/api/players/ace/timeseries")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            daily_progression: [
              { date: "2026-03-10", score: 100 },
              { date: "2026-03-11", score: 150 }
            ],
            daily_benchmarks: [
              { date: "2026-03-10", median_score: 80, leader_score: 120 },
              { date: "2026-03-11", median_score: 100, leader_score: 160 }
            ],
            recent_performance: [
              { date: "2026-03-10", score_delta: 30, rolling_win_rate: 0.5 },
              { date: "2026-03-11", score_delta: 50, rolling_win_rate: 0.75 }
            ],
            weekly_scores: [
              { week_start: "2026-03-03", team: 40, ffa: 0, support: 5 },
              { week_start: "2026-03-10", team: 120, ffa: 20, support: 12 }
            ]
          }),
          { status: 200 }
        )
      );
    }
    if (url.includes("/api/players/ace")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            player: { display_username: "Ace", normalized_username: "ace", state: "Observed", team_score: 300 },
            badges: [{ badge_code: "team-grinder", label: "Team Grinder", badge_level: "Bronze", earned_at: "2026-03-15T12:00:00" }],
            badge_catalog: [
              { badge_code: "team-grinder", label: "Team Grinder", description: "Play Team games", is_locked: false, levels: [{ name: "Bronze", earned: true }] },
              { badge_code: "quartermaster", label: "Quartermaster", description: "Donate heavily", is_locked: true }
            ],
            best_partners: [{ normalized_username: "bolt", display_username: "Bolt", win_rate: 0.8 }],
            combo_summaries: [{ roster_key: "ace|bolt", members: [{ display_username: "Ace" }, { display_username: "Bolt" }], status: "confirmed", title: "Duos" }],
            weekly_summary: { score: 120, rank: 1, movement: { kind: "up", delta: 2 } },
            sections: {
              team: { score: 300, wins: 4, games: 5, score_note_label: "Wins / Games" },
              ffa: { score: 80, wins: 1, games: 2, score_note_label: "Wins / Games" },
              support: { support_bonus: 5, role_label: "Hybrid" }
            }
          }),
          { status: 200 }
        )
      );
    }
    return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders home engagement sections from backend contracts", async () => {
  renderApp("/");

  await waitFor(() => {
    expect(screen.getByRole("link", { name: /leaderboard/i })).toBeInTheDocument();
  });
  expect(screen.getByText(/competitive pulse/i)).toBeInTheDocument();
  expect(screen.getByText(/weekly pulse/i)).toBeInTheDocument();
  expect(screen.getByText(/latest guild games/i)).toBeInTheDocument();
  expect(screen.getByText(/ace \/ bolt/i)).toBeInTheDocument();
});

test("renders player profile badge catalog and dated charts", async () => {
  renderApp("/players/ace");

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "Ace" })).toBeInTheDocument();
  });
  expect(screen.getByRole("heading", { name: /badge catalog/i })).toBeInTheDocument();
  expect(screen.getByText(/quartermaster/i)).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /progression/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /recent performance/i })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /weekly contribution/i })).toBeInTheDocument();
});

test("renders rosters confirmed, pending, and detail views", async () => {
  renderApp("/rosters/duo/ace%7Cbolt");

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "Confirmed" })).toBeInTheDocument();
  });
  expect(screen.getByText(/cedar \/ drift/i)).toBeInTheDocument();
  expect(screen.getByText(/replay/i)).toBeInTheDocument();
});

test("renders recent games and leaderboard sorting controls", async () => {
  renderApp("/leaderboard");

  await waitFor(() => {
    expect(screen.getByRole("button", { name: /score/i })).toBeInTheDocument();
  });
  fireEvent.click(screen.getByRole("button", { name: /score/i }));
  await waitFor(() => {
    expect(
      global.fetch.mock.calls.some(([input]) => String(input).includes("sort_by=team_score"))
    ).toBe(true);
  });

  renderApp("/games");

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: /recent games/i })).toBeInTheDocument();
  });
  expect(screen.getByText(/guild winners/i)).toBeInTheDocument();
  expect(screen.getByText(/watch replay/i)).toBeInTheDocument();
});

test("renders weekly trends with labeled weeks instead of raw chip history", async () => {
  renderApp("/weekly");

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: /weekly/i })).toBeInTheDocument();
  });
  expect(screen.getByText("2026-02-09")).toBeInTheDocument();
  expect(screen.getByText("2026-03-16")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: /trend chart/i })).toBeInTheDocument();
});
