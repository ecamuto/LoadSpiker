---
phase: 04-protocol-i-o
plan: "04"
subsystem: api
tags: [tcp, socket, partial-send, retry, c]

# Dependency graph
requires:
  - phase: 04-protocol-i-o
    provides: tcp_send() single-call baseline established in 04-01
provides:
  - partial-send retry loop in tcp_send() — loops while total_sent < data_len
  - accurate engine_tcp_send() comment describing retry behavior
affects: [any caller of tcp_send() that relied on single-call send semantics]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - partial-send retry: accumulate total_sent, advance pointer by total_sent each iteration, report bytes delivered on error

key-files:
  created: []
  modified:
    - src/protocols/tcp.c
    - src/engine.c

key-decisions:
  - "tcp_send() retry loop uses total_sent accumulator per CONTEXT.md decision — loops while total_sent < data_len advancing data pointer each iteration"
  - "Error path includes total_sent in message so callers know how many bytes were delivered before failure"
  - "engine_tcp_send() comment updated to 'retries until all bytes are delivered or an error occurs' for accuracy"

patterns-established:
  - "Partial-send retry: while(total_sent < data_len) { bytes_sent = send(fd, data+total_sent, data_len-total_sent, 0); total_sent += bytes_sent; }"

requirements-completed: [PROT-01]

# Metrics
duration: 5min
completed: 2026-05-21
---

# Phase 04 Plan 04: TCP Partial-Send Retry Summary

**tcp_send() partial-send retry loop with total_sent accumulator, replacing the silent-truncation single-call pattern**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-21T11:47:39Z
- **Completed:** 2026-05-21T11:52:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Replaced single `send()` call in `tcp_send()` with a `while(total_sent < data_len)` retry loop that advances the data pointer each iteration
- Error path now includes bytes already delivered (`total_sent`) in the error message, giving callers accurate partial-delivery information
- `tcp_data->bytes_sent` and `response->body` reflect `total_sent` (full delivery count) rather than a single `send()` return value
- Updated `engine_tcp_send()` comment from the inaccurate "handles partial-send retry" (when it didn't) to "retries until all bytes are delivered or an error occurs" (now true)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add partial-send retry loop to tcp_send() and fix engine.c comment** - `230e980` (fix)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified

- `src/protocols/tcp.c` — replaced single send() call with while(total_sent < data_len) retry loop
- `src/engine.c` — updated engine_tcp_send() comment to accurately describe retry behavior

## Decisions Made

- tcp_send() retry loop accumulates `total_sent`, advances the data pointer by `total_sent` each iteration, and passes `data_len - total_sent` as the send length — matches CONTEXT.md decision
- The `int send_error = 0;` line from the plan snippet was omitted (it was unused and the plan itself flagged it as removable)
- Error message format: "Send failed after %zu bytes: %s" — includes total_sent so callers know partial delivery count

## Deviations from Plan

None — plan executed exactly as written. The `send_error` variable was explicitly noted as removable in the plan and was never included.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- TCP send is now correct for large payloads under high concurrency — no silent truncation
- All four protocol I/O plans (TCP, UDP, MQTT, TCP partial-send) are complete
- Phase 04 is fully complete; ready to advance to Phase 05

---
*Phase: 04-protocol-i-o*
*Completed: 2026-05-21*
