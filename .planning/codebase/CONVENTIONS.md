# Coding Conventions

**Analysis Date:** 2026-04-29

## Naming Patterns

**Files:**
- Python source modules: `snake_case.py` (e.g., `data_sources.py`, `session_manager.py`, `performance_assertions.py`)
- Test files: `test_<module_name>.py` (e.g., `test_engine_core.py`, `test_tcp.py`)
- C source files: `snake_case.c/.h` (e.g., `engine.c`, `python_extension.c`)

**Classes:**
- PascalCase for all classes: `Engine`, `Scenario`, `RESTAPIScenario`, `ThroughputAssertion`, `MockTCPServer`
- Suffix names carry semantic meaning: `*Assertion`, `*Scenario`, `*Reporter`, `*Strategy`
- Private/internal classes prefixed with underscore: `_PythonEngine`, `_PlaceholderScenario`

**Functions and Methods:**
- `snake_case` for all functions and methods: `execute_request`, `get_metrics`, `build_requests`, `check_metrics`
- Private helpers prefixed with underscore: `_run_with_ramp_up`, `_substitute_variables`, `_detect_db_type`, `_get_nested_value`
- Boolean flag helpers follow `_has_*` pattern: `_has_tcp`, `_has_mqtt` (used in test skip markers)

**Variables:**
- `snake_case` for all local and instance variables: `response_time_ms`, `broker_host`, `failed_assertions`
- Module-level flags use `_snake_case`: `_c_extension_available`, `_session_auth_available`, `_python_modules_available`
- Constants use `UPPER_SNAKE_CASE`: `DEFAULT_HTTP_TIMEOUT_MS`, `DEFAULT_MQTT_PORT`, `WARNING_FLAGS`
- TypedDict instances follow PascalCase with `Dict` suffix: `ResponseDict`, `MetricsDict`, `ProtocolDataDict`

**Parameters:**
- Timeout parameters consistently named `timeout_ms` (milliseconds)
- Host parameters consistently named `hostname` or `broker_host`
- Port parameters consistently named `port` or `broker_port`

## Code Style

**Formatting:**
- No enforced formatter detected (no `.prettierrc`, `black.toml`, or `pyproject.toml`)
- 4-space indentation throughout
- Blank lines between class methods; two blank lines between top-level definitions
- Trailing whitespace generally absent

**Linting:**
- No linting config detected (no `.flake8`, `.pylintrc`, or `ruff.toml`)
- Code generally follows PEP 8 conventions by convention, not enforcement

**Type Annotations:**
- Used consistently on public method signatures in the main `loadspiker/` package
- `typing` imports used: `List`, `Dict`, `Any`, `Optional`, `Callable`, `Union`, `TYPE_CHECKING`
- `TypedDict` used for structured return types: `ResponseDict`, `MetricsDict`, `ProtocolDataDict` in `loadspiker/engine.py`
- Fallback/internal classes often omit type annotations

## Import Organization

**Order:**
1. Standard library imports
2. Third-party imports (with `try/except ImportError` fallbacks)
3. Local/relative imports (with `try/except ImportError` fallbacks)

**Path manipulation:**
- Test files consistently add parent directory to `sys.path`:
  ```python
  sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
  ```
- `loadspiker/__init__.py` adds its own directory to `sys.path` for import compatibility

**Relative imports:**
- Used within the package: `from .engine import Engine`, `from .scenarios import Scenario`
- Every relative import wrapped in try/except with a direct import fallback

**Guarded imports:**
- `TYPE_CHECKING` guard used for circular import avoidance in `loadspiker/engine.py`
- Protocol/optional features guarded with boolean flags: `_c_extension_available`, `_session_auth_available`

## Error Handling

**Core pattern — return dicts, never raise:**
All protocol methods return a consistent response dictionary regardless of success or failure:
```python
return {
    'status_code': 500,
    'response_time_ms': 0.0,
    'response_time_us': 0.0,
    'body': '',
    'success': False,
    'error_message': f'TCP connect failed: {str(e)}'
}
```
The broad `except Exception as e` pattern is standard across all protocol implementations.

**Assertion exceptions:**
`loadspiker/assertions.py` defines a custom `AssertionError` for the assertion subsystem. Assertion methods never raise — they return `bool` from `check()`.

**C extension fallback:**
The entire `Engine` class gracefully falls back to `_PythonEngine` when the C extension is unavailable. This is checked once at module load time via `_c_extension_available`.

**Import-time fallbacks:**
Optional modules wrapped in try/except chains in `loadspiker/__init__.py`, with stub classes created when imports fail.

## Logging

**Framework:** `print()` — no logging framework used

**Patterns:**
- Emoji-prefixed print statements used throughout: `"🚀 C extension loaded"`, `"⚠️  Using Python fallback"`, `"❌ Missing Dependencies"`
- Debug/status output goes to stdout via `print()`
- Error messages in response dicts are plain strings without prefix
- Test files use `print()` for manual run output; pytest assertions for automated checks

## Comments and Documentation

**Module docstrings:**
- Every `loadspiker/*.py` module starts with a triple-quoted module docstring describing purpose and often includes usage examples
- Example from `loadspiker/engine.py`:
  ```python
  """
  High-level Python API for the load testing engine
  ...
  Example usage:
      from loadspiker import Engine
      engine = Engine(max_connections=1000, worker_threads=10)
  """
  ```

**Class docstrings:**
- Single-line or short multi-line docstrings on all public classes

**Method docstrings:**
- Public methods in `Engine` class use Google-style docstrings with `Args:` and `Returns:` sections
- Private/fallback methods use single-line docstrings

**Inline comments:**
- Section dividers using `# =====...=====` banners for logical grouping (see `loadspiker/engine.py`, `setup.py`)
- `#:` syntax used for constant documentation: `#: Default timeout for HTTP requests in milliseconds`
- Inline `# comment` used for non-obvious logic

## Function Design

**Size:**
- Public interface methods are thin delegators; all heavy logic is in the underlying `_engine` instance
- `_PythonEngine` protocol methods are self-contained and long (~30-50 lines each) due to repeated boilerplate

**Parameters:**
- Optional parameters use default values consistently: `timeout_ms: int = 30000`, `method: str = "GET"`
- `None` used as sentinel for optional strings/dicts, converted to `""` or `{}` inside method body
- `**kwargs` not used — all parameters are explicit

**Return Values:**
- Protocol methods always return `Dict[str, Any]` with keys: `status_code`, `success`, `error_message`, `response_time_ms`, `response_time_us`, `body`, `protocol_data`
- Assertion methods return `bool`
- Builder methods return `self` for fluent chaining: `scenario.get(...).post(...).setup(...)`

## Module Design

**Exports:**
- `loadspiker/__init__.py` defines explicit `__all__` list
- `from .assertions import *` used for bulk assertion export (wildcard import pattern)

**Barrel file:**
- `loadspiker/__init__.py` acts as the primary barrel file re-exporting from all submodules
- Version pinned in `__init__.py`: `__version__ = "1.0.0"`

**C extension integration:**
- C extension exposed as `loadspiker.loadspiker_c` submodule
- Python `Engine` wraps either `_CEngine` (C extension) or `_PythonEngine` (pure Python) transparently
- Extension source in `src/` directory; builds via `setup.py` / `make build`

---

*Convention analysis: 2026-04-29*
