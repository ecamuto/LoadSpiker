# Testing Patterns

**Analysis Date:** 2026-04-29

## Test Framework

**Runner:**
- `pytest` — primary framework for `tests/` suite
- `unittest.TestCase` — used in `tests/test_mqtt.py` (mixed style; pytest can still discover and run it)
- Config: No `pytest.ini` or `pyproject.toml`; pytest invoked directly

**Assertion Library:**
- pytest's built-in `assert` statements in `tests/test_engine_core.py`, `tests/test_tcp.py`, `tests/test_udp.py`, `tests/test_performance_assertions.py`
- `unittest.TestCase.assert*` methods in `tests/test_mqtt.py` and `tests/test_database.py`

**Run Commands:**
```bash
make test            # Runs: python3 -m pytest tests/ -v
make test-all        # Runs: python3 -m pytest tests/ -v --timeout=60 (includes network tests)
make test-asan       # Runs tests with AddressSanitizer for memory error detection
python3 -m pytest tests/ -v          # Direct invocation
python3 -m pytest tests/ -v --timeout=30
```

## Test File Organization

**Location:**
- Primary test suite: `tests/` directory (co-located at project root, not inside `loadspiker/`)
- Ad-hoc/exploratory scripts: root-level `test_*.py` files (NOT part of the pytest suite)

**Naming:**
- Test modules: `tests/test_<area>.py` (e.g., `tests/test_engine_core.py`, `tests/test_tcp.py`)
- Test classes: `Test<Feature>` (e.g., `TestEngineLifecycle`, `TestTCPBasicOperations`, `TestMetrics`)
- Test methods: `test_<behavior>` (e.g., `test_tcp_connect_success`, `test_metrics_after_request`)

**Structure:**
```
tests/
├── conftest.py              # Shared fixtures, mock servers
├── test_engine_core.py      # Engine lifecycle, HTTP, metrics, protocol skip markers
├── test_tcp.py              # TCP protocol operations
├── test_udp.py              # UDP protocol operations
├── test_mqtt.py             # MQTT protocol (unittest.TestCase style)
├── test_database.py         # Database protocol
└── test_performance_assertions.py  # Performance assertion classes

# Root-level scripts (manual/demo, not part of pytest suite):
test_c_ext_direct.py
test_simple.py
test_debug.py
test_websocket.py
test_data_system_working.py
test_data_driven.py
test_loadspiker_basic.py
test_distribution_ready.py
test_performance_assertions_standalone.py
```

## Test Structure

**Suite Organization (pytest style — used in most test files):**
```python
class TestTCPBasicOperations:
    """Test basic TCP operations"""

    def test_tcp_connect_success(self, engine, mock_tcp_server):
        """Test successful TCP connection"""
        server, port = mock_tcp_server
        response = engine.tcp_connect('localhost', port, timeout_ms=5000)
        assert response['success'] is True
        assert response['status_code'] == 200
```

**Suite Organization (unittest style — used in `tests/test_mqtt.py`):**
```python
class TestMQTTProtocol(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = Engine(max_connections=10, worker_threads=2)
        cls.test_broker = "test.mosquitto.org"

    def setUp(self):
        self.engine.reset_metrics()

    def test_mqtt_connect_basic(self):
        result = self.engine.mqtt_connect(...)
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
```

**Patterns:**
- Each test class groups related behavior; names are descriptive noun phrases
- Test method docstrings are one-liner descriptions of the behavior under test
- `engine.reset_metrics()` called in `setUp`/at the start of metrics tests to isolate state
- All response dict assertions check `response['success'] is True/False` and `response['status_code']`

## Mocking

**Framework:** `unittest.mock` — used sparingly

**Pattern:**
```python
from unittest.mock import Mock, patch

# Used in tests/test_performance_assertions.py for custom assertion testing
func = lambda m: m.get('value', 0) > 5
assertion = CustomPerformanceAssertion(func)
```

**Real mock servers preferred over unittest.mock:**
The codebase uses real in-process TCP/UDP servers over `unittest.mock`. Both `conftest.py` and `tests/test_tcp.py` define `MockTCPServer` and `MockUDPServer` classes that spawn real sockets:

```python
class MockTCPServer:
    """Reusable mock TCP echo server for testing."""
    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.port = self.server_socket.getsockname()[1]  # bind to port 0, get actual port
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        time.sleep(0.1)  # allow server to start
        return self.port
```

**What to Mock:**
- External services not available in CI (use `pytest.mark.skipif` instead of mocking for protocol support)
- Custom callable logic in `CustomAssertion` / `CustomPerformanceAssertion`

**What NOT to Mock:**
- The `Engine` class itself — tests always instantiate a real `Engine`
- TCP/UDP servers — use real socket servers from `conftest.py`
- Metrics — always call `engine.reset_metrics()` to isolate, never mock the dict

## Fixtures and Shared Infrastructure

