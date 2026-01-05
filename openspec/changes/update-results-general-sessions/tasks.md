## 1. Implementation
- [x] 1.1 Add an OpenFront client method to list public games with `start/end/type` and `Content-Range` pagination.
- [x] 1.2 Update the results poller to gather game IDs from public games instead of clan sessions.
- [x] 1.3 Implement winner parsing from game details (clientID mapping, single clan tag, skip invalid cases).
- [x] 1.4 Include all players with the winning clan tag as winners and annotate non-winner client IDs as `*died early*`.
- [x] 1.5 Keep opponent grouping and embed formatting consistent with existing output.

## 2. Tests
- [x] 2.1 Add tests for `Content-Range` pagination handling.
- [x] 2.2 Add tests for winner tag resolution (single tag, mixed tags, missing tag).
- [x] 2.3 Add tests for the "died early" annotation and FFA game handling.

## 3. Validation
- [x] 3.1 Run the relevant pytest suite (at least `tests/test_results_poll.py`).
