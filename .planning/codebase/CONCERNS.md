# Codebase Concerns

**Analysis Date:** 2026-04-29

## Tech Debt

**WebSocket protocol is fully simulated:**
- Issue: All WebSocket methods use `usleep()` delays and return hardcoded strings like "WebSocket connection established (simulated)". No real TCP handshake or frame encoding occurs.
- Files: `src/protocols/websocket.c`
- Impact: WebSocket tests produce meaningless timing data. Response times reflect artificial delays (10ms connect, 1ms send, 5ms close) rather than actual network behavior.
- Fix approach: Implement actual RFC 6455 WebSocket handshake using libcurl's ws:// support or a dedicated WebSocket library.

**Database protocol is fully simulated:**
- Issue: `database_connect()` sets `connection_handle = (void*)1` as a placeholder and `database_execute_query()` calls `usleep((100 + rand() % 400) * 1000)` to simulate 100-500ms query time with hardcoded result sets.
- Files: `src/protocols/database.c`
- Impact: Database tests validate nothing real. No actual database driver (libmysql, libpq, mongoc) is linked or called. The engine.h comment still reads "stubs for now".
- Fix approach: Link real database client libraries and implement actual connection/query execution.

**TCP send/receive/disconnect in engine are unimplemented stubs:**
- Issue: `engine_tcp_send()`, `engine_tcp_receive()`, and `engine_tcp_disconnect()` all contain comment "for now, create a placeholder implementation", set `response->success = true` and `return 0` without doing any real work. The actual `tcp_send()`/`tcp_receive()` functions in `tcp.c` take a host+port pair but the engine wrapper receives a `socket_fd`.
- Files: `src/engine.c` lines 303-376
- Impact: When the C extension is used, TCP send/receive/disconnect operations always report success and zero bytes transferred, regardless of actual network state.
- Fix approach: Align the TCP API to pass connection key through the engine or look up the fd-to-host mapping.

**UDP receive/close in engine are unimplemented stubs:**
- Issue: `engine_udp_receive()` and `engine_udp_close_endpoint()` use the same placeholder pattern as TCP stubs — they set success=true and return 0 without calling into `udp.c`.
- Files: `src/engine.c` lines 415-463
- Impact: UDP receive always reports 0 bytes received; close never closes the socket.
- Fix approach: Same as TCP — reconcile the socket_fd vs. host:port abstraction gap.

**`engine_execute_request_generic`, `engine_execute_request_generic_sync`, `engine_start_load_test_generic` are declared but not implemented:**
- Issue: These three functions are declared in `src/engine.h` (lines 162-163) but have no implementation anywhere in the `.c` files.
- Files: `src/engine.h`
- Impact: Any caller of the generic multi-protocol API will get a linker error. The full multi-protocol request dispatch path is dead code.
- Fix approach: Implement or remove these declarations.

**`requests_per_second` metric calculation is incorrect:**
- Issue: In `engine_get_metrics()`, RPS is computed as `successful_requests / (total_response_time_us / 1_000_000 * num_workers)`. This divides by cumulative response time across all workers rather than actual elapsed wall time, producing systematically wrong values.
- Files: `src/engine.c` lines 853-854
- Impact: Reported RPS is unreliable and cannot be used for SLA assertions.
- Fix approach: Track test start wall time in `engine_t` and compute `RPS = total_requests / elapsed_seconds`.

**`engine_start_load_test` rate limiting is broken:**
- Issue: Line 881 does `usleep(1000000 / concurrent_users)` — integer division discards the result for `concurrent_users > 1000000`, and the formula assumes one thread is doing all the work sequentially instead of dispatching to worker threads.
- Files: `src/engine.c` lines 868-888
- Impact: Load test timing is inaccurate. The trailing `sleep(2)` on line 885 is a hardcoded magic number.
- Fix approach: Use async queue dispatch to workers and track actual throughput with proper wall-clock pacing.

