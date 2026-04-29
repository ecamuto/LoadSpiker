---
phase: 01-metrics-correctness
plan: 01
subsystem: engine
tags: [c-extension, metrics, histogram, percentiles, rps, latency]

# Dependency graph
requires: []
provides:
  - metrics_t struct with 10000-bucket fixed-size histogram (O(1) insert)
  - Correct wall-clock RPS formula using gettimeofday elapsed time
  - P95 and P99 percentile computation from histogram in engine_get_metrics
  - Python MetricsDict TypedDict updated with p95_us and p99_us fields
  - get_metrics() dict exposes p95_us and p99_us keys from C extension
affects:
  - 01-02 (any further phase 1 plan using metrics)
  - All phases using engine metrics reporting

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Fixed-size histogram bucket array (O(1) insert, no dynamic allocation) for latency percentiles
    - Wall-clock elapsed time via gettimeofday for RPS accuracy across concurrent workers
    - Histogram-based percentile scan on read path (O(N) where N=10000 bucket count, called infrequently)

key-files:
  created: []
  modified:
    - src/engine.h
    - src/engine.c
    - src/python_extension.c
    - loadspiker/engine.py

key-decisions:
  - "Fixed-size histogram (HISTOGRAM_BUCKET_COUNT=10000, 1ms/bucket) chosen for O(1) insert and bounded memory"
  - "RPS computed from wall-clock elapsed time (gettimeofday) not cumulative response time to avoid worker thread inflation"
  - "Percentile computation happens on read path in engine_get_metrics, not on write path, to avoid locking overhead per request"

patterns-established:
  - "Histogram pattern: histogram_buckets[] in metrics_t, insert in update_metrics, scan in engine_get_metrics"

requirements-completed:
  - METR-01
  - METR-02
  - METR-03

# Metrics
duration: 3min
completed: 2026-04-29
---

# Phase 1 Plan 01: Metrics Correctness - Histogram and Wall-Clock RPS Summary

**Fixed-size 10000-bucket histogram in metrics_t enabling P95/P99 percentile computation, plus correct wall-clock RPS formula replacing cumulative response time division**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-04-29T00:13:13Z
- **Completed:** 2026-04-29T00:16:33Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Added HISTOGRAM_BUCKET_COUNT (10000, 1ms/bucket) to metrics_t with p95_us and p99_us fields
- Fixed the RPS formula from `successful_requests / (cumulative_response_time * workers)` to `total_requests / wall_clock_elapsed_seconds`
- Wired histogram inserts in update_metrics (called on every response) and percentile scan in engine_get_metrics
- Exposed p95_us and p99_us in the Python extension bridge and MetricsDict TypedDict

## Task Commits

Each task was committed atomically:

1. **Task 1: Add histogram to metrics_t and test_start_time to engine struct** - `11eed51` (feat)
2. **Task 2: Fix RPS formula and wire histogram inserts + percentile computation** - `c001ca3` (feat)
3. **Task 3: Expose p95_us and p99_us in the Python extension bridge** - `fb4d6f7` (feat)

## Files Created/Modified
- `src/engine.h` - Added HISTOGRAM_BUCKET_COUNT/HISTOGRAM_OVERFLOW_INDEX defines; extended metrics_t with histogram_buckets[10000], p95_us, p99_us
- `src/engine.c` - Added test_start_time to struct engine; record gettimeofday in engine_start_load_test; histogram insert in update_metrics; replaced engine_get_metrics body with wall-clock RPS + percentile computation
- `src/python_extension.c` - Added PyDict_SetItemString for p95_us and p99_us in LoadTestEngine_get_metrics
- `loadspiker/engine.py` - Added p95_us: int and p99_us: int fields to MetricsDict TypedDict

## Key Line Ranges Modified

- `src/engine.h` lines 144-152: metrics_t typedef replaced (lines 144-162 after change)
- `src/engine.c` line 51: struct engine gained test_start_time field
- `src/engine.c` lines 494-503: update_metrics gained histogram bucket insert
- `src/engine.c` lines 846-858: engine_get_metrics replaced with 50-line wall-clock + percentile implementation
- `src/engine.c` lines 871-872: engine_start_load_test gained gettimeofday call after engine_reset_metrics
- `src/python_extension.c` lines 182-183: two new PyDict_SetItemString calls after requests_per_second
- `loadspiker/engine.py` lines 51-52: p95_us and p99_us added to MetricsDict

## Decisions Made
- Used fixed-size histogram (10000 buckets, 1ms each) as decided in planning phase — O(1) insert, no dynamic allocation, covers 0-10s latency range
- Histogram insert placed in update_metrics (which is already mutex-protected) — no additional locking needed
- Percentile computation happens on read path (engine_get_metrics) not write path to avoid overhead per request
- engine_reset_metrics uses memset which already zeroes histogram and percentile fields — no additional change needed
- engine_create uses memset to zero the engine struct which zeroes test_start_time — no additional change needed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failures in tests/test_database.py, tests/test_udp.py, and other protocol test files (AttributeError: C extension Engine object missing database_connect, udp_* etc. methods). These are pre-existing failures not caused by or related to this plan's changes. Verified by stash-testing: identical failures occur on the previous commit. Logged as out-of-scope.
- Engine core tests (tests/test_engine_core.py) and performance assertion tests (tests/test_performance_assertions.py) all pass — 17+99=116 tests pass, 19 skipped, 0 regressions from this plan's changes.

## Build Verification Output
```
Build exit: 0  (0 compiler errors, all tasks)
MetricsDict has p95_us and p99_us: OK
p95_us in m: True, p99_us in m: True, requests_per_second in m: True
tests/test_engine_core.py: 17 passed, 19 skipped
tests/test_performance_assertions.py: 99 passed
```

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Metrics correctness foundation complete for plan 01-01
- histogram_buckets, p95_us, p99_us are now live in the C engine and surfaced in the Python API
- Any consumer of get_metrics() can now read p95_us and p99_us directly
- Existing RPS callers will now receive wall-clock accurate values instead of the inflated cumulative formula

---
*Phase: 01-metrics-correctness*
*Completed: 2026-04-29*
