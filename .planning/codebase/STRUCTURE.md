# Codebase Structure

**Analysis Date:** 2026-04-29

## Directory Layout

```
LoadSpiker/
├── cli.py                          # CLI entry point (console_scripts: loadspiker)
├── setup.py                        # Build config; compiles C extension
├── Makefile                        # Alternative build / test / install targets
├── requirements.txt                # Runtime Python dependencies
├── activate_env.sh                 # Helper to activate .venv
├── setup_env.py                    # Environment setup helper
│
├── src/                            # C source for the engine and protocols
│   ├── engine.c                    # Core engine: libcurl, pthreads, request queue
│   ├── engine.h                    # Public C API declaration (request_t, response_t, engine_t)
│   ├── common.h                    # Shared constants, macros, get_time_us()
│   ├── python_extension.c          # CPython extension bridge
│   └── protocols/
│       ├── tcp.c / tcp.h
│       ├── udp.c / udp.h
│       ├── mqtt.c / mqtt.h
│       ├── database.c / database.h
│       └── websocket.c / websocket.h
│
├── loadspiker/                     # Python package (installed by setup.py)
│   ├── __init__.py                 # Public surface; re-exports everything with fallbacks
│   ├── engine.py                   # Engine class (C/Python facade) + _PythonEngine fallback
│   ├── scenarios.py                # Scenario hierarchy; HTTPRequest; HAR importer
│   ├── assertions.py               # Per-response assertion classes and factory functions
│   ├── performance_assertions.py   # Aggregate metric assertions
│   ├── reporters.py                # ConsoleReporter, JSONReporter, HTMLReporter, MultiReporter
│   ├── data_sources.py             # CSVDataSource, DataManager, DataStrategy
│   ├── session_manager.py          # SessionStore, SessionManager singleton, ResponseExtractor
│   ├── authentication.py           # AuthenticationFlow ABC + concrete flows
│   ├── utils.py                    # ramp_up, constant_load, spike_test load pattern generators
│   ├── loadspiker_c.cpython-313-darwin.so   # Compiled C extension (production)
│   ├── loadspiker.cpython-313-darwin.so     # Compiled C extension (alternate build)
│   ├── loadspiker.so                        # Older build artifact
│   └── _c_ext/
│       ├── loadspiker_c.so         # Earlier standalone .so build
│       └── loadspiker_engine.so
│
├── obj/                            # Compiled .o object files (Makefile build)
│   ├── engine.o
│   ├── websocket.o
│   ├── mqtt.o
│   ├── database.o
│   ├── tcp.o
│   ├── udp.o
│   ├── python_extension.o
│   └── loadspiker.so               # Linked shared library (Makefile output)
│
├── build/                          # setuptools build artifacts
│   ├── lib.macosx-15.0-arm64-cpython-313/
│   └── temp.macosx-15.0-arm64-cpython-313/
│
├── tests/                          # Canonical test suite (pytest)
│   ├── conftest.py                 # Shared fixtures: engine, mock_tcp_server, mock_udp_server
│   ├── test_engine_core.py         # Core engine behaviour
│   ├── test_performance_assertions.py
│   ├── test_tcp.py
│   ├── test_udp.py
│   ├── test_mqtt.py
│   └── test_database.py
│
├── examples/                       # Runnable demo scripts (not part of test suite)
│   ├── api_test.py
│   ├── simple_test.py
│   ├── stress_test.py
│   ├── multi_protocol_demo.py
│   ├── tcp_demo.py
│   ├── udp_demo.py
│   ├── mqtt_demo.py
│   ├── database_demo.py
│   └── session_auth_demo.py
│
├── benchmarks/
│   └── benchmark_engine.py         # Engine performance benchmarks
│
├── docs/                           # Documentation
│   ├── API.md
│   ├── CODE_ANALYSIS.md
│   ├── ROADMAP.md
│   └── site/                       # Built static docs
│
├── assets/
│   └── logo.png
│
├── .planning/
│   └── codebase/                   # GSD codebase analysis documents
│
├── .venv/                          # Local virtual environment (not committed)
├── .pytest_cache/
│
# Root-level legacy/scratch test files (pre-dates tests/ directory)
├── test_assertions.py
├── test_build.py
├── test_c_ext_direct.py
├── test_c_extension_integration.py
├── test_data_driven.py
├── test_data_driven_simple.py
├── test_data_system_working.py
├── test_debug.py
├── test_distribution_ready.py
├── test_loadspiker_basic.py
├── test_performance_assertions.py
├── test_performance_assertions_standalone.py
├── test_simple.py
├── test_websocket.py
└── test_csv_data.csv
```

