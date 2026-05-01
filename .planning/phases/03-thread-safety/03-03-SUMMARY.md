---
phase: 03-thread-safety
plan: "03"
subsystem: testing
tags: [tsan, thread-sanitizer, makefile, pthread, c, protocol-pool]

# Dependency graph
requires:
  - phase: 03-01
    provides: per-pool mutexes on tcp/udp/mqtt/database connection pools
  - phase: 03-02
    provides: getaddrinfo replacing gethostbyname, rand_r replacing rand()
provides:
  - make tsan target compiling all engine+protocol sources with -fsanitize=thread
  - tests/tsan_check.c stress binary (32 threads across 4 protocol pools, 20 iterations each)
  - CI-reproducible TSAN verification that exits 0 with zero DATA RACE warnings
affects:
  - phase-04 (any future phases calling tcp/udp protocol functions will benefit from overflow fix)

# Tech tracking
tech-stack:
  added: [ThreadSanitizer (-fsanitize=thread)]
  patterns: [separate *_tsan.o compile rules for sanitizer builds, protocol_data union accessed via typed union member not raw char[] cast]

key-files:
  created: [tests/tsan_check.c]
  modified: [Makefile, src/protocols/tcp.c, src/protocols/udp.c]

key-decisions:
  - "03-03: Use separate *_tsan.o object files for TSAN build to avoid rebuilding production .o files"
  - "03-03: protocol_data accessed via &response->protocol_data.tcp/udp (typed union members) not (tcp_data_t*)protocol_data.protocol_data to avoid out-of-bounds writes"
  - "03-03: tsan_check.c uses unique MQTT client IDs per thread (tsan_mqtt_N) to avoid all threads contending for the same slot"

patterns-established:
  - "Always use engine.h typed union member (&response->protocol_data.tcp, .udp, .mqtt) instead of raw char[] cast when writing protocol_data"

requirements-completed: [SAFE-01, SAFE-02, SAFE-03, SAFE-04, SAFE-05, SAFE-06]

# Metrics
duration: 35min
completed: 2026-05-01
---

# Phase 03 Plan 03: TSAN Verification Summary

**make tsan target running 32-thread connect/disconnect stress test against all four protocol pools, exits 0 with zero ThreadSanitizer DATA RACE warnings after fixing out-of-bounds tcp_data_t/udp_data_t union writes**

## Performance

- **Duration:** 35 min
- **Started:** 2026-05-01T08:13:00Z
- **Completed:** 2026-05-01T08:48:00Z
- **Tasks:** 2
- **Files modified:** 4 (tests/tsan_check.c created, Makefile, src/protocols/tcp.c, src/protocols/udp.c)

## Accomplishments

- Wrote `tests/tsan_check.c`: 32 threads (8 per protocol) each doing 20 connect/disconnect iterations concurrently across TCP, UDP, MQTT, and database pools
- Added `make tsan` Makefile target with separate `*_tsan.o` compile rules using `-fsanitize=thread -g -O1`; listed in `.PHONY` and `make help`
- Discovered and fixed critical buffer overflow in tcp.c and udp.c: the `tcp_data_t`/`udp_data_t` local structs (both contain `received_data[MAX_BODY_LENGTH]` = 65536 bytes) were being written via a cast to `protocol_data.protocol_data` (char[MAX_PROTOCOL_DATA] = 32768), with `connection_established`, `remote_host`, etc. fields landing 0–264 bytes past the union end, causing SIGABRT on exit

## Task Commits

Each task was committed atomically:

1. **Task 1: Write tests/tsan_check.c stress binary** - `50e58f0` (feat)
2. **Task 2: Add make tsan target and verify clean run** - `de6e01b` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `tests/tsan_check.c` - 32-thread TSAN stress binary exercising all four protocol pools
- `Makefile` - Added tsan target with TSAN_FLAGS, per-file *_tsan.o rules, TSAN_BIN link rule, help entry
- `src/protocols/tcp.c` - Fixed three `(tcp_data_t*)protocol_data.protocol_data` casts to `&response->protocol_data.tcp`
- `src/protocols/udp.c` - Fixed three `(udp_data_t*)protocol_data.protocol_data` casts to `&response->protocol_data.udp`

