<p align="center">
  <img src="assets/logo.png" alt="LoadSpiker logo" width="300"/>
</p>

# LoadSpiker

A high-performance load-testing tool with a **C engine** and a **Python
scripting interface**, designed in the spirit of Gatling and JMeter but driven
by plain Python.

> **This README is the primary documentation.** For internals and contribution
> workflow see the **[Contributor Guide](docs/CONTRIBUTOR_GUIDE.md)**; for known
> issues and their fixes see the **[Security & Correctness Audit](docs/SECURITY_AUDIT.md)**;
> for the full user API see **[docs/API.md](docs/API.md)**.

## Features

- **C engine on the hot path** — worker-thread pool, libcurl HTTP, connection
  pooling, and a microsecond-resolution latency histogram (p95/p99).
- **Python scripting** — author scenarios, assertions, and reporting in Python.
- **Multi-protocol** — HTTP/HTTPS, TCP, UDP, MQTT (real); real RFC 6455
  WebSocket and real databases (PostgreSQL, MySQL/MariaDB, MongoDB) where the
  build finds libcurl's WebSocket API and the respective client libs — each
  degrades to simulation otherwise (see the capability matrix below).
- **Session management** — thread-safe per-user session storage, cookie
  handling, and response→variable correlation.
- **Authentication flows** — Basic, Bearer, API Key, Form, OAuth 2.0, Custom.
- **Assertions** — response assertions (status, body, JSON path, headers,
  timing) and aggregate performance assertions (throughput, error rate, …).
- **Reporting** — Console, JSON, and HTML reporters, composable via `MultiReporter`.
- **Load patterns** — constant, ramp-up, spike, and stress helpers.
- **Data-driven testing** — CSV sources with sequential/random/circular/unique
  distribution and `${var}` substitution.

### Protocol capability matrix

LoadSpiker runs either the **C engine** (when the compiled extension is present)
or a **pure-Python fallback**. What each protocol actually does today:

| Protocol | C engine | Python fallback | Notes |
| -------- | -------- | --------------- | ----- |
| HTTP/HTTPS | ✅ real (libcurl) | ✅ real (`requests`) | Full request queue + worker pool in C. |
| TCP | ✅ real sockets | ✅ real sockets | Connection pool; binary payloads with embedded NULs send in full. |
| UDP | ✅ real sockets | ✅ real sockets | Endpoint pool. |
| MQTT | ✅ real MQTT 3.1.1 over TCP | ⚠️ simulated | Hand-rolled CONNECT/PUBLISH/SUBSCRIBE packets. |
| WebSocket | ✅ real RFC 6455 (libcurl WS) / ⚠️ simulated fallback | ⚠️ not implemented | Real frames via libcurl's WebSocket API when built with `HAVE_CURL_WEBSOCKETS`; simulated where libcurl lacks WS support. |
| Database | ✅ real PostgreSQL (libpq) / MySQL (libmysqlclient) / MongoDB (libmongoc), each with ⚠️ simulated fallback | ⚠️ not implemented | Real connect/query when built with `HAVE_LIBPQ` / `HAVE_MYSQL` / `HAVE_MONGOC`; falls back to simulation when a client lib is absent. MongoDB query string is a JSON command document. |

