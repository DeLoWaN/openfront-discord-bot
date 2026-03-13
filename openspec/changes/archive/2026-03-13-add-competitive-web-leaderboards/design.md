# Add Competitive Web Leaderboards Design

## Context

The current guild website is intentionally minimal. It renders HTML directly
from backend services, reads one guild-scoped aggregate table, and exposes a
single leaderboard ranked by win totals. That was enough to launch the
web-first product surface, but it is too limited for a competitive site where
players want to compare different play styles, separate Team and FFA
performance, and understand why one player ranks above another.

This change also introduces a stronger architectural requirement than the
current site provides. The backend must own score computation, stat
aggregation, and JSON contracts. The frontend should stay replaceable so the
project can ship the functional leaderboard product first, then revisit the
visual design and UX later without rewriting business logic.

Recent investigation against live OpenFront team games confirmed that
`GET /public/game/:id` turn payloads expose exact `donate_troops` and
`donate_gold` intents. That makes support scoring feasible without relying on
weak economy proxies such as final gold totals. The same investigation also
confirmed a current limitation: donation recipients are not directly resolvable
to the public `clientID` values already exposed in the player list, so
pair-specific support metrics are out of scope for the first version.

Further product review exposed two additional issues with the first scoring and
identity pass:

- tracked clan-tag prefixes such as `[NU] Temujin` and `[UN] Temujin` still
  split the same observed player because the merge key is based on the raw
  normalized username
- the current raw `0.7 * team_score + 0.3 * ffa_score` Overall formula can
  distort rankings because Team and FFA scores do not share the same natural
  scale and one mode may have only a tiny sample size

## Goals / Non-Goals

**Goals:**

- Add distinct `Team`, `FFA`, `Overall`, and `Support` leaderboard views for
  each guild.
- Merge observed players across tracked clan-tag username variants inside the
  same guild scope.
- Remove tracked clan-tag prefixes from public player-name display on the
  guild website.
- Score team games with a result-first model that can reward support play
  without penalizing frontliners for not donating.
- Use exact donation events from OpenFront turn payloads for support metrics.
- Keep leaderboard reads API-driven and backed by stored aggregates instead of
  recalculating scores in the browser or on each request.
- Expose a small player-facing explanation of how scores work, including what
  makes a match more difficult.
- Decouple frontend rendering from backend scoring so the design can be
  replaced later without changing ingestion or aggregate logic.

**Non-Goals:**

- Reconstruct full territory state or tile ownership over time.
- Infer whether a player was hoarding troops by estimating time spent at cap.
- Penalize players directly for low donation totals.
- Build a polished final visual design in the same change.
- Derive pair-specific "who supported whom" metrics before recipient identity
  mapping is understood.
- Build a full placement-based FFA model in the same change.

## Decisions

### 1. Strip tracked clan-tag prefixes for observed identity and public display

Observed identity remains guild-scoped, but it should no longer depend on the
tracked clan-tag prefix that a player happened to use in a given game.

For each guild-scoped observed player row:

- inspect the leading `[TAG]` prefix in the raw username
- if that prefix belongs to the guild's tracked clan tags, strip it before
  deriving the observed merge key
- if the prefix is not tracked by the guild, leave the username untouched
- preserve the raw username and effective clan tag internally for ingestion,
  debugging, and auditability

The same tracked-tag-stripped base username should also be used for public
player-name display on leaderboard and profile pages. Because the site is
already scoped to a guild, tracked clan tags are useful for ingestion but
redundant in public display.

Alternatives considered:

- Strip every `[TAG]` prefix unconditionally: too broad and likely to merge
  unrelated players.
- Keep the raw username as the observed identity key: fails the desired guild
  player merge behavior.

### 2. Split competitive views into Team, FFA, Overall, and Support

The website will expose four leaderboard views:

