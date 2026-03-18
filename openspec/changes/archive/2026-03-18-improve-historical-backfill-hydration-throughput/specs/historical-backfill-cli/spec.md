# Historical Backfill CLI Spec Delta

## MODIFIED Requirements

### Requirement: Start historical backfill runs from an external CLI

The system SHALL provide an external CLI command that starts a historical
backfill run by accepting the requested date range and creating a durable run
record for the hybrid discovery-and-hydration pipeline. Ordinary `start`
behavior SHALL skip games that were already hydrated successfully in earlier
runs when their cached payloads remain readable, and it SHALL reserve all
reparsing of known history for explicit replay. The `start` command SHALL also
accept explicit OpenFront throttling controls for backfill hydration and SHALL
default to a non-bursty safe profile when no overrides are provided.

#### Scenario: Operator starts with no explicit OpenFront tuning

- **WHEN** an operator starts a backfill without passing any OpenFront
  throttling overrides
- **THEN** the CLI uses its safe default OpenFront profile instead of a hidden
  aggressive burst profile

### Requirement: Resume interrupted historical backfill runs from an external CLI

The system SHALL provide an external CLI command that resumes an interrupted or
paused historical backfill run from its persisted state instead of restarting
from the beginning. Ordinary `resume` behavior SHALL skip overlap with games
that were already hydrated successfully in earlier runs when their cached
payloads remain readable, and it SHALL reserve full reprocessing for explicit
replay. The `resume` command SHALL accept the same explicit OpenFront
throttling controls as `start`.

#### Scenario: Operator resumes with explicit OpenFront tuning

- **WHEN** an operator resumes a run while passing OpenFront throttling
  overrides
- **THEN** the CLI applies those overrides to the resumed hydration work

### Requirement: Probe OpenFront fetch behavior from an external CLI

The system SHALL provide an external CLI command that probes OpenFront fetch
behavior over a bounded historical sample without creating backfill runs,
cached payloads, or ingested observations. The probe SHALL discover candidate
public game ids in the requested window, sample a bounded subset, fetch
`/public/game/{id}?turns=false` for calibration, report operator-readable
latency and rate-limit metrics, and stop early when the selected profile is
clearly too aggressive.

#### Scenario: Operator probes a safe profile

- **WHEN** an operator runs the probe command over a bounded time window
- **THEN** the CLI reports sampled request count, success count, rate-limit
  count, retry-after distribution, latency percentiles, throughput, and the
  OpenFront profile used

#### Scenario: Probe encounters a long upstream cooldown

- **WHEN** a probe request receives a `429` whose retry-after value indicates a
  large cooldown
- **THEN** the probe records that result and stops early instead of continuing
  the remaining sample
