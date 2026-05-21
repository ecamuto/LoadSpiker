---
phase: 04-protocol-i-o
plan: "03"
subsystem: protocol
tags: [mqtt, c, socket, binary-protocol, connection-pool]

# Dependency graph
requires:
  - phase: 03-thread-safety
    provides: union-safe protocol_data access pattern via typed members (&response->protocol_data.tcp/.udp)
provides:
  - Full CONNACK validation in mqtt_connect() (all four packet fields: 0x20/0x02/ack_flags/return_code)
  - Pool entry cleanup on bad CONNACK via new_entry flag
  - Multi-byte variable-length remaining-length encoding in subscribe/unsubscribe packets
  - Union-safe mqtt_data access via &response->protocol_data.mqtt in all three sites
affects: [engine-mqtt-bridge, any caller of mqtt_connect/publish/subscribe]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "new_entry flag: track whether pool slot was freshly allocated vs reused, to conditionally undo on failure"
    - "MQTT CONNACK validation: check all four bytes before marking connection established"
    - "MQTT variable-length encoding: do/while loop with encoded_byte = rl % 128, continuation bit at 128"

key-files:
  created: []
  modified:
    - src/protocols/mqtt.c

key-decisions:
  - "04-03: new_entry flag distinguishes freshly-allocated pool slots from reused disconnected slots — only decrement mqtt_connection_count on CONNACK failure when new_entry is true"
  - "04-03: CONNACK validation checks all four required MQTT 3.1.1 §3.2 fields before marking is_connected=true; broker rejection (return code != 0x00) produces descriptive error with return code hex value"
  - "04-03: mqtt_data accessed via &response->protocol_data.mqtt (mqtt_response_data_t*) not raw (mqtt_data_t*)protocol_data.protocol_data cast — same fix applied to all three sites: connect, publish, subscribe"
  - "04-03: multi-byte remaining-length loop uses local int rl to preserve remaining_length variable; identical do/while pattern as mqtt_create_connect_packet and mqtt_create_publish_packet"

patterns-established:
  - "Pool cleanup on failure: use entry flag to track newly-allocated slots; undo with count-- + memset on failure"
  - "MQTT binary protocol validation: cast to unsigned char before comparing packet bytes to avoid sign-extension"

requirements-completed: [MQTT-01, MQTT-02]

# Metrics
duration: 2min
completed: 2026-05-21
---

# Phase 04 Plan 03: MQTT Correctness Fixes Summary

**Full CONNACK validation (all four MQTT 3.1.1 §3.2 fields), multi-byte variable-length remaining-length encoding for subscribe/unsubscribe, and union-safe protocol_data access via typed member in mqtt.c**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-21T10:55:57Z
- **Completed:** 2026-05-21T10:57:46Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments

- mqtt_connect() now validates all four CONNACK bytes (0x20 header, 0x02 remaining length, 0x00 ack flags, 0x00 return code) before marking connection established; broker rejection produces a descriptive error including the return code
- Pool entry cleanup on CONNACK failure uses a new_entry flag to distinguish freshly-allocated slots from reused disconnected slots — only undoes the allocation when the slot was newly created
- mqtt_create_subscribe_packet() and mqtt_create_unsubscribe_packet() use the correct do/while multi-byte remaining-length loop, fixing silent packet corruption for topic names >= 128 bytes
- All three mqtt_data_t* raw cast sites replaced with typed union member &response->protocol_data.mqtt (mqtt_response_data_t*)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix CONNACK validation and pool cleanup on failure in mqtt_connect()** - `f5684c9` (fix)
2. **Task 2: Fix variable-length encoding in subscribe/unsubscribe packets and union access in mqtt.c** - `381cdc2` (fix)

**Plan metadata:** `[see final commit]` (docs: complete plan)

## Files Created/Modified

- `src/protocols/mqtt.c` - Full CONNACK validation with new_entry pool cleanup, multi-byte remaining-length in subscribe/unsubscribe, union-safe mqtt_data access in connect/publish/subscribe

## Decisions Made

- new_entry flag approach chosen over index-tracking: simpler, correct, and avoids the ambiguity of whether a found-but-disconnected slot should be removed on failure (it should not, since it predates this call)
- `(unsigned char)` casts used when comparing connack[] bytes to 0x20/0x02 to avoid sign-extension on platforms where char is signed
- Local variable `rl` used in the encoding loop to avoid mutating `remaining_length` for clarity even though the variable is not used after the loop

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- mqtt.c correctness bugs resolved; MQTT protocol I/O is now correct for all packet types
- Engine bridge for MQTT (analogous to TCP/UDP bridges in 04-01/04-02) can proceed with clean foundation
- No blockers

---
*Phase: 04-protocol-i-o*
*Completed: 2026-05-21*