## Directory Purposes

**`src/`:**
- Purpose: All C source code — engine core plus per-protocol implementations
- Contains: `.c` implementation files, `.h` header files
- Key files: `src/engine.h` (authoritative C API), `src/common.h` (shared constants/macros), `src/engine.c` (engine logic), `src/python_extension.c` (CPython bridge)

**`src/protocols/`:**
- Purpose: One `.c`/`.h` pair per non-HTTP protocol
- Contains: `tcp.c`, `udp.c`, `mqtt.c`, `database.c`, `websocket.c`
- Key files: Each exports functions following the pattern `engine_<protocol>_<action>` declared in `src/engine.h`

**`loadspiker/`:**
- Purpose: The installable Python package
- Contains: Public Python API, scenario builders, assertion system, reporters, session/auth, data sources
- Key files: `loadspiker/__init__.py` (public surface), `loadspiker/engine.py` (facade Engine class + fallback), `loadspiker/scenarios.py` (scenario hierarchy)

**`tests/`:**
- Purpose: Canonical pytest test suite with shared fixtures
- Contains: One test file per major subsystem; `conftest.py` for fixtures
- Key files: `tests/conftest.py` (engine fixtures, MockTCPServer, MockUDPServer)

**`examples/`:**
- Purpose: Runnable demonstration scripts showing real usage patterns
- Contains: Protocol-specific demos, authentication demo, stress test
- Key files: Not imported by source; run directly with `python examples/<file>.py`

**`obj/`:**
- Purpose: Object files and final `.so` produced by `make build`
- Generated: Yes
- Committed: Yes (artifacts at repo snapshot time)

**`build/`:**
- Purpose: setuptools/distutils build artifacts from `python setup.py build_ext`
- Generated: Yes
- Committed: Yes (artifacts at repo snapshot time)

## Key File Locations

**Entry Points:**
- `cli.py`: CLI entry point; `main()` function; `loadspiker` console script
- `loadspiker/__init__.py`: Python package entry; all public symbols re-exported here

**Configuration:**
- `setup.py`: C extension definition, package metadata, install_requires
- `Makefile`: Manual build and test commands; `make build`, `make test`, `make clean`
- `requirements.txt`: Minimal runtime deps (`requests`, `pkgconfig`)

**Core Logic:**
- `src/engine.c`: C engine — libcurl multi, pthreads worker pool, HTTP execution
- `src/engine.h`: Single source of truth for all C struct/function declarations
- `src/common.h`: Shared constants, `get_time_us()`, `INIT_RESPONSE`, `SET_SUCCESS_RESPONSE`, `SET_ERROR_RESPONSE` macros
- `src/python_extension.c`: CPython extension; bridges Python ↔ C engine
- `loadspiker/engine.py`: Python `Engine` facade + `_PythonEngine` fallback (~1200 lines)

