# LoadSpiker

## What This Is

LoadSpiker is a multi-protocol load testing library and CLI written in C/Python. It provides a high-performance C engine (via libcurl + pthreads) exposed as a Python extension, with a pure-Python fallback. The target use case is mixed-protocol load testing (HTTP + TCP + MQTT) from a single Python script or CLI command, with trustworthy metrics output.

## Core Value

Correct, trustworthy metrics across multiple protocols from a single process — if the numbers are wrong, nothing else matters.

## Requirements

### Validated

- ✓ HTTP/HTTPS load testing via libcurl C engine — existing
- ✓ Pure-Python fallback engine using `requests` — existing
- ✓ CLI entry point (`cli.py`) with URL, scenario file, config file, and interactive modes — existing
- ✓ Scenario building: HTTPRequest, Scenario, RESTAPIScenario, WebsiteScenario, TCPScenario, UDPScenario, MQTTScenario, MixedProtocolScenario — existing
- ✓ Per-response assertions: StatusCode, ResponseTime, BodyContains, Regex, JSONPath, Header, Custom — existing
- ✓ Performance assertions: throughput, latency, error-rate variants — existing
- ✓ Session management with per-virtual-user cookie and token storage — existing
- ✓ Authentication flows: Basic, Bearer, APIKey, FormBased, OAuth2, Custom — existing
- ✓ CSV-driven parameterized data sources — existing
- ✓ Reporters: Console, JSON, HTML — existing
- ✓ TCP/UDP basic connect in C engine and Python fallback — existing
- ✓ MQTT basic connect/publish/subscribe/unsubscribe in C engine — existing

### Active

- [ ] RPS calculation reports correct wall-clock-based requests-per-second
- [ ] Load test dispatcher uses worker thread pool (not main-thread usleep loop)
- [ ] Rate limiting uses correct per-worker pacing (not broken integer-division formula)
- [ ] TCP/MQTT/UDP/DB connection pools are mutex-protected (thread-safe under concurrent load)
- [ ] P95 and P99 latency tracked and surfaced in MetricsDict and all reporters
- [ ] TCP send/receive/disconnect operations execute real network I/O via C engine
- [ ] UDP receive/close operations execute real network I/O via C engine
- [ ] MQTT CONNACK validation rejects failed connections
- [ ] MQTT subscribe/unsubscribe use correct multi-byte remaining-length encoding
- [ ] `gethostbyname` replaced with thread-safe `getaddrinfo` in TCP/MQTT/UDP

### Out of Scope

- Real WebSocket network I/O (RFC 6455) — deferred; high complexity, not the primary workload
- Real database drivers (libmysql, libpq, mongoc) — deferred; DB load testing is not the current use case
- Distributed / multi-machine coordination — deferred; single-machine scope for this milestone
- GUI or real-time web dashboard — deferred; Console/JSON/HTML reporters sufficient for now

## Context

Codebase is brownfield — the architecture is sound (C engine with Python facade, protocol separation in `src/protocols/`) but several protocols have stub/simulated implementations that have not been corrected. The current RPS metric calculation divides by cumulative response time instead of elapsed wall time, making all load test results unreliable. The connection pool arrays for TCP, UDP, MQTT, and Database lack mutex protection, creating data races under any concurrent load — the primary use case.

Key files:
- `src/engine.c` — core engine, load test loop, metrics, RPS formula (broken)
- `src/engine.h` — `engine_t`, `metrics_t` structs; generic API declarations without implementations
- `src/protocols/tcp.c`, `udp.c`, `mqtt.c` — pool arrays without mutexes; `gethostbyname` usage
- `loadspiker/engine.py` — Python facade; Python fallback `_PythonEngine`

## Constraints

- **Tech stack**: C11 + CPython C Extension API; no new system dependencies without strong justification (libcurl and pthreads are already linked)
- **Compatibility**: Must maintain the existing Python public API (`Engine`, `MetricsDict`, `ResponseDict`) — no breaking changes to callsites
- **Platform**: macOS and Linux (POSIX); no Windows support required
- **Testing**: All fixes must have corresponding tests in `tests/` (not root-level `test_*.py` scripts); thread safety fixes must include concurrent stress tests

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Fix engine correctness before adding features | Metrics are untrustworthy today; new features built on bad metrics compound the problem | — Pending |
| Use histogram (fixed-size bucket array) for percentiles | Adding sorted sample buffer would require dynamic allocation in C; histogram is O(1) insert and gives good accuracy | — Pending |
| Replace `gethostbyname` with `getaddrinfo` | Thread safety and IPv6 support; `gethostbyname` is deprecated POSIX 2008 | — Pending |
| Add per-pool mutexes matching `ws_connections_mutex` pattern | Consistent with existing WebSocket pool implementation; minimal new code | — Pending |

---
*Last updated: 2026-04-29 after initialization*
