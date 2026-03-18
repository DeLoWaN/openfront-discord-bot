# OpenFront Upstream Resilience Spec Delta

## MODIFIED Requirements

### Requirement: Coordinate OpenFront traffic through one shared gate

The system SHALL coordinate all OpenFront API traffic through one shared
cross-process gate backed by the shared MariaDB database unless an explicit
configured OpenFront bypass is active. Without a bypass, callers SHALL honor
the shared gate and the configured success-delay and fallback cooldown rules.
With a bypass, callers SHALL send the configured custom header and optional
`User-Agent` on every OpenFront API request and SHALL skip client-side gate and
cooldown waits.

#### Scenario: Request succeeds without upstream throttling

- **WHEN** an OpenFront request completes successfully and no longer cooldown
  is provided by the upstream response while bypass mode is not configured
- **THEN** the shared gate records the configured post-success cooldown before
  the next request may begin

#### Scenario: Bypass mode is configured

- **WHEN** the operator configures an OpenFront bypass header and value
- **THEN** every OpenFront caller sends that header and the optional configured
  `User-Agent` and does not wait on the shared gate before issuing requests

### Requirement: Honor upstream cooldown headers before retrying

The system SHALL derive OpenFront cooldown timing from upstream rate-limit
headers in this precedence order: numeric `Retry-After`, HTTP-date
`Retry-After`, standard `RateLimit-Reset`, supported vendor reset headers, and
only then a conservative local fallback. Every OpenFront caller SHALL use the
same parsing and cooldown behavior, and a `429` with an absent or zero-second
retry-after SHALL apply a configured minimum fallback cooldown when bypass mode
is not active.

#### Scenario: No retry-after value is present

- **WHEN** an OpenFront response signals a transient upstream failure without a
  usable cooldown header while bypass mode is not configured
- **THEN** the shared gate applies the configured minimum fallback cooldown
  before the next request

#### Scenario: Bypass mode still receives a 429

- **WHEN** an OpenFront request receives `429` while bypass mode is configured
- **THEN** the logs warn that the configured bypass key may be wrong instead of
  silently retrying through the ordinary cooldown loop
