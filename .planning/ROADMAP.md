# Roadmap: LoadSpiker

## Overview

LoadSpiker is a brownfield C/Python load testing library with several correctness defects that make its metrics untrustworthy and its concurrent use unsafe. This roadmap fixes the engine in dependency order: metrics first (the core value proposition), then dispatch reliability, then thread safety across all protocol pools, then real protocol I/O, then validation and test cleanup. Each phase delivers a verifiable improvement to the library's correctness and safety.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Metrics Correctness** - Fix RPS calculation and add P95/P99 percentile tracking through all reporters (completed 2026-04-29)
- [x] **Phase 2: Dispatch & Rate Control** - Replace main-thread usleep loop with proper worker pool dispatch and correct rate pacing (completed 2026-04-29)
- [x] **Phase 3: Thread Safety** - Mutex-protect all connection pools and replace non-reentrant libc calls (completed 2026-05-01)
- [x] **Phase 4: Protocol I/O** - Implement real network I/O for TCP send/receive/disconnect, UDP receive/close, and MQTT correctness (completed 2026-05-21)
- [ ] **Phase 5: Test Infrastructure** - Add concurrent stress tests, metric accuracy tests, behavioral parity tests, and clean up test layout

## Phase Details

### Phase 1: Metrics Correctness

**Goal**: Engine reports trustworthy RPS and exposes accurate P95/P99 latency to users and all reporters
**Depends on**: Nothing (first phase)
**Requirements**: METR-01, METR-02, METR-03, METR-04
**Success Criteria** (what must be TRUE):
  1. Running a load test and calling `engine.get_metrics()` returns an RPS value that reflects actual wall-clock elapsed time, not cumulative response time
  2. `MetricsDict` contains `p95_us` and `p99_us` fields with non-zero values after any load test that completes requests
  3. ConsoleReporter output includes P95 and P99 latency lines
  4. JSONReporter output includes `p95_us` and `p99_us` keys in the JSON payload
  5. HTMLReporter renders P95 and P99 latency in the generated HTML report

**Plans**: 2 plans

Plans:

- [x] 01-01-PLAN.md — Fix RPS formula in engine.c, add histogram to metrics_t, expose p95_us/p99_us via Python extension bridge
- [x] 01-02-PLAN.md — Surface p95_us/p99_us in MetricsDict TypedDict and all three reporters (Console, JSON, HTML)

### Phase 2: Dispatch & Rate Control

**Goal**: Load test execution uses the existing worker thread pool with correct per-worker rate pacing and reliable completion detection
**Depends on**: Phase 1
**Requirements**: DISP-01, DISP-02, DISP-03
**Success Criteria** (what must be TRUE):
  1. Starting a load test does not block the calling thread for the test duration (requests are dispatched to worker threads)
  2. Actual measured request rate matches the configured target rate within an acceptable margin (not distorted by integer-division pacing)
  3. Load test completion is detected without relying on a hardcoded `sleep(2)` — the engine signals done when all workers finish

**Plans**: TBD

Plans:

- [x] 02-01-PLAN.md — Rewrite engine_start_load_test: pre-fill queue, spawn per-test workers, pthread_join with hard timeout, _Atomic stop_flag, load_test_active guard
- [ ] 02-02-PLAN.md — Verify GIL release in python_extension.c and audit dispatch path for stdout output

### Phase 3: Thread Safety

**Goal**: All connection pools are safe to use from concurrent worker threads with no data races
**Depends on**: Phase 2
**Requirements**: SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05, SAFE-06
**Success Criteria** (what must be TRUE):
  1. TCP, UDP, MQTT, and database connection pools each have a dedicated `pthread_mutex_t` that guards all read/write access to their pool arrays and counts
  2. No calls to `gethostbyname` remain in tcp.c, mqtt.c, or udp.c — all DNS resolution uses `getaddrinfo`
  3. No calls to `rand()` remain in MQTT or database code — all random number generation uses `rand_r` with per-thread seed state
  4. The codebase compiles with thread sanitizer enabled and no data-race warnings appear on a concurrent connect/disconnect workload

**Plans**: 3 plans

Plans:

- [ ] 03-01-PLAN.md — Add pthread_mutex_t to TCP, UDP, MQTT, and DB pools (SAFE-01, SAFE-02, SAFE-03, SAFE-04)
- [ ] 03-02-PLAN.md — Replace gethostbyname with getaddrinfo and rand() with rand_r (SAFE-05, SAFE-06)
- [ ] 03-03-PLAN.md — Add make tsan target and tests/tsan_check.c; verify TSAN-clean concurrent workload

### Phase 4: Protocol I/O

**Goal**: TCP, UDP, and MQTT operations perform real network I/O rather than simulated or stub behavior
**Depends on**: Phase 3
**Requirements**: PROT-01, PROT-02, PROT-03, PROT-04, PROT-05, MQTT-01, MQTT-02
**Success Criteria** (what must be TRUE):
  1. `engine_tcp_send()` transmits data over the established socket and returns the actual byte count transferred
  2. `engine_tcp_receive()` reads from the socket and returns actual received bytes (not a simulated value)
  3. `engine_tcp_disconnect()` closes the file descriptor and removes the entry from the connection pool
  4. `engine_udp_receive()` reads a real datagram and returns the actual byte count; `engine_udp_close_endpoint()` closes the socket and removes the pool entry
  5. A TCP/MQTT connect attempt to a server that rejects the connection (bad CONNACK) is reported as a failure, not a success

**Plans**: 3 plans

Plans:

- [ ] 04-01-PLAN.md — Add tcp_lookup_by_fd() helper and replace engine_tcp_send/receive/disconnect stubs with real socket I/O
- [ ] 04-02-PLAN.md — Add udp_lookup_by_fd() helper and replace engine_udp_receive/close_endpoint stubs with real socket I/O
- [ ] 04-03-PLAN.md — Fix MQTT CONNACK 4-field validation, variable-length encoding in subscribe/unsubscribe, and union-safe protocol_data access

### Phase 5: Test Infrastructure

**Goal**: All correctness claims are covered by automated tests in the canonical location, and no stale test scripts remain at the project root
**Depends on**: Phase 4
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):
  1. `pytest tests/` runs without errors and includes a concurrent stress test that exercises simultaneous connect/disconnect across TCP, UDP, and MQTT pools
  2. A metric accuracy test in `tests/` verifies that reported RPS is within 10% of the actual wall-clock request rate
  3. A metric accuracy test in `tests/` verifies that P95/P99 values are correct against a known latency distribution
  4. A behavioral parity test in `tests/` confirms C engine and Python fallback return identical response dict shapes for HTTP requests
  5. No `test_*.py` files exist at the project root — all tests live under `tests/`

**Plans**: TBD

Plans:

- [ ] 05-01: Add concurrent stress tests and metric accuracy tests
- [ ] 05-02: Add behavioral parity test and migrate/delete root-level test scripts

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Metrics Correctness | 2/2 | Complete    | 2026-04-29 |
| 2. Dispatch & Rate Control | 2/2 | Complete    | 2026-04-29 |
| 3. Thread Safety | 3/3 | Complete    | 2026-05-01 |
| 4. Protocol I/O | 3/3 | Complete   | 2026-05-21 |
| 5. Test Infrastructure | 0/2 | Not started | - |