**Conftest fixtures (`tests/conftest.py`):**
```python
@pytest.fixture
def engine():
    """Provide a fresh LoadSpiker engine with default settings."""
    eng = Engine(max_connections=10, worker_threads=2)
    yield eng
    del eng

@pytest.fixture
def engine_large():
    """Provide a LoadSpiker engine with larger capacity for stress tests."""
    eng = Engine(max_connections=50, worker_threads=4)
    yield eng
    del eng

@pytest.fixture
def mock_tcp_server():
    """Fixture providing a mock TCP echo server."""
    server = MockTCPServer()
    server.start()
    yield server, server.port
    server.stop()

@pytest.fixture
def mock_udp_server():
    """Fixture providing a mock UDP echo server."""
    server = MockUDPServer()
    server.start()
    yield server, server.port
    server.stop()
```

**Local fixtures:** `tests/test_tcp.py` also defines its own `engine` and `mock_tcp_server` fixtures (duplicating conftest) — this is inconsistency, not intentional design.

**Test data fixtures (`tests/test_performance_assertions.py`):**
```python
@pytest.fixture
def sample_metrics_good(self):
    return {
        'requests_per_second': 50.0,
        'avg_response_time_ms': 200.0,
        'max_response_time_us': 1000000,
        'total_requests': 1000,
        'successful_requests': 980,
        'failed_requests': 20
    }
```

**Location:**
- Shared fixtures: `tests/conftest.py`
- Per-file fixtures: defined inline in test files
- CSV test data: `test_csv_data.csv` at project root (used by data-driven tests)

## Conditional Test Skipping

C extension protocol methods that may not be bound are skipped at collection time using module-level skip markers:

```python
# From tests/test_engine_core.py

def _has_protocol_method(method_name):
    """Check if the underlying engine exposes a given protocol method."""
    try:
        eng = Engine(max_connections=1, worker_threads=1)
        return hasattr(eng._engine, method_name)
    except Exception:
        return False

_has_tcp = _has_protocol_method('tcp_connect')
_skip_tcp = pytest.mark.skipif(
    not _has_tcp,
    reason="C extension missing TCP protocol bindings (python_extension.c)"
)

@_skip_tcp
class TestTCPProtocol:
    ...
```

Apply `@_skip_tcp`, `@_skip_udp`, `@_skip_mqtt`, or `@_skip_database` to entire test classes that depend on C extension bindings.

## Coverage

**Requirements:** Not enforced — no coverage configuration found

**View Coverage:**
```bash
python3 -m pytest tests/ --cov=loadspiker --cov-report=html
```

## Test Types

**Unit Tests:**
- `tests/test_performance_assertions.py` — pure unit tests for assertion classes, no I/O
- Tests instantiate classes directly with in-memory dicts as inputs
- All edge cases tested: missing keys, zero values, exact matches, `None` values, large/small numbers

**Integration Tests:**
- `tests/test_engine_core.py` — makes real HTTP requests to `http://example.com` and `http://httpbin.org`
- `tests/test_tcp.py`, `tests/test_udp.py` — use real in-process socket servers
- `tests/test_mqtt.py` — connects to public `test.mosquitto.org` broker (requires network)

**E2E / Demo Scripts:**
- Root-level `test_*.py` files are manual scripts, not pytest-discoverable tests
- Run directly: `python3 test_c_ext_direct.py`, `python3 test_simple.py`
- These test full stack including C extension loading

## Common Patterns

**Async Testing:**
Not used — no `async def test_*` or `pytest-asyncio` in the codebase. Concurrent behavior is tested synchronously via threading inside test helpers.

**Error path testing:**
```python
def test_tcp_connect_failure(self, engine):
    """Test TCP connection failure to non-existent server"""
    response = engine.tcp_connect('localhost', 65432, timeout_ms=1000)
    assert isinstance(response, dict)
    assert response['success'] is False

def test_tcp_invalid_hostname(self, engine):
    response = engine.tcp_connect('invalid.nonexistent.domain', 80, timeout_ms=1000)
    assert response['success'] is False
    assert response['error_message'] != ''
```

**Exception testing (assertion system):**
```python
def test_check_not_implemented(self):
    assertion = PerformanceAssertion()
    with pytest.raises(NotImplementedError):
        assertion.check({})

def test_invalid_logic(self):
    group = PerformanceAssertionGroup("INVALID")
    group.add(ThroughputAssertion(10.0))
    with pytest.raises(ValueError, match="Unknown logic operator: INVALID"):
        group.check_all_metrics({'requests_per_second': 15.0})
```

**Integration scenario pattern:**
```python
class TestIntegrationScenarios:
    @pytest.fixture
    def sample_metrics_good(self):
        return { 'requests_per_second': 50.0, ... }

    def test_high_performance_api_requirements(self, sample_metrics_good):
        api_requirements = [
            throughput_at_least(30.0, "API should handle 30+ RPS"),
            avg_response_time_under(500.0, "API response time under 500ms"),
        ]
        success, failures = run_performance_assertions(sample_metrics_good, api_requirements)
        assert success is True
        assert len(failures) == 0
```

---

*Testing analysis: 2026-04-29*