- `Team`: the primary clan-facing competitive view
- `FFA`: a separate solo-performance view
- `Overall`: a weighted blend of Team and FFA
- `Support`: a donation-first supporting view

`Team` remains the default view because the website is guild-centric and clan
performance is the main product. `FFA` stays separate because support and
alliance concepts do not apply. `Overall` remains guild-first, but it should
only converge toward a `70% Team / 30% FFA` influence split when both modes
have meaningful sample sizes. `Support` exists as a dedicated view so support
play is visible and sortable without having to dominate the main Team ranking.

Alternatives considered:

- One unified leaderboard with filters: simpler UI, but too easy to conflate
  incompatible metrics.
- A `50/50` Overall score: more symmetrical, but weaker fit for a guild-first
  website.

### 3. Make support an additive bonus, never a penalty

The Team score will remain result-first. Support contributes a capped bonus
based on exact donations, but players with low or zero donation totals do not
lose points for that alone. This preserves legitimate frontline play, where a
player may be expected to spend troops on attacks rather than pass them to
allies.

The first version will expose support volume and support-share metrics to help
players interpret roles, but only positive support signals affect the Team
score. Role labels such as `Backliner`, `Hybrid`, and `Frontliner` stay
descriptive rather than punitive.

Alternatives considered:

- Penalize low-support players: would mis-rank valid frontline contributors.
- Ignore support entirely in Team score: simpler, but fails the product goal of
  recognizing team-oriented play.

### 4. Use exact turn-level donation events for team support metrics

Guild-relevant Team games will fetch and cache turnful game detail via
`/public/game/:id`, then derive per-player donation totals from
`donate_troops` and `donate_gold` intents. FFA games continue to use turn-free
detail only because support is irrelevant there.

Turn ingestion will remain donor-centric in the first version. The system will
record who donated, how much, and how often, but will not attempt to publish
recipient-level leaderboards because the current `recipient` values do not map
cleanly to public `clientID` values.

Alternatives considered:

- Use economy proxies such as gold totals or trade counts: rejected because
  they are too correlated with territory size and game state.
- Fetch turn data for all games: simpler pipeline, but too expensive relative
  to the actual needs of scoring.

### 5. Normalize Team and FFA scores separately before combining them

`Overall` will not sum raw Team and FFA totals directly. The backend will
compute Team and FFA scores in their own domains, normalize them to a shared
comparison scale, and weight them by both the intended Team-first product bias
and each player's actual sample confidence in that mode. This avoids cases
where one mode dominates only because its raw score distribution is wider or
because the player has only a tiny sample in the weaker mode.

The intended behavior is:

- Team and FFA remain independently meaningful in their own leaderboard views
- Overall trends toward a `70/30` Team/FFA influence split when both mode
  samples are strong
- a very small FFA sample should not heavily drag down a strong Team player
- a very small Team sample should not overstate a strong FFA player on a
  guild-first website

The backend will expose the component scores and the resulting Overall score as
returned values, so the frontend never needs to know the normalization
formula.

Alternatives considered:

- Raw weighted sum of unnormalized scores: easier to implement, but unstable if
  the Team and FFA formulas evolve differently and too sensitive to tiny
  cross-mode samples.

### 6. Materialize richer per-guild aggregates for leaderboard reads

The system will continue to treat stored aggregates as the source for website
reads. Team, FFA, Overall, and Support views will be served from additive
aggregate fields rather than by replaying raw observations or turn streams in
request time.

At minimum, the aggregate model needs separate Team and FFA game counts, win
counts, score fields, support totals, donation action counts, and role-label
inputs. Per-game derived metrics may live in a new additive table if extending
`GameParticipant` directly becomes too dense, but the read path should still
collapse into guild-level player aggregates before the API serves leaderboard
rows.

Alternatives considered:

- Compute scores live from raw observations: too slow and harder to reason
  about.
- Store only raw donation events and defer aggregation to API reads: simpler
  writes, but moves too much work to read time.