## Decisions Made

- Used separate `*_tsan.o` object file names for TSAN build (e.g., `engine_tsan.o`) to avoid overwriting production `.o` files and breaking incremental `make build`
- Set `TSAN_FLAGS = -fsanitize=thread -g -O1 -Wall -Wextra -pthread` (O1 preserves enough structure for TSAN while keeping compile time low)
- Unique MQTT client IDs per thread (`tsan_mqtt_0` through `tsan_mqtt_7`) prevent 8 threads competing for identical pool slots; TCP/UDP use the same host:port since pool-level races are exactly what TSAN should test

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed tcp.c out-of-bounds write via tcp_data_t cast**
- **Found during:** Task 2 (make tsan run — binary crashed with SIGABRT exit 133 after all output)
- **Issue:** `tcp_data_t` is 65552 bytes; `response_t.protocol_data` union is 65544 bytes. Fields `connection_established` (offset 65544) and `connection_time_us` (offset 65548) are 8 bytes past the union end. Writing them via `(tcp_data_t*)response->protocol_data.protocol_data` corrupts the stack frame on return.
- **Fix:** Replaced all 3 `(tcp_data_t*)response->protocol_data.protocol_data` casts with `&response->protocol_data.tcp` (typed `tcp_response_data_t*`); dropped `connection_established` and `connection_time_us` writes (already conveyed via `response->success`)
- **Files modified:** `src/protocols/tcp.c`
- **Verification:** Binary exits 0, `make build` still passes
- **Committed in:** `de6e01b` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed udp.c out-of-bounds write via udp_data_t cast**
- **Found during:** Task 2 (same crash investigation — UDP alone triggered SIGABRT)
- **Issue:** `udp_data_t` is 65808 bytes; `response_t.protocol_data` union is 65544 bytes. `remote_host` starts at offset 65544 (exactly at union end), `remote_port` at 65800, `datagram_sent` at 65804 — all 264 bytes out of bounds. `strncpy(udp_data->remote_host, host, 255)` overwrites 255 bytes past the union, corrupting adjacent stack memory.
- **Fix:** Replaced all 3 `(udp_data_t*)response->protocol_data.protocol_data` casts with `&response->protocol_data.udp` (typed `udp_response_data_t*`); mapped fields to `sender_address`/`sender_port` which are the engine.h equivalents
- **Files modified:** `src/protocols/udp.c`
- **Verification:** UDP binary exits 0, full 32-thread stress test exits 0, no TSAN warnings
- **Committed in:** `de6e01b` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes were required for the binary to run at all. The overflows preexisted from the original protocol implementation; this plan exposed them by calling the protocol functions from a standalone C binary. No scope creep.

## Issues Encountered

- `make tsan` initially produced "Trace/BPT trap: 5" (SIGTRAP exit 133). Isolated to UDP alone crashing via a series of minimal test binaries. Root cause: `udp_data_t.received_data[MAX_BODY_LENGTH]` (65536 bytes at offset 8) pushes trailing fields past the 65544-byte union boundary. Same issue found in `tcp_data_t`. Both fixed by switching to the engine.h typed union members.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 03 (Thread Safety) is complete: per-pool mutexes (03-01), getaddrinfo + rand_r (03-02), TSAN clean pass (03-03)
- All four protocol pools (TCP, UDP, MQTT, DB) are now race-free under TSAN with 32 concurrent threads
- `make tsan` is CI-runnable and will catch regressions if future changes re-introduce races

## Self-Check: PASSED

- tests/tsan_check.c: FOUND
- obj/tsan_check: FOUND
- 03-03-SUMMARY.md: FOUND
- commit 50e58f0 (Task 1): FOUND
- commit de6e01b (Task 2): FOUND

---
*Phase: 03-thread-safety*
*Completed: 2026-05-01*
