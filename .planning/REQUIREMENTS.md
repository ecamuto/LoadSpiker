# Requirements: LoadSpiker

**Defined:** 2026-04-29
**Core Value:** Correct, trustworthy metrics across multiple protocols from a single process

## v1 Requirements

### Metrics

- [x] **METR-01**: Engine reports RPS based on actual wall-clock elapsed time, not cumulative response time
- [x] **METR-02**: `metrics_t` struct tracks a response-time histogram sufficient to compute P95 and P99
- [x] **METR-03**: `MetricsDict` returned from `engine.get_metrics()` includes `p95_us` and `p99_us` fields
- [x] **METR-04**: ConsoleReporter, JSONReporter, and HTMLReporter display P95 and P99 latency

### Dispatch

- [x] **DISP-01**: `engine_start_load_test` dispatches requests to the existing worker thread pool instead of running a usleep loop on the calling thread
- [x] **DISP-02**: Rate limiting uses correct per-worker pacing (not `usleep(1000000 / concurrent_users)` integer division)
- [x] **DISP-03**: Load test completion is signaled via a proper barrier/counter, not a hardcoded `sleep(2)`

### Thread Safety

- [x] **SAFE-01**: TCP connection pool (`tcp_connections[]`, `tcp_connection_count`) is protected by a `pthread_mutex_t`
- [x] **SAFE-02**: UDP endpoint pool (`udp_endpoints[]`, `udp_endpoint_count`) is protected by a `pthread_mutex_t`
- [x] **SAFE-03**: MQTT connection pool (`mqtt_connections[]`, `mqtt_connection_count`) is protected by a `pthread_mutex_t`
- [x] **SAFE-04**: Database connection pool (`db_connections[]`, `db_connection_count`) is protected by a `pthread_mutex_t`
- [x] **SAFE-05**: `gethostbyname` replaced with `getaddrinfo` in `tcp.c`, `mqtt.c`, and `udp.c`
- [x] **SAFE-06**: `rand()` calls in MQTT and database code replaced with thread-safe `rand_r()` with per-thread seed state

### Protocol Correctness (TCP/UDP)

- [x] **PROT-01**: `engine_tcp_send()` sends data over the established socket and returns actual bytes transferred
- [x] **PROT-02**: `engine_tcp_receive()` reads from the established socket and returns actual bytes received
- [x] **PROT-03**: `engine_tcp_disconnect()` closes the socket and removes it from the connection pool
- [x] **PROT-04**: `engine_udp_receive()` reads a datagram from the socket and returns actual bytes received
- [x] **PROT-05**: `engine_udp_close_endpoint()` closes the socket and removes it from the endpoint pool

### Protocol Correctness (MQTT)

- [ ] **MQTT-01**: `mqtt_connect()` validates the CONNACK packet type byte (`0x20`) and return code (`0x00`) before reporting success
- [ ] **MQTT-02**: `mqtt_create_subscribe_packet()` and `mqtt_create_unsubscribe_packet()` use correct multi-byte variable-length remaining-length encoding for topic names ≥ 128 bytes

### Test Infrastructure

- [ ] **TEST-01**: Concurrent stress test verifies no data races when N threads simultaneously connect/disconnect TCP, UDP, MQTT pools
- [ ] **TEST-02**: Metric accuracy test verifies reported RPS is within 10% of actual wall-clock request rate
- [ ] **TEST-03**: Metric accuracy test verifies P95/P99 values are computed correctly against a known latency distribution
- [ ] **TEST-04**: Behavioral parity test verifies C engine and Python fallback return identical response dict shapes for HTTP requests
- [ ] **TEST-05**: Root-level canonical `test_*.py` files migrated into `tests/` and duplicate/debug scripts deleted

## v2 Requirements

### Protocol Completion

- **WS-01**: Real WebSocket network I/O — TCP + TLS + HTTP upgrade handshake + RFC 6455 frame encoding/decoding
- **DB-01**: Real MySQL load testing via libmysql
- **DB-02**: Real PostgreSQL load testing via libpq
- **DB-03**: Real MongoDB load testing via mongoc

### Scale

- **SCALE-01**: Distributed test coordination across multiple machines
- **SCALE-02**: Real-time metrics streaming to Grafana / external dashboard

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real WebSocket (RFC 6455) | High complexity; not the primary workload for this milestone |
| Database drivers (libmysql/libpq/mongoc) | DB load testing is not the current use case |
| Distributed / multi-machine coordination | Single-machine scope sufficient for target workloads |
| GUI or real-time web dashboard | Console/JSON/HTML reporters sufficient |
| Windows support | POSIX APIs required; macOS and Linux only |

## Traceability

| Requirement | Phase | Status |
| ----------- | ----- | ------ |
| METR-01 | Phase 1 - Metrics Correctness | Complete (01-01) |
| METR-02 | Phase 1 - Metrics Correctness | Complete (01-01) |
| METR-03 | Phase 1 - Metrics Correctness | Complete (01-01) |
| METR-04 | Phase 1 - Metrics Correctness | Complete |
| DISP-01 | Phase 2 - Dispatch & Rate Control | Pending |
| DISP-02 | Phase 2 - Dispatch & Rate Control | Pending |
| DISP-03 | Phase 2 - Dispatch & Rate Control | Pending |
| SAFE-01 | Phase 3 - Thread Safety | Complete |
| SAFE-02 | Phase 3 - Thread Safety | Complete |
| SAFE-03 | Phase 3 - Thread Safety | Complete |
| SAFE-04 | Phase 3 - Thread Safety | Complete |
| SAFE-05 | Phase 3 - Thread Safety | Complete |
| SAFE-06 | Phase 3 - Thread Safety | Complete |
| PROT-01 | Phase 4 - Protocol I/O | Complete |
| PROT-02 | Phase 4 - Protocol I/O | Complete |
| PROT-03 | Phase 4 - Protocol I/O | Complete |
| PROT-04 | Phase 4 - Protocol I/O | Complete |
| PROT-05 | Phase 4 - Protocol I/O | Complete |
| MQTT-01 | Phase 4 - Protocol I/O | Pending |
| MQTT-02 | Phase 4 - Protocol I/O | Pending |
| TEST-01 | Phase 5 - Test Infrastructure | Pending |
| TEST-02 | Phase 5 - Test Infrastructure | Pending |
| TEST-03 | Phase 5 - Test Infrastructure | Pending |
| TEST-04 | Phase 5 - Test Infrastructure | Pending |
| TEST-05 | Phase 5 - Test Infrastructure | Pending |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-29*
*Last updated: 2026-04-29 after roadmap creation*
