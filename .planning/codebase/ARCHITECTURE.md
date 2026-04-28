# Architecture

**Analysis Date:** 2026-04-29

## Pattern Overview

**Overall:** Hybrid C/Python library with CLI entry point

**Key Characteristics:**
- High-performance C engine compiled as a CPython extension (`.so`) for request execution
- Pure Python fallback implementation activates when C extension is not available
- Python API layer (`Engine` class in `loadspiker/engine.py`) transparently delegates to whichever backend is loaded
- Protocol dispatch is handled within the C engine via a unified `request_t`/`response_t` struct pair
- Multi-protocol: HTTP, WebSocket, TCP, UDP, MQTT, Database (each as a separate `.c` file under `src/protocols/`)

## Layers

**C Engine Core:**
- Purpose: High-throughput request execution, connection pooling, metric accumulation
- Location: `src/engine.c`, `src/engine.h`, `src/common.h`
- Contains: `engine_t` struct (libcurl multi-handle + pthreads worker pool + mutex-guarded metrics), protocol dispatch functions, timing utilities
- Depends on: libcurl (HTTP), pthreads, POSIX sockets
- Used by: Python extension bridge

**Protocol Implementations (C):**
- Purpose: Protocol-specific send/receive logic called by the core engine
- Location: `src/protocols/tcp.c`, `src/protocols/udp.c`, `src/protocols/mqtt.c`, `src/protocols/database.c`, `src/protocols/websocket.c` (and matching `.h` files)
- Contains: Raw socket code for TCP/UDP, MQTT packet framing, DB stub, WebSocket handshake
- Depends on: `src/engine.h`, `src/common.h`
- Used by: `src/engine.c`

**Python Extension Bridge:**
- Purpose: Exposes the C engine as the `loadspiker.loadspiker_c.Engine` Python type
- Location: `src/python_extension.c`
- Contains: `LoadTestEngineObject` CPython type, argument parsing (`PyArg_ParseTupleAndKeywords`), response dict construction
- Depends on: `src/engine.h`, CPython C API
- Used by: `loadspiker/engine.py` via `from . import loadspiker_c`

**Python API Layer:**
- Purpose: High-level public API; transparent C/Python backend selection; TypedDict contracts
- Location: `loadspiker/engine.py`
- Contains: `Engine` class (public), `_PythonEngine` class (fallback), `MetricsDict`/`ResponseDict`/`ProtocolDataDict` TypedDicts
- Depends on: C extension (optional), `session_manager`, `authentication`, stdlib `socket`, `requests`
- Used by: `cli.py`, end-user test scripts

**Scenario / Request Building:**
- Purpose: Declarative test scenario construction; per-protocol scenario specializations
- Location: `loadspiker/scenarios.py`
- Contains: `HTTPRequest`, `Scenario`, `RESTAPIScenario`, `WebsiteScenario`, `DatabaseScenario`, `TCPScenario`, `UDPScenario`, `MQTTScenario`, `MixedProtocolScenario`, `create_scenario_from_har`
- Depends on: `data_sources.py`
- Used by: `loadspiker/engine.py` (`run_scenario`), `cli.py`

**Assertions:**
- Purpose: Per-response validation (request assertions) and aggregate metric validation (performance assertions)
- Location: `loadspiker/assertions.py`, `loadspiker/performance_assertions.py`
- Contains: `Assertion` base + `StatusCodeAssertion`, `ResponseTimeAssertion`, `BodyContainsAssertion`, `RegexAssertion`, `JSONPathAssertion`, `HeaderAssertion`, `CustomAssertion`, `AssertionGroup`; and separately `PerformanceAssertion` base + throughput/latency/error-rate variants
- Depends on: nothing (standalone)
- Used by: user test scripts, `loadspiker/__init__.py`