**14 scattered test files at project root:**
- Issue: Files like `test_build.py`, `test_debug.py`, `test_c_ext_direct.py`, `test_data_driven.py`, etc. exist at the project root alongside the formal test suite in `tests/`.
- Files: `/Users/enzo/src/LoadSpiker/test_*.py` (14 files)
- Impact: Unclear which tests are canonical. `pytest` discovery may pick up both sets inconsistently.
- Fix approach: Migrate validated tests into `tests/` and delete duplicate or debug test files.

**Multiple compiled `.so` files with different names and dates:**
- Issue: The `loadspiker/` directory contains four `.so` files: `loadspiker_c.cpython-313-darwin.so`, `loadspiker.cpython-313-darwin.so`, `loadspiker.so`, and `_c_ext/loadspiker_c.so` and `_c_ext/loadspiker_engine.so`. The oldest files date to August 2025 and the newest to February 2026.
- Files: `loadspiker/loadspiker_c.cpython-313-darwin.so`, `loadspiker/loadspiker.cpython-313-darwin.so`, `loadspiker/loadspiker.so`, `loadspiker/_c_ext/loadspiker_c.so`, `loadspiker/_c_ext/loadspiker_engine.so`, `loadspiker.cpython-313-darwin.so` (root)
- Impact: Import resolution is fragile. `engine.py` tries `from . import loadspiker_c as c_module` and falls back, but stale `.so` files with old ABIs may be silently loaded instead of the current build.
- Fix approach: Clean up to a single canonical build artifact path; add `.so` to `.gitignore` or the build clean target.

**MQTT CONNACK is not validated:**
- Issue: After sending the CONNECT packet, `mqtt_connect()` reads 4 bytes but only checks `recv() < 0`. It never checks whether the CONNACK packet type byte is `0x20` or inspects the return code byte to detect broker-side authentication failure.
- Files: `src/protocols/mqtt.c` lines 325-336
- Impact: A rejected MQTT connection (wrong credentials, banned client ID) will be silently treated as successful.
- Fix approach: Validate `connack[0] == MQTT_CONNACK` and `connack[3] == 0x00` (success return code).

**MQTT subscribe packet remaining-length encoding assumes < 128 bytes:**
- Issue: `mqtt_create_subscribe_packet()` and `mqtt_create_unsubscribe_packet()` use a single-byte remaining-length field with comment "simplified - assumes < 128". MQTT's variable-length encoding requires multi-byte encoding for topics > 118 characters.
- Files: `src/protocols/mqtt.c` lines 433-435, 531-533
- Impact: MQTT subscribe/unsubscribe operations silently fail for topic names longer than approximately 118 bytes.
- Fix approach: Use the proper multi-byte continuation-bit encoding loop (same as used in `mqtt_create_connect_packet`).

**`gethostbyname` used in three protocol files:**
- Issue: `tcp.c`, `mqtt.c`, and `udp.c` all call `gethostbyname()`, which is deprecated (POSIX 2008), not thread-safe, and IPv6-unaware.
- Files: `src/protocols/tcp.c:127`, `src/protocols/mqtt.c:282`, `src/protocols/udp.c:187`
- Impact: Race conditions possible in multi-threaded load tests. IPv6 targets silently fail.
- Fix approach: Replace with `getaddrinfo()` which is thread-safe and protocol-agnostic.

**TCP/UDP/MQTT/Database connection pools have no mutex protection:**
- Issue: The static global arrays `tcp_connections[]`, `udp_endpoints[]`, `mqtt_connections[]`, and `db_connections[]` are accessed and mutated (including the shared `_count` integers) without any mutex. Only `ws_connections[]` has a `ws_connections_mutex`.
- Files: `src/protocols/tcp.c` lines 15-17, `src/protocols/udp.c` lines 16-17, `src/protocols/mqtt.c` lines 15-16, `src/protocols/database.c` lines 10-11
- Impact: Concurrent workers calling connect/disconnect on different hosts will cause data races. The `_count++` operation is not atomic. Under load, this can corrupt the pool arrays.
- Fix approach: Add a per-pool `pthread_mutex_t` (same pattern as `ws_connections_mutex`).