> Where a protocol falls back to simulation it returns realistic-looking
> responses and timings so you can build and validate scenarios, but it does not
> talk to a real server. The build degrades gracefully: `setup.py` probes
> `curl-config`/`pg_config` and defines `HAVE_CURL_WEBSOCKETS` / `HAVE_LIBPQ`
> only when those are present.
> Tracked in the [Contributor Guide](docs/CONTRIBUTOR_GUIDE.md#8-known-gaps--refactor-todo).

## Additional documentation

A static HTML site also ships in `docs/site/` (`open docs/site/index.html`); its
protocol/architecture/API pages are reconciled with the capability matrix above.
When in doubt, this README and the Contributor Guide are authoritative.

## Quick Start

### Installation

```bash
# 1. System dependencies
sudo apt-get install build-essential libcurl4-openssl-dev python3-dev pkg-config  # Debian/Ubuntu
# brew install curl pkg-config                                                    # macOS

# 2. Get the source
git clone <repository-url>
cd LoadSpiker

# 3a. Build the C extension for the interpreter that will run your tests
python3 setup.py build_ext --inplace          # produces loadspiker/loadspiker_c.<abi>.so
# 3b. (or) use the Makefile helpers
make install-deps
make install
```

> **Which build command?** `python3 setup.py build_ext --inplace` compiles the
> extension for *your* Python interpreter and places it where `import loadspiker`
> finds it. `make build` produces `obj/loadspiker.so` against whatever
> `python3-config` resolves to — handy for a compile check, but the in-place
> build is what Python imports. After editing a C **header**, re-run with
> `--force` (setuptools doesn't track header dependencies). If imports look
> stale, delete leftover `*.so` files in the repo root / `loadspiker/`.

### Simple Usage

```bash
# Quick URL test
python3 cli.py https://httpbin.org/get -u 10 -d 30

# Interactive mode
python3 cli.py -i

# Advanced load pattern
python3 cli.py https://api.example.com -p "ramp:1:50:60" --html report.html
```

### Python API

```python
from loadspiker import Engine, Scenario

# Create engine
engine = Engine(max_connections=100, worker_threads=4)

# Create scenario
scenario = Scenario("My Test")
scenario.get("https://httpbin.org/get")
scenario.post("https://httpbin.org/post", body='{"test": "data"}')

# Run test
results = engine.run_scenario(scenario, users=10, duration=60)
print(f"RPS: {results['requests_per_second']:.2f}")
```

### Advanced Assertions

```python
from loadspiker import Engine
from loadspiker.assertions import (
    status_is, response_time_under, body_contains, json_path, 
    header_exists, run_assertions
)

engine = Engine(max_connections=50, worker_threads=4)

# Execute request
response = engine.execute_request("https://api.example.com/users/123")

# Define assertions
assertions = [
    status_is(200, "Expected successful response"),
    response_time_under(1000, "Response should be under 1 second"),
    json_path("user.id", 123, message="User ID should match"),
    json_path("user.email", exists=True),
    header_exists("content-type", "application/json"),
    body_contains("user")
]

# Run assertions
success, failures = run_assertions(response, assertions)
if not success:
    print("Assertion failures:", failures)
```

## Architecture

LoadSpiker is three layers; the hot path lives in C while authoring stays in
Python.

```
Layer 3  Python authoring        loadspiker/*.py, cli.py
         (Engine wrapper, Scenario builders, assertions,
          reporters, sessions/auth, CSV data sources)
                    │  keyword-argument method calls
Layer 2  CPython C extension     src/python_extension.c
         (loadspiker.Engine type: marshal args → C structs,
          release the GIL around I/O, build result dicts)
                    │  engine_* / protocol_* C calls
Layer 1  C engine core           src/engine.c + src/protocols/*.c
         (worker-thread pool, request queue, libcurl HTTP,
          metrics histogram, per-protocol modules)
```

**Threading.** `engine_create` starts a pool of worker threads. A load test
(`start_load_test`) additionally spawns up to `min(users, num_requests)`
per-test workers that drain a shared request ring buffer and exit when it is
empty or a hard timeout (`duration + 5s`) elapses. Metrics are updated under a
dedicated `metrics_mutex`; the queue is guarded by `queue_mutex` + a condition
variable; shutdown/cancel flags are atomic. The build is verified race-free with
ThreadSanitizer (`make tsan`).

**Metrics.** Each request is recorded into a 1 ms-bucket latency histogram
(0–10 s + overflow). `get_metrics()` derives p95/p99 from the histogram and RPS
from wall-clock elapsed time.

For a full internals tour (data structures, lock ordering, the C↔Python
boundary rules, and how to add a protocol) read the
**[Contributor Guide](docs/CONTRIBUTOR_GUIDE.md)**.

## Security & trust boundaries

- **Scenario and config files execute arbitrary code.** `python3 cli.py -s
  scenario.py` imports and runs a Python file; a JSON config drives requests.
  Treat scenario/config files like executables — only run ones you authored or
  trust.
- **Point load tests only at systems you are authorized to test.** A load tool
  is, by definition, a traffic generator.
- **Credentials** passed to MQTT/HTTP auth are used to build requests and are
  not persisted by the engine (the MQTT module explicitly wipes the password
  after the CONNECT packet is sent).

See the **[Security & Correctness Audit](docs/SECURITY_AUDIT.md)** for the full
findings list and verification steps.

## Examples

### REST API Testing

```python
from loadspiker import Engine, RESTAPIScenario
from loadspiker.assertions import status_is, json_path, response_time_under

engine = Engine(max_connections=200)
scenario = RESTAPIScenario("https://api.example.com")

# Add requests with assertions
scenario.get_resource("users", assertions=[
    status_is(200),
    json_path("users", exists=True),
    response_time_under(500)
])

scenario.create_resource("users", {"name": "Test User"}, assertions=[
    status_is(201),
    json_path("user.id", exists=True),
    json_path("user.name", "Test User")
])

scenario.update_resource("users/1", {"name": "Updated User"}, assertions=[
    status_is(200),
    json_path("user.name", "Updated User")
])

scenario.delete_resource("users/1", assertions=[status_is(204)])

results = engine.run_scenario(scenario, users=25, duration=60)
```

### Website Testing

```python
from loadspiker import Engine, WebsiteScenario

engine = Engine(max_connections=100)
scenario = WebsiteScenario("https://example.com")

scenario.browse_page("/")
scenario.browse_page("/products", think_time=2.0)
scenario.search("laptop")
scenario.login("user@example.com", "password")

results = engine.run_scenario(scenario, users=15, duration=120)
```

### MQTT Message Queue Testing

```python
from loadspiker import Engine
from loadspiker.scenarios import MQTTScenario

engine = Engine(max_connections=100, worker_threads=4)

# Create MQTT scenario for IoT device simulation
mqtt_scenario = MQTTScenario(
    broker_host="test.mosquitto.org",
    broker_port=1883,
    client_id="loadspiker_iot_test",
    name="IoT Sensor Load Test"
)

# Add various MQTT test patterns
mqtt_scenario.add_publish_test(
    topic="sensors/temperature",
    payload="25.3",
    qos=1,
    retain=True
)

mqtt_scenario.add_burst_publish_test(
    topic="sensors/data",
    message_count=100,
    base_payload="sensor reading",
    qos=0
)

mqtt_scenario.add_topic_pattern_test(
    topic_pattern="devices/+/status",
    payload="online",
    topic_count=50,
    qos=1
)

# Run MQTT load test
results = engine.run_scenario(mqtt_scenario, users=25, duration=120)
print(f"MQTT throughput: {results['requests_per_second']:.2f} messages/sec")

# Direct MQTT operations
engine = Engine()

# Connect and publish
response = engine.mqtt_connect("test.mosquitto.org", 1883, "test_client")
response = engine.mqtt_publish(
    broker_host="test.mosquitto.org",
    broker_port=1883,
    client_id="test_client",
    topic="loadtest/data",
    payload="Hello MQTT!",
    qos=1,
    retain=False
)

# Subscribe with wildcards
response = engine.mqtt_subscribe(
    broker_host="test.mosquitto.org",
    broker_port=1883,
    client_id="test_client",
    topic="sensors/+/temperature",  # Single-level wildcard
    qos=0
)
```

### Custom Load Patterns

```python
from loadspiker.utils import ramp_up, spike_test, stress_test

# Gradual ramp-up
for users, duration in ramp_up(1, 100, 300):
    engine.run_scenario(scenario, users, duration)

# Spike testing
for users, duration in spike_test(20, 100, 60, 30):
    engine.run_scenario(scenario, users, duration)

# Stress testing
for users, duration in stress_test(200, step_size=20):
    engine.run_scenario(scenario, users, duration)
```

### Session Management and Authentication

```python
from loadspiker import Engine
from loadspiker.session_manager import get_session_manager
from loadspiker.authentication import (
    get_authentication_manager, create_basic_auth, create_bearer_auth,
    create_api_key_auth, create_form_auth, create_oauth2_auth
)

engine = Engine()
session_manager = get_session_manager()
auth_manager = get_authentication_manager()

# Register different authentication methods
auth_manager.register_flow("basic", create_basic_auth("user", "pass"))
auth_manager.register_flow("api_key", create_api_key_auth("sk-123", "X-API-Key"))
auth_manager.register_flow("bearer", create_bearer_auth(token="jwt_token_xyz"))
auth_manager.register_flow("form", create_form_auth(
    login_url="https://example.com/login",
    username_field="email",
    password_field="password",
    success_indicator="Welcome"
))

# Authenticate different users with different methods
for user_id, auth_method in [("user1", "basic"), ("user2", "api_key"), ("user3", "bearer")]:
    result = auth_manager.authenticate(auth_method, engine, user_id)
    print(f"{user_id} authenticated: {result['success']}")

# Session management with request correlation
login_response = engine.execute_request(
    url="https://api.example.com/login",
    method="POST",
    headers={"Content-Type": "application/json"},
    body='{"username": "testuser", "password": "testpass"}'
)

# Auto-handle cookies and extract values for correlation
session_manager.auto_handle_cookies("user1", login_response)
extract_rules = [
    {"type": "json_path", "path": "access_token", "variable": "token"},
    {"type": "json_path", "path": "user.id", "variable": "user_id"},
    {"type": "header", "name": "X-Session-ID", "variable": "session_id"},
    {"type": "cookie", "name": "csrf_token", "variable": "csrf"}
]
session_manager.process_response("user1", login_response, extract_rules)

# Use session data in subsequent requests
headers = session_manager.prepare_request_headers("user1", {
    "Content-Type": "application/json"
})
protected_response = engine.execute_request(
    url="https://api.example.com/protected",
    headers=headers  # Automatically includes session cookies and auth tokens
)

# Access extracted session variables
session = session_manager.get_session("user1")
user_id = session.get("user_id")
csrf_token = session.get("csrf")
print(f"User {user_id} session established with CSRF: {csrf_token}")

# Multi-user session isolation
for user in ["alice", "bob", "charlie"]:
    auth_manager.authenticate("basic", engine, user_id=user)
    session = session_manager.get_session(user)
    session.set("role", f"{user}_role")
    
# Each user maintains separate session state
print("Session isolation test:")
for user in ["alice", "bob", "charlie"]:
    session = session_manager.get_session(user)
    print(f"{user}: role={session.get('role')}, cookies={session.get_all_cookies()}")
```

### Data-Driven Testing with CSV

```python
from loadspiker import Engine, Scenario
from loadspiker.data_sources import load_csv_data, get_user_data

# Load CSV data for parameterized testing
load_csv_data("users.csv", strategy="sequential")

engine = Engine(max_connections=100)
scenario = Scenario("User Login Test")

# CSV file format: username,password,email,user_id,subscription_type
# Data is automatically distributed among virtual users

def user_login(user_id):
    user_data = get_user_data(user_id)
    return scenario.post("/api/login", body=f'''{
        "username": "{user_data['username']}",
        "password": "{user_data['password']}"
    }''')

# Or use built-in scenario CSV support with variable substitution
scenario.load_data_file("users.csv", strategy="sequential")
scenario.post("/api/login", body='{"username": "${data.username}", "password": "${data.password}"}')

# Multiple CSV files for complex scenarios
scenario.load_data_file("users.csv", name="users", strategy="sequential")
scenario.load_data_file("products.csv", name="products", strategy="random")
scenario.post("/api/order", body='{"user_id": "${users.user_id}", "product_id": "${products.product_id}"}')

results = engine.run_scenario(scenario, users=20, duration=60)
```

### Advanced Reporting

```python
from loadspiker.reporters import HTMLReporter, JSONReporter, MultiReporter

# Multiple report formats
reporter = MultiReporter([
    ConsoleReporter(show_progress=True),
    HTMLReporter("report.html"),
    JSONReporter("results.json")
])

reporter.start_reporting()
results = engine.run_scenario(scenario, users=50, duration=120)
reporter.report_metrics(results)
reporter.end_reporting()
```

## Configuration Files

### JSON Configuration

```json
{
  "type": "rest_api",
  "name": "API Load Test",
  "base_url": "https://api.example.com",
  "requests": [
    {
      "url": "https://api.example.com/health",
      "method": "GET"
    },
    {
      "url": "https://api.example.com/users",
      "method": "POST",
      "body": "{\"name\": \"Test User\"}",
      "headers": {"Content-Type": "application/json"}
    }
  ],
  "variables": {
    "api_key": "your-api-key"
  }
}
```

```bash
python3 cli.py -c config.json -u 20 -d 60
```

### Python Scenario Files

```python
# scenario.py
from loadspiker import Scenario
from loadspiker.scenarios import HTTPRequest

scenario = Scenario("Custom Test")
scenario.add_request(HTTPRequest("https://api.example.com/endpoint1", "GET"))
scenario.add_request(HTTPRequest("https://api.example.com/endpoint2", "POST", body='{"data": "test"}'))
```

```bash
python3 cli.py -s scenario.py -u 30 -d 90
```

## Performance

LoadSpiker keeps the request/metrics path in C with fixed-size buffers (no
per-request allocation) and a lock-light worker pool. Actual throughput depends
heavily on the target, the network, and your `max_connections`/`worker_threads`
settings, so **benchmark against your own workload** rather than relying on a
headline number. Measure with:

```bash
make benchmark   # runs benchmarks/benchmark_engine.py
```

## CLI Reference

```bash
LoadSpiker [OPTIONS] [URL]

Positional Arguments:
  URL                   Target URL for simple tests

Load Parameters:
  -u, --users          Number of concurrent users (default: 10)
  -d, --duration       Test duration in seconds (default: 60)
  -r, --ramp-up        Ramp-up duration in seconds (default: 0)
  -p, --pattern        Load pattern: "constant:100:60", "ramp:1:100:60"

Engine Configuration:
  --max-connections    Maximum connections (default: 1000)
  --threads           Worker threads (default: 10)

Request Options:
  -m, --method        HTTP method (default: GET)
  -H, --header        HTTP header (repeatable)
  -b, --body          Request body
  -t, --timeout       Request timeout in ms (default: 30000)

Input Sources:
  -s, --scenario      Python scenario file
  -c, --config        JSON configuration file
  -i, --interactive   Interactive mode

Output Options:
  --json             Save results to JSON file
  --html             Save results to HTML file
  -q, --quiet        Suppress output
  --no-progress      Disable progress reporting
```

## Build System

```bash
# Install dependencies
make install-deps

# Build C extension
make build

# Install LoadSpiker
make install

# Run tests
make test

# Run examples
make example
make quick-test

# Clean build
make clean

# Development setup
make dev-setup

# Create package
make package
```

## Troubleshooting

### Common Issues

#### Segmentation Fault on Startup

**Symptoms**: Program crashes with "segmentation fault" when making HTTP requests.

**Causes**: 
- Memory corruption in C extension
- Uninitialized buffers
- Buffer overflow in response handling

**Solutions**:
```bash
# 1. Build the AddressSanitizer debug version
make clean
make debug          # produces obj/loadspiker_debug.so

# 2. Run the suite under ASan (rebuilds + runs pytest)
make test-asan

# 3. Or run your own script with leak detection (Linux)
ASAN_OPTIONS=detect_leaks=1:abort_on_error=1 python3 your_test.py

# 4. If AddressSanitizer is unavailable, try Valgrind (Linux)
valgrind --tool=memcheck --leak-check=full python3 your_test.py
```

#### Import Error: No module named 'loadspiker'

**Symptoms**: `ImportError: No module named 'loadspiker'` when running Python scripts.

**Solutions**:
```bash
# 1. Set PYTHONPATH manually
export PYTHONPATH=/path/to/LoadSpiker:$PYTHONPATH

# 2. Use the activation script
source activate_env.sh

# 3. Verify the compiled extension exists for your interpreter
ls -la loadspiker/loadspiker_c*.so
#    If missing, build it:  python3 setup.py build_ext --inplace --force

# 4. Install in development mode (requires virtual environment)
python3 -m pip install -e .
```

#### Build Failures

**Symptoms**: Compilation errors during `make build`.

**Common Issues**:
```bash
# Missing libcurl headers
sudo apt-get install libcurl4-openssl-dev  # Ubuntu/Debian
sudo yum install libcurl-devel             # CentOS/RHEL
brew install curl                          # macOS

# Missing Python headers
sudo apt-get install python3-dev          # Ubuntu/Debian
sudo yum install python3-devel            # CentOS/RHEL

# Missing pkg-config
sudo apt-get install pkg-config           # Ubuntu/Debian
sudo yum install pkgconfig                # CentOS/RHEL
brew install pkg-config                   # macOS
```

#### High Memory Usage

**Symptoms**: Excessive memory consumption during load tests.

**Solutions**:
- Reduce `max_connections` parameter
- Decrease `worker_threads` count
- Use smaller buffer sizes for response bodies
- Implement request throttling

#### Performance Issues

**Symptoms**: Lower than expected requests per second.

**Debugging Steps**:
```bash
# 1. Check system limits
ulimit -n  # File descriptor limit
cat /proc/sys/net/core/somaxconn  # Linux connection limit

# 2. Monitor system resources
top -p $(pgrep python3)
iostat 1
netstat -an | grep ESTABLISHED | wc -l

# 3. Profile the application
python3 -m cProfile -o profile.out your_test.py
python3 -c "import pstats; p=pstats.Stats('profile.out'); p.sort_stats('cumulative').print_stats(20)"
```

#### Thread Safety Issues

**Symptoms**: Inconsistent results, crashes in multi-threaded scenarios.

**Solutions**:
- Verify thread-safe usage of the engine
- Check for shared state between threads
- Use separate engine instances for each thread if needed

### Debug Mode

Enable debug mode for detailed logging and error information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

from loadspiker import Engine
engine = Engine(max_connections=10, worker_threads=2)  # Use smaller values for debugging
```

### Getting Help

1. Check this troubleshooting section
2. Review the [Contributing Guide](CONTRIBUTING.md) for development setup
3. Search existing issues on GitHub
4. Create a new issue with:
   - Complete error message
   - System information (OS, Python version)
   - Minimal reproduction case
   - Build configuration used

## Requirements

- **System**: Linux, macOS, or Windows
- **Python**: 3.7+
- **Dependencies**: libcurl, pkg-config
- **Build Tools**: GCC or Clang, Make

### System-Specific Requirements

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install build-essential libcurl4-openssl-dev python3-dev pkg-config
```

#### CentOS/RHEL
```bash
sudo yum groupinstall "Development Tools"
sudo yum install libcurl-devel python3-devel pkgconfig
```

#### macOS
```bash
# Install Xcode Command Line Tools
xcode-select --install

# Install dependencies via Homebrew
brew install curl pkg-config
```

#### Windows
- Install Visual Studio Build Tools
- Install curl development libraries
- Install Python development headers

## Contributing

We welcome contributions! Start with the
**[Contributor Guide](docs/CONTRIBUTOR_GUIDE.md)** — a deep tour of the codebase
covering architecture, the threading model, the C↔Python boundary, build/debug
workflow, and a PR checklist. The short [CONTRIBUTING.md](CONTRIBUTING.md) is a
quickstart. Before changing the C engine, also skim the
[Security & Correctness Audit](docs/SECURITY_AUDIT.md).

Key topics:

- Setting up the development environment (and the two build paths)
- The three-layer architecture and threading model
- Reference-counting / GIL rules at the C↔Python boundary
- Testing (`make test`), ASan (`make test-asan`), and TSan (`make tsan`)
- Submitting pull requests

Quick start:
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes following our style guide
4. Add tests and ensure they pass: `make test`
5. Submit a pull request with a clear description

## License

MIT License - see LICENSE file for details.

## Comparison with Other Tools

| Feature | LoadSpiker | Gatling | JMeter | Artillery |
|---------|------------|---------|--------|-----------|
| Performance | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Ease of Use | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| Scripting | Python | Scala | GUI/XML | JavaScript |
| Resource Usage | Very Low | Low | High | Medium |
| Real-time Metrics | ✅ | ✅ | ✅ | ✅ |
| HTML Reports | ✅ | ✅ | ✅ | ✅ |
| CI/CD Integration | ✅ | ✅ | Limited | ✅ |

LoadSpiker combines the performance of Gatling with the simplicity of Python scripting, making it ideal for both developers and QA engineers.
