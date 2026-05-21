---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: in_progress
last_updated: "2026-05-21T10:49:00Z"
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 10
  completed_plans: 9
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-29)

**Core value:** Correct, trustworthy metrics across multiple protocols from a single process
**Current focus:** Phase 4 - Protocol I/O

## Current Position

Phase: 4 of 5 (Protocol I/O) — IN PROGRESS
Plan: 3 of 3 in current phase (complete)
Status: 04-03 complete — MQTT correctness bugs fixed: full CONNACK validation, multi-byte remaining-length in subscribe/unsubscribe, union-safe protocol_data.mqtt access
Last activity: 2026-05-21 — Completed 04-03: mqtt_connect() validates all four CONNACK fields; subscribe/unsubscribe use do/while variable-length encoding; all three mqtt_data casts replaced with typed union member

Progress: [█████████░] 90%

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 03 P01 | 286 | 2 tasks | 4 files |
| Phase 03-thread-safety P02 | 3 | 2 tasks | 4 files |
| Phase 03-thread-safety P03 | 35 | 2 tasks | 4 files |
| Phase 04-protocol-i-o P01 | 3 | 2 tasks | 3 files |
| Phase 04-protocol-i-o P03 | 2 | 2 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- All phases: Fix engine correctness before adding features — metrics are untrustworthy today
- Phase 1: Use fixed-size histogram bucket array for percentiles (O(1) insert, no dynamic allocation)
- Phase 3: Add per-pool mutexes matching ws_connections_mutex pattern; replace gethostbyname with getaddrinfo
- 01-01: RPS computed from wall-clock elapsed time (gettimeofday) not cumulative response time to avoid worker thread inflation
- 01-01: Percentile computation happens on read path in engine_get_metrics, not write path, to avoid locking overhead per request
- 01-02: JSONReporter required no code change — stores full metrics dict by reference so p95_us/p99_us pass through automatically
- 01-02: Display unit for P95/P99 is milliseconds (divide by 1000), consistent with existing Min/Max lines
- 02-01: Per-test threads created/destroyed each run (not reused from persistent pool) — avoids complex state reset
- 02-01: stop_flag uses _Atomic int with atomic_store/atomic_load, correct on ARM64/x86 without extra mutex
- 02-01: Hard timeout is duration_seconds + 5s grace period so in-flight requests can complete
- 02-01: Queue resized via realloc when num_requests exceeds current capacity — no fixed upper bound
- 02-02: GIL-release block correct — requests is plain C heap pointer, self->engine is engine_t*, safe without GIL
- 02-02: engine.c dispatch path has zero stdout output — grep returned empty for printf/fprintf/puts/fputs
- 02-02: concurrent_users is thread-count only — 3 occurrences: function signature, input guard, actual_workers assignment
- 03-01: Inlined pool search inside compound functions (connect, send, etc.) to avoid double-lock deadlock when helpers now hold their own mutex
- 03-01: Full-operation locking per prior decision — socket syscalls stay inside lock for correctness
- 03-01: One-time pool-full stderr warnings per pool (tcp_pool_warned, udp_pool_warned, mqtt_pool_warned, db_pool_warned)
- [Phase 03]: Inlined pool search inside compound functions to avoid double-lock deadlock when helpers now acquire their own mutex
- [Phase 03]: One-time pool-full stderr warnings per pool (tcp/udp/mqtt/db_pool_warned) to avoid log spam
- [Phase 03-thread-safety]: 03-02: getaddrinfo replaces gethostbyname in tcp/udp/mqtt — no global DNS buffer across concurrent threads
- [Phase 03-thread-safety]: 03-02: rand_r with __thread seed from pthread_self() replaces rand() in mqtt/database — per-thread RNG, no global seed lock
- [Phase 03-thread-safety]: 03-03: Use separate *_tsan.o object files for TSAN build to avoid overwriting production .o files
- [Phase 03-thread-safety]: 03-03: protocol_data accessed via typed union members (&response->protocol_data.tcp/.udp) not raw char[] cast — tcp_data_t/udp_data_t both exceed union size causing out-of-bounds writes
- [Phase 04-protocol-i-o]: 04-01: tcp_lookup_by_fd() in tcp.c/tcp.h reverse-maps socket_fd to host+port; engine bridge delegates entirely to tcp.c pool functions
- [Phase 04-protocol-i-o]: 04-01: tcp_disconnect uses shutdown(SHUT_RDWR)+close() for graceful teardown; tcp_receive select() timeout raised from 1s to 5s per CONTEXT.md
- [Phase 04-protocol-i-o]: 04-01: (void)param casts suppress intentionally-unused API params in engine bridge without altering engine.h public signatures
- [Phase 04-protocol-i-o]: 04-02: udp_lookup_by_fd() in udp.c/udp.h reverse-maps socket_fd to host+port; engine bridge delegates entirely to udp.c pool functions
- [Phase 04-protocol-i-o]: 04-02: udp_receive() select() timeout raised from 1s to 5s per CONTEXT.md; engine returns 400 when socket_fd not in pool
- [Phase 04-protocol-i-o]: 04-03: new_entry flag distinguishes freshly-allocated pool slots from reused disconnected slots — only decrement mqtt_connection_count on CONNACK failure when new_entry is true
- [Phase 04-protocol-i-o]: 04-03: CONNACK validation checks all four MQTT 3.1.1 §3.2 fields (0x20/0x02/0x00/0x00) before marking is_connected=true; broker rejection produces descriptive error with return code hex
- [Phase 04-protocol-i-o]: 04-03: mqtt_data accessed via &response->protocol_data.mqtt (mqtt_response_data_t*) not raw cast — same union-safe pattern as tcp/udp from Phase 03

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-05-21
Stopped at: Completed 04-03-PLAN.md — MQTT correctness bugs fixed; CONNACK validation, multi-byte remaining-length, union-safe protocol_data.mqtt access
Resume file: None