**Session & Authentication:**
- Purpose: Per-virtual-user session state (cookies, tokens) and pluggable auth flows
- Location: `loadspiker/session_manager.py`, `loadspiker/authentication.py`
- Contains: `SessionStore` (thread-safe dict + cookie + token storage), `ResponseExtractor`, `SessionManager` (singleton), `AuthenticationFlow` ABC + `BasicAuthenticationFlow`, `BearerTokenAuthenticationFlow`, `APIKeyAuthenticationFlow`, `FormBasedAuthenticationFlow`, `OAuth2AuthorizationCodeFlow`, `CustomAuthenticationFlow`, `AuthenticationManager`
- Depends on: `session_manager` (authentication imports it)
- Used by: `_PythonEngine` in `loadspiker/engine.py`

**Data Sources:**
- Purpose: Data-driven testing; supplies per-user parameterised values
- Location: `loadspiker/data_sources.py`
- Contains: `DataStrategy` enum, `DataSource` ABC, `CSVDataSource`, `DataManager`
- Depends on: stdlib `csv`, `json`, `threading`
- Used by: `loadspiker/scenarios.py`

**Reporters:**
- Purpose: Consuming metrics and producing test output
- Location: `loadspiker/reporters.py`
- Contains: `BaseReporter`, `ConsoleReporter`, `JSONReporter`, `HTMLReporter`, `MultiReporter`
- Depends on: nothing (operates on metric dicts)
- Used by: `cli.py`, user test scripts

**CLI Entry Point:**
- Purpose: Command-line interface; scenario/config loading; interactive REPL
- Location: `cli.py` (root)
- Contains: `load_scenario_from_file`, `create_scenario_from_config`, `run_interactive_mode`, `main`
- Depends on: `loadspiker` package, argparse
- Used by: `loadspiker` console_scripts entry point (setup.py)

## Data Flow

**Single HTTP Request:**
1. User calls `engine.execute_request(url, method, headers, body, timeout_ms)`
2. `Engine` in `loadspiker/engine.py` marshals headers to a newline-delimited string
3. Delegates to `self._engine.execute_request(...)` — either C extension or Python fallback
4. **C path:** `LoadTestEngine_execute_request` in `src/python_extension.c` fills `http_request_t`, calls `engine_execute_request_sync` in `src/engine.c`, which uses libcurl; populates `http_response_t`; returns Python dict
5. **Python fallback path:** `_PythonEngine.execute_request` uses `requests` library, returns equivalent dict
6. Caller receives `ResponseDict` with `status_code`, `response_time_us`, `body`, `success`, `error_message`

**Load Test Scenario:**
1. User constructs a `Scenario` (or subclass) in `loadspiker/scenarios.py`, adds requests
2. Calls `engine.run_scenario(scenario, users=N, duration=D)`
3. `Engine.run_scenario` calls `scenario.build_requests()` → list of request dicts
4. Delegates to `self._engine.start_load_test(requests, concurrent_users, duration_seconds)`
5. C engine: spawns pthreads workers, distributes requests via mutex-guarded queue (`engine_t.request_queue`), accumulates `metrics_t`
6. After duration, `engine.get_metrics()` returns `MetricsDict`
7. Optional: `ConsoleReporter.report_metrics(metrics)` or `JSONReporter`/`HTMLReporter`

**CLI Invocation:**
1. `cli.py:main()` parses args (URL / `-s` scenario file / `-c` config file / `-i` interactive)
2. Constructs `Engine`, scenario, reporters
3. Runs test loop; periodically calls `reporter.report_progress`
4. Calls `reporter.report_metrics` at the end

**State Management:**
- Engine metrics (`metrics_t`) are guarded by `pthread_mutex_t metrics_mutex` in C
- Session state per virtual user is held in `SessionManager` singleton (`loadspiker/session_manager.py`) using `threading.RLock`
- Python fallback socket state (`_tcp_sockets`, `_udp_sockets`) is stored as instance dicts on `_PythonEngine`

## Key Abstractions

**`engine_t` (C struct):**
- Purpose: Central engine state — libcurl multi-handle, worker threads, request queue, metrics
- Examples: `src/engine.c` (definition), `src/engine.h` (declaration)
- Pattern: Opaque handle; created/destroyed via `engine_create`/`engine_destroy`

