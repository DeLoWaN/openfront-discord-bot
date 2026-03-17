import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
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
              leaders: [{ normalized_username: "ace", display_username: "Ace", team_score: 300 }],
              most_active: [{ normalized_username: "ace", display_username: "Ace", team_recent_game_count_30d: 6 }],
              support_spotlight: [{ normalized_username: "bolt", display_username: "Bolt", support_bonus: 12 }]
            },
            combo_podiums: {
              duo: [{ roster_key: "ace|bolt", members: [{ display_username: "Ace" }, { display_username: "Bolt" }], win_rate: 0.8, games_together: 5 }],
              trio: [],
              quad: []
            },
            pending_combo_teaser: { counts: { duo: 1, trio: 0, quad: 0 }, featured: [] },
            recent_wins_preview: [],
            recent_badges: []
          }),
          { status: 200 }
        )
      );
    }
    if (url.includes("/api/combos/duo/ace%7Cbolt")) {
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
            history: [{ openfront_game_id: "duo-1", map_name: "Europe", did_win: true, replay_link: "https://openfront.io/#join=duo-1" }]
          }),
          { status: 200 }
        )
      );
    }
    if (url.endsWith("/api/combos/duo")) {
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
            rows: [{ normalized_username: "ace", display_username: "Ace", team_score: 300, state: "Observed" }]
          }),
          { status: 200 }
        )
      );
    }
    if (url.endsWith("/api/results/recent")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [{ openfront_game_id: "win-1", map_name: "Europe", mode: "Team", format_label: "Duos", ended_at: "2026-03-15T12:00:00", replay_link: "https://openfront.io/#join=win-1", players: [{ normalized_username: "ace", display_username: "Ace" }] }]
          }),
          { status: 200 }
        )
      );
    }
    if (url.includes("/api/players/ace/timeseries")) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            progression: [{ ended_at: "2026-03-15T12:00:00", team_score: 300 }],
            recent_form: [{ ended_at: "2026-03-15T12:00:00", did_win: true, mode: "Team" }]
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
            best_partners: [{ normalized_username: "bolt", display_username: "Bolt", win_rate: 0.8 }],
            combo_summaries: [{ roster_key: "ace|bolt", members: [{ display_username: "Ace" }, { display_username: "Bolt" }], status: "confirmed" }],
            sections: {
              team: { score: 300, wins: 4, games: 5, win_rate: 0.8, recent_games_30d: 5, last_game_at: "2026-03-15T12:00:00" },
              ffa: { score: 80, wins: 1, games: 2, win_rate: 0.5, recent_games_30d: 2, last_game_at: "2026-03-14T12:00:00" },
              support: { troops_donated: 10, gold_donated: 0, donation_actions: 1, support_bonus: 5, role_label: "Hybrid", recent_games_30d: 5, last_game_at: "2026-03-15T12:00:00" }
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
  expect(screen.getAllByRole("link", { name: "Ace" }).length).toBeGreaterThan(0);
  expect(screen.getByText(/ace \/ bolt/i)).toBeInTheDocument();
});

test("renders player profile achievements and graphs", async () => {
  renderApp("/players/ace");

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "Ace" })).toBeInTheDocument();
  });
  expect(screen.getByText(/team grinder/i)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Bolt" })).toBeInTheDocument();
  expect(screen.getByText(/progression/i)).toBeInTheDocument();
});

test("renders combos confirmed, pending, and detail views", async () => {
  renderApp("/combos/duo/ace%7Cbolt");

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: "Confirmed" })).toBeInTheDocument();
  });
  expect(screen.getByText(/cedar \/ drift/i)).toBeInTheDocument();
  expect(screen.getByText(/replay/i)).toBeInTheDocument();
});

test("renders recent wins feed", async () => {
  renderApp("/wins");

  await waitFor(() => {
    expect(screen.getByRole("heading", { name: /recent wins/i })).toBeInTheDocument();
  });
  expect(screen.getByText(/europe/i)).toBeInTheDocument();
  expect(screen.getByText(/watch replay/i)).toBeInTheDocument();
});
