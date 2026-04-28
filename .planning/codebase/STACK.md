# Technology Stack

**Analysis Date:** 2026-04-29

## Languages

**Primary:**
- Python 3 (>=3.7, tested on 3.13) - High-level API, CLI, test scenarios, reporters, assertions
- C (C11 standard) - High-performance load testing engine (`src/engine.c`, `src/protocols/*.c`)

**Secondary:**
- Bash - Build environment activation script (`activate_env.sh`)

## Runtime

**Environment:**
- Python 3.13 (detected on dev machine; requires >=3.7 per `setup.py`)
- POSIX-compatible OS (macOS and Linux supported; uses `pthread`, `sys/time.h`, POSIX sockets)

**Package Manager:**
- pip / pip3
- No lockfile present (only `requirements.txt` with a single entry)

## Frameworks

**Core:**
- CPython C Extension API (Python.h) - Bridges C engine to Python via `src/python_extension.c`
- setuptools + `distutils.Extension` - Build system for the C extension (`setup.py`)

**Testing:**
- pytest - Test runner; invoked as `python3 -m pytest tests/ -v` (`Makefile`)

**Build/Dev:**
- GNU Make - Primary build orchestration (`Makefile`)
- gcc - C compiler; flags: `-O3 -Wall -Wextra -pthread -fPIC` (production), `-g -O0 -fsanitize=address` (debug)
- pkg-config - Resolves libcurl compiler/linker flags at build time (`setup.py`, `Makefile`)

## Key Dependencies

**Critical (C layer):**
- libcurl - HTTP/HTTPS request execution in the C engine (`src/engine.c` includes `<curl/curl.h>`); system library, not a Python package
- pthreads - Worker thread pool and mutex synchronization in the C engine (`src/engine.c`)

**Critical (Python layer):**
- pkgconfig (PyPI) - Python wrapper to call pkg-config during the setuptools build; declared in `setup.py` `install_requires`

**Optional (Python fallback):**
- requests - Used only when C extension is unavailable; lazy `import requests` inside `_PythonEngine.execute_request()` in `loadspiker/engine.py`

**Dev/Test:**
- pytest - Listed in `Makefile` dev-setup target (`pip3 install pytest`)
- sphinx - Optional docs generator (`Makefile` docs target)
- AddressSanitizer (compiler flag `-fsanitize=address`) - Memory safety in debug builds

## Configuration

**Environment:**
- `LOADSPIKER_DEBUG=1` - Build with debug symbols and AddressSanitizer (`setup.py`)
- `LOADSPIKER_VERBOSE=1` - Print detailed build output (`setup.py`)
- `PYTHONPATH` - Must include project root when running without pip install; set by `activate_env.sh`
- `HOMEBREW_PREFIX` - Used as fallback when pkg-config is unavailable on macOS (`setup.py`)

**Build:**
- `setup.py` - Setuptools build configuration; compiles C extension `loadspiker.loadspiker_c`
- `Makefile` - Convenient wrappers for build, test, install, debug, benchmark, and packaging targets
- `setup_env.py` - Copies compiled `.so` into `loadspiker/` directory and generates `activate_env.sh`

## C Extension Architecture

The C extension (`src/python_extension.c`) wraps the core engine as a Python module `loadspiker.loadspiker_c`. The Python `Engine` class in `loadspiker/engine.py` auto-selects the C backend when available; otherwise falls back to `_PythonEngine` which uses stdlib `socket` and optional `requests`.

C source files compiled into the extension:
- `src/engine.c` - Core engine, libcurl multi-handle, thread pool, metrics
- `src/protocols/tcp.c` - Raw TCP sockets
- `src/protocols/udp.c` - UDP datagrams
- `src/protocols/mqtt.c` - MQTT 3.1.1 over TCP
- `src/protocols/database.c` - Database connection stubs (MySQL/PostgreSQL/MongoDB URL parsing)
- `src/protocols/websocket.c` - WebSocket connection state management

## Platform Requirements

**Development:**
- macOS or Linux (POSIX APIs required)
- gcc or clang
- libcurl dev headers (`libcurl4-openssl-dev` on Ubuntu, `brew install curl` on macOS)
- pkg-config
- Python 3 dev headers (`python3-config`)

**Production:**
- No server runtime; LoadSpiker is a CLI/library tool run locally or in CI
- Built artifact: `loadspiker.loadspiker_c.cpython-<ver>-<platform>.so` placed in `loadspiker/`

---

*Stack analysis: 2026-04-29*