**`request_t` / `response_t` (C structs):**
- Purpose: Protocol-agnostic message container; carries `protocol_type_t` discriminant and a `union` of protocol-specific sub-structs
- Examples: `src/engine.h` lines 42–132
- Pattern: Tagged union; protocol-specific data in `protocol_data` union field

**`Engine` (Python class):**
- Purpose: Public API; hides C/Python backend selection from callers
- Examples: `loadspiker/engine.py` line 1000
- Pattern: Facade / strategy — delegates every call to `self._engine` which is either `_CEngine` or `_PythonEngine`

**`Scenario` hierarchy:**
- Purpose: Declarative request builder per protocol type
- Examples: `loadspiker/scenarios.py` — `Scenario`, `RESTAPIScenario`, `TCPScenario`, `MQTTScenario`, etc.
- Pattern: Template method — subclasses override `build_requests()` to produce a list of request dicts consumed by the engine

**`Assertion` / `PerformanceAssertion` hierarchies:**
- Purpose: Composable validation objects; `Assertion` validates single responses, `PerformanceAssertion` validates aggregate `MetricsDict`
- Examples: `loadspiker/assertions.py`, `loadspiker/performance_assertions.py`
- Pattern: Strategy — `check(response)` / `check_metrics(metrics)` methods

**`AuthenticationFlow` ABC:**
- Purpose: Pluggable authentication strategies that write tokens/cookies into per-user `SessionStore`
- Examples: `loadspiker/authentication.py` lines 31–615
- Pattern: Strategy / Template method with abstract `authenticate(engine, user_id)`

## Entry Points

**CLI:**
- Location: `cli.py` (`main` function)
- Triggers: `loadspiker` console script (setup.py entry point) or `python cli.py`
- Responsibilities: Argument parsing, scenario file loading, engine instantiation, reporter orchestration, interactive REPL

**Python API:**
- Location: `loadspiker/__init__.py`
- Triggers: `from loadspiker import Engine` / `import loadspiker`
- Responsibilities: Re-exports all public symbols; lazy-loads modules with graceful fallbacks if C extension or optional modules are absent

**C Extension Module:**
- Location: `loadspiker/loadspiker_c.cpython-313-darwin.so` (compiled); source at `src/python_extension.c`
- Triggers: `from . import loadspiker_c` inside `loadspiker/engine.py`
- Responsibilities: Bridges Python calls to `engine_t`; exposes `Engine` Python type with `execute_request`, `start_load_test`, `get_metrics`, `reset_metrics`, WebSocket/TCP/UDP/MQTT methods

## Error Handling

**Strategy:** Graceful degradation with explicit fallbacks

**Patterns:**
- C extension import failures are caught and the code silently falls back to `_PythonEngine` (logged to stdout)
- All module imports in `loadspiker/__init__.py` are wrapped in `try/except ImportError` blocks that provide stub implementations so the package always imports cleanly
- C functions use `SET_ERROR_RESPONSE` macro (defined in `src/common.h`) to set `success=false`, HTTP-style status code, and error string on failure
- Python fallback methods return a uniform error dict `{'status_code': 500, 'success': False, 'error_message': str(e)}`
- CLI uses bare `except Exception as e` with `print` for user-facing errors

## Cross-Cutting Concerns

**Logging:** `print()` to stdout throughout (no structured logging library). C extension build progress uses emoji-prefixed print statements.

**Validation:** Assertion objects (`loadspiker/assertions.py`, `loadspiker/performance_assertions.py`) — called explicitly by the user after receiving a response; not enforced automatically.

**Authentication:** `SessionManager` singleton holds per-user `SessionStore`; `AuthenticationFlow` subclasses inject Authorization headers or tokens before requests are dispatched.

**Thread Safety:** C engine metrics guarded by `pthread_mutex_t`. Python session store uses `threading.RLock`. Python fallback socket maps (`_tcp_sockets`, `_udp_sockets`) are per-instance dicts with no explicit lock.

---

*Architecture analysis: 2026-04-29*
