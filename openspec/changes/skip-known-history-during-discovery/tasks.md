# Tasks: Skip Known History During Discovery

## 1. Persist discovery overlap accounting

- [ ] 1.1 Add an additive backfill run field and schema bootstrap/migration
  support for discovery-phase known-history skip counts.
- [ ] 1.2 Update backfill run summaries and status formatting to expose the new
  discovery skip counter alongside existing overlap and failure counters.

## 2. Move known-history filtering into discovery

- [ ] 2.1 Implement a shared eligibility helper that classifies prior
  successful readable history without excluding unreadable cache that still
  needs ordinary repair.
- [ ] 2.2 Update team and FFA discovery to increment the discovery skip counter
  and avoid creating `BackfillGame` rows when overlap is excluded early.
- [ ] 2.3 Keep hydration-time known-history checks as a compatibility fallback
  for pre-existing queued rows and mixed-semantics resumed runs.

## 3. Verify backfill behavior and operator output

- [ ] 3.1 Add or update tests for discovery-phase exclusion of known readable
  history and for unreadable-cache repair remaining eligible for hydration.
- [ ] 3.2 Update CLI and progress-log tests to cover the new discovery skip
  counter and the reduced hydration-phase skip path.