**Testing:**
- `tests/conftest.py`: Shared fixtures (`engine`, `engine_large`, `mock_tcp_server`, `mock_udp_server`)
- `tests/test_engine_core.py`: Core engine functional tests
- `tests/test_performance_assertions.py`: Performance assertion suite

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (`session_manager.py`, `data_sources.py`)
- C source: `snake_case.c` / `snake_case.h`
- Test files: `test_<subsystem>.py` inside `tests/`; older root-level scratch tests use the same prefix
- Demo files: `<protocol>_demo.py` or `<feature>_demo.py` in `examples/`

**Directories:**
- Python package: lowercase (`loadspiker/`)
- C source: lowercase (`src/`, `src/protocols/`)
- Artifact dirs: lowercase (`obj/`, `build/`)

**Python symbols:**
- Classes: `PascalCase` (`Engine`, `RESTAPIScenario`, `BasicAuthenticationFlow`)
- Functions/methods: `snake_case` (`execute_request`, `run_scenario`, `build_requests`)
- Private/internal: leading underscore (`_PythonEngine`, `_c_extension_available`, `_get_python_modules`)
- Constants: `UPPER_SNAKE_CASE` (`DEFAULT_HTTP_TIMEOUT_MS`, `DEFAULT_MQTT_PORT`)

**C symbols:**
- Types: `snake_case_t` (`engine_t`, `request_t`, `response_t`, `metrics_t`)
- Functions: `engine_<subsystem>_<action>` (`engine_tcp_connect`, `engine_mqtt_publish`)
- Macros: `UPPER_SNAKE_CASE` (`MAX_URL_LENGTH`, `INIT_RESPONSE`, `SET_ERROR_RESPONSE`)
- Enums: `snake_case_t` with `UPPER_SNAKE_CASE` members (`protocol_type_t`, `PROTOCOL_HTTP`)

## Where to Add New Code

**New Protocol (C side):**
- Add `src/protocols/<protocol>.c` and `src/protocols/<protocol>.h`
- Declare new `engine_<protocol>_*` functions in `src/engine.h`
- Implement them, `#include` the new header in `src/engine.c`
- Add the new source to `loadspiker_c_extension.sources` in `setup.py` and `ENGINE_SOURCES` in `Makefile`

**New Protocol (Python side):**
- Add `engine_<protocol>_*` wrapper methods to the `Engine` class in `loadspiker/engine.py`
- Add stub methods to `_PythonEngine` in the same file using stdlib sockets or returning 501 dicts
- Add a `<Protocol>Scenario` class to `loadspiker/scenarios.py` extending `Scenario`
- Export from `loadspiker/__init__.py`

**New Assertion Type:**
- Per-response: extend `Assertion` in `loadspiker/assertions.py`; add a factory function following the pattern of `status_is()`, `body_contains()`, etc.
- Aggregate metrics: extend `PerformanceAssertion` in `loadspiker/performance_assertions.py`

**New Reporter:**
- Extend `BaseReporter` in `loadspiker/reporters.py`; implement `report_metrics` and optionally `report_progress`

**New Authentication Flow:**
- Extend `AuthenticationFlow` ABC in `loadspiker/authentication.py`; implement `authenticate(engine, user_id)`
- Register via `AuthenticationManager` or expose as a `create_<type>_auth()` factory function

**Tests for new feature:**
- Place in `tests/test_<feature>.py`
- Use fixtures from `tests/conftest.py`; add new shared fixtures there if needed

**Utilities:**
- Load pattern generators: `loadspiker/utils.py`
- Shared C constants/macros: `src/common.h`

## Special Directories

**`loadspiker/_c_ext/`:**
- Purpose: Houses older `.so` build artifacts from earlier build iterations
- Generated: Yes
- Committed: Yes (historical artifacts)

**`.planning/codebase/`:**
- Purpose: GSD codebase analysis documents consumed by plan/execute commands
- Generated: Yes (by `/gsd:map-codebase`)
- Committed: Recommended yes

**`.venv/`:**
- Purpose: Local virtual environment
- Generated: Yes
- Committed: No (in `.gitignore`)

---

*Structure analysis: 2026-04-29*
