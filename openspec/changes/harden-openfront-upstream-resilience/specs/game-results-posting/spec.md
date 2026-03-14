# Game Results Posting Delta

## ADDED Requirements

### Requirement: Coordinate results polling through the shared OpenFront gate

The system SHALL route all OpenFront requests used by results polling through
the shared OpenFront upstream gate, including public lobby polling, public
games discovery, and public game detail fetches. Results posting SHALL wait for
the shared cooldown state instead of retrying independently of other OpenFront
callers.

#### Scenario: Another process is already using OpenFront

- **WHEN** results polling becomes ready to fetch lobbies or game details while
  another process holds the shared OpenFront lease
- **THEN** results polling waits until the shared lease and cooldown are
  released before issuing its request

#### Scenario: Results detail fetch receives upstream cooldown headers

- **WHEN** a results-related OpenFront response includes rate-limit cooldown
  headers
- **THEN** the next results request is delayed according to the shared
  OpenFront cooldown state