**`rand()` called without thread safety in MQTT and database code:**
- Issue: `mqtt_parse_url()` uses `rand()` to generate client IDs. `database_execute_query()` uses `rand()` for simulated delay. Both are called from worker threads without locking.
- Files: `src/protocols/mqtt.c` lines 41, 60, 74; `src/protocols/database.c` line 245
- Impact: `rand()` is not thread-safe on some platforms and can return duplicate values under concurrent calls, causing MQTT client ID collisions.
- Fix approach: Use `rand_r()` with per-thread seed state, or `arc4random()` on Darwin.

**Python fallback MQTT methods are no-ops:**
- Issue: `_PythonEngine.mqtt_connect/publish/subscribe/unsubscribe/disconnect` all simulate success instantly without any real network I/O, returning immediately with fabricated response dicts. They don't use paho-mqtt or any real MQTT library.
- Files: `loadspiker/engine.py` lines 796-997
- Impact: Tests using the Python fallback path get silent false-positive MQTT results.
- Fix approach: Implement using `paho-mqtt` or document that Python fallback does not support MQTT.

**`__init__.py` imports `from .assertions import *` twice:**
- Issue: Lines 17 and 84 in `loadspiker/__init__.py` both perform `from .assertions import *`.
- Files: `loadspiker/__init__.py` lines 17, 84
- Impact: Minor redundancy; raises risk if `assertions.py` has module-level side effects.
- Fix approach: Remove the duplicate import.

## Security Considerations

**Database connection strings contain plaintext passwords in connection pool keys:**
- Risk: `db_connections[i].connection_string` stores the full connection string (e.g., `mysql://user:password@host/db`) as an 1024-byte field. This string is the lookup key and is retained in memory for the process lifetime.
- Files: `src/protocols/database.c` lines 128-131
- Current mitigation: MQTT intentionally zeroes the password field after connect. Database does not.
- Recommendations: Store a hash of the connection string as the lookup key and strip credentials from the stored value.

**Python fallback sends basic auth credentials encoded but not encrypted:**
- Risk: `BasicAuthenticationFlow` in `loadspiker/authentication.py` encodes credentials with `base64.b64encode` and stores them in-session. Base64 is not encryption. If the session dict is logged or serialized, credentials are trivially recoverable.
- Files: `loadspiker/authentication.py` lines 76-91
- Current mitigation: None — credentials are stored as-is in the session store dict.
- Recommendations: Scrub credentials from memory after use; do not persist in session stores.

## Performance Bottlenecks

**Simulated delays in WebSocket inflate all response time measurements:**
- Problem: WebSocket connect always sleeps 10ms, send sleeps 1ms, and close sleeps 5ms regardless of actual network conditions.
- Files: `src/protocols/websocket.c` lines 86, 121, 155
- Cause: Placeholder implementation.
- Improvement path: Remove artificial delays when real network I/O is implemented.

**`engine_start_load_test` is blocking (GIL-holding during test):**
- Problem: The Python extension releases the GIL with `Py_BEGIN_ALLOW_THREADS` around `engine_start_load_test`, but the function itself uses `usleep` and `sleep` on the calling thread rather than dispatching work to worker threads.
- Files: `src/python_extension.c` lines 162-164`, `src/engine.c` lines 868-888`
- Cause: The load test loop runs synchronously in the main thread, not using the worker thread pool.
- Improvement path: Convert to a proper dispatch model that submits requests to the queue and tracks completion via a barrier.

**O(N) linear scan on all connection pool lookups:**
- Problem: `tcp_find_connection()`, `udp_find_endpoint()`, `mqtt_find_connection()`, `find_connection()` (database) all do sequential array scans for every operation.
- Files: `src/protocols/tcp.c:58`, `src/protocols/udp.c:58`, `src/protocols/mqtt.c:81`, `src/protocols/database.c:114`
- Cause: Simple array-based pools without hashing.
- Improvement path: Use a hash map keyed on host:port or connection string for O(1) lookups.

## Fragile Areas