### 7. Expose the website through an API-first backend contract

The backend will provide guild-scoped JSON endpoints for leaderboard views,
player profiles, and scoring explanation content. The frontend becomes a thin
consumer of those endpoints. It can sort by the numeric fields returned by the
API, but it does not own score computation or duplicate formulas.

The first frontend iteration should stay functional rather than visually final:
clear navigation, usable tables, basic filtering and sorting, and a concise
scoring explanation. A later design-focused change can replace layout and style
without changing how scores are produced.

Alternatives considered:

- Keep server-rendered HTML as the main contract: faster short term, but too
  coupled to ongoing UX work.
- Build a heavy standalone frontend immediately: unnecessary while the product
  is still validating scoring and leaderboard behavior.

### 8. Explain match difficulty and overall weighting in player language

Player-facing scoring copy will avoid the ambiguous word `difficulty` on its
own. Instead, the site will explain that a match becomes more difficult when a
player must beat more teams. For example, winning a seven-team match counts
more than winning a two-team match. The site will state that this competitive
difficulty is based on team count, not on the upstream API's `difficulty`
label.

The site should also explain that `Overall` does not blindly mix raw Team and
FFA scores. It combines the two modes after separate normalization, with a
Team-first target weighting and reduced influence from modes where the player
has only a small sample size.

Alternatives considered:

- Reuse the API `difficulty` label in scoring explanations: too easy to confuse
  with competitive weighting.

## Risks / Trade-offs

- [Turn payloads are much larger than turn-free payloads] -> Fetch and cache
  turn data only for guild-relevant Team games that need support scoring.
- [Donation recipients cannot yet be tied back to public player identities] ->
  Keep support metrics donor-centric and defer pair-specific synergy features.
- [Observed usernames remain imperfect identities] -> Keep linked versus
  observed state explicit, merge only tracked clan-tag variants, and avoid
  overstating precision in competitive views.
- [Multiple leaderboard views can make the product feel more complex] -> Keep
  Team as the default and present other views as clearly labeled tabs.
- [Score explanations can become either too vague or too gameable] -> Expose
  score factors and weight directions, but not every internal constant.
- [Tracked-tag stripping could hide meaningful differences for unrelated
  players] -> Strip tracked prefixes only when they belong to the guild's own
  clan tags.

## Migration Plan

1. Extend the shared schema with additive support-metric storage and richer
   guild aggregate fields.
2. Update hydration and caching so guild-relevant Team games fetch and retain
   turnful detail while FFA and irrelevant games can remain turn-free.
3. Derive per-player team donation and attack metrics during ingestion and fold
   them into guild aggregates.
4. Derive tracked-tag-stripped observed identity keys and public display names
   for guild-scoped players.
5. Recalculate Overall from normalized Team and FFA mode outputs with
   confidence-aware weighting instead of a raw weighted sum.
6. Add backend services and JSON endpoints for Team, FFA, Overall, Support,
   player profiles, and scoring explanation content.
7. Replace the current server-rendered leaderboard pages with a minimal
   API-backed frontend shell that consumes the new endpoints.
8. Backfill or replay existing cached data so leaderboard scores are rebuilt
   from the richer aggregate model.

Rollback strategy:

- Keep the current leaderboard pages available behind the existing aggregate
  model until the new API-backed leaderboard data is validated.
- Make the new schema additive so the old reads can survive while score logic
  is verified.
- If turn ingestion proves too expensive, fall back to Team scoring without the
  support bonus while keeping the multi-view leaderboard model.

## Open Questions

- Which recent-form window should the first release use for leaderboard and
  profile displays?
- What minimum sample thresholds should gate sorts such as `win_rate` and
  `support_share`?
- Should the first profile view surface role labels only, or also display a
  short textual description of why that role was assigned?
- Should the first FFA revision incorporate lobby-size-aware weighting beyond
  the current win-based formula, or leave that for a follow-up change?