**C extension vs. Python fallback behavioral divergence:**
- Files: `loadspiker/engine.py` (entire `_PythonEngine` class)
- Why fragile: The C engine and Python fallback return different response dict shapes in some cases (e.g., Python fallback for WebSocket returns `{'status': 501}` while C returns `{'status_code': ...}`). Tests that pass with one may silently fail with the other.
- Safe modification: Always normalize response shapes at the Python wrapper layer before returning.
- Test coverage: No tests verify behavioral parity between C and Python fallback paths.

**Import chain has triple-fallback layers with silent swallowing:**
- Files: `loadspiker/__init__.py`
- Why fragile: Each module (scenarios, assertions, data_sources, reporters, utils) has a try/except chain that creates stub classes on failure. Silent import failures mean missing features appear to work until runtime.
- Safe modification: Add a `loadspiker.check_installation()` function that explicitly reports which components loaded successfully.
- Test coverage: `test_build.py` at root partially tests this but is not part of the canonical suite.

**TCP connection pool count is never decremented:**
- Files: `src/protocols/tcp.c` lines 67-81
- Why fragile: `tcp_create_connection()` increments `tcp_connection_count` but `tcp_disconnect()` and `tcp_cleanup_all()` only close the socket and set `is_connected=false`; they never decrement the count or compact the array. After 100 disconnect/reconnect cycles to different hosts, the pool is permanently full.
- Safe modification: Implement slot reuse (set socket_fd=-1 to mark slot as available).
- Test coverage: No test exercises connection pool exhaustion.

## Missing Critical Features

**No actual WebSocket network I/O:**
- Problem: The websocket.c implementation simulates all operations with delays. There is no TLS upgrade, no HTTP upgrade handshake, no frame encoding/decoding.
- Blocks: Any meaningful WebSocket load testing.

**Database protocol has no real drivers:**
- Problem: MySQL, PostgreSQL, and MongoDB "connections" immediately succeed without contacting any server. Query results are hardcoded strings.
- Blocks: Database load testing, connection pooling validation, query performance measurement.

**No percentile tracking (P95/P99):**
- Problem: The `metrics_t` struct only tracks min, max, and total response time. There is no histogram or sorted sample buffer for computing percentile values.
- Files: `src/engine.h` lines 144-152
- Blocks: SLA assertions based on P95/P99 response time.

**No distributed/multi-process test coordination:**
- Problem: Each `Engine` instance is a single-process, single-machine entity with no coordination protocol.
- Blocks: Testing at scale beyond a single machine.

## Test Coverage Gaps

**Protocol stub behavior not tested:**
- What's not tested: No test verifies that WebSocket/Database responses accurately reflect the stub nature (simulated=true indicator). Tests in `test_engine_core.py` assert `success=True` which the stubs always return.
- Files: `tests/test_engine_core.py` lines 190-211
- Risk: Stubs could be replaced with broken real implementations and existing tests would still pass.
- Priority: Medium

**Thread safety of connection pools not tested:**
- What's not tested: No concurrent stress test exercises `tcp_connect`/`tcp_disconnect` simultaneously from multiple threads to expose the missing mutex on the static pool arrays.
- Files: `src/protocols/tcp.c`, `src/protocols/mqtt.c`, `src/protocols/udp.c`, `src/protocols/database.c`
- Risk: Race conditions would only manifest under concurrent load, the primary use case.
- Priority: High

**C/Python fallback response parity not tested:**
- What's not tested: No test creates an engine with `_c_extension_available=False` forced and verifies output matches C extension output shape.
- Files: `loadspiker/engine.py`
- Risk: Python fallback returns `status` (integer) in some cases instead of `status_code`.
- Priority: Medium

**Connection pool exhaustion not tested:**
- What's not tested: Creating more than 100 TCP connections, 50 MQTT connections, or 100 database connections to trigger the "Too many connections" error path.
- Files: `src/protocols/tcp.c:68`, `src/protocols/mqtt.c:93`, `src/protocols/database.c:123`
- Risk: Pool exhaustion silently drops connections in production load tests.
- Priority: High

---

*Concerns audit: 2026-04-29*
