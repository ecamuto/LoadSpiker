<p align="center">
  <img src="assets/logo.png" alt="LoadSpiker logo" width="300"/>
</p>

# LoadSpiker

A high-performance load testing tool with a C engine and Python scripting interface, designed to compete with tools like Gatling and JMeter.

## Features

- **High Performance**: C-based HTTP engine with async I/O and connection pooling
- **Python Scripting**: Easy-to-use Python API for creating test scenarios
- **Real-time Metrics**: Live performance monitoring and reporting
- **Multiple Report Formats**: Console, JSON, and HTML reports with charts
- **Flexible Load Patterns**: Constant load, ramp-up, spike testing, and custom patterns
- **REST API Testing**: Built-in support for REST API testing scenarios
- **Website Testing**: Realistic user behavior simulation for web applications
- **Advanced Assertions**: Comprehensive assertion system for response validation
- **Data-Driven Testing**: CSV file support for parameterized load testing with multiple distribution strategies

## Quick Start

### Installation

```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install libcurl4-openssl-dev python3-dev pkg-config

# Install LoadSpiker
git clone <repository-url>
cd LoadSpiker
make install-deps
make install
```

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

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Python API    │    │  Python Scripts  │    │   CLI Interface │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────────────────────────────┐
         │           Python C Extension                  │
         └───────────────────────────────────────────────┘
                                 │
         ┌───────────────────────────────────────────────┐
         │              C Engine Core                    │
         │  • HTTP Client (libcurl)                      │
         │  • Connection Pooling                         │
         │  • Worker Threads                             │
         │  • Metrics Collection                         │
         └───────────────────────────────────────────────┘
```

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
    return scenario.post("/api/login", body=f'''{{
        "username": "{user_data['username']}",
        "password": "{user_data['password']}"
    }}''')

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

## Performance Benchmarks

LoadSpiker is designed for high performance:

- **Throughput**: 10,000+ requests/second on modern hardware
- **Memory Usage**: Low memory footprint with efficient connection pooling
- **Latency**: Minimal overhead compared to pure HTTP clients
- **Scalability**: Handles thousands of concurrent connections

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
# 1. Build debug version for detailed error information
make clean
make debug

# 2. Copy debug build to package
cp obj/loadtest_debug.so loadspiker/loadtest.so

# 3. Run with memory debugging (Linux)
ASAN_OPTIONS=abort_on_error=1:halt_on_error=1 python3 your_test.py

# 4. Run with memory debugging (macOS)
DYLD_INSERT_LIBRARIES=/Library/Developer/CommandLineTools/usr/lib/clang/17/lib/darwin/libclang_rt.asan_osx_dynamic.dylib python3 your_test.py

# 5. If AddressSanitizer doesn't work, try Valgrind (Linux)
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

# 3. Verify the shared library exists
ls -la loadspiker/_c_ext/loadspiker_c.so

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

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for detailed information on:

- Setting up the development environment
- Code style guidelines
- Testing procedures
- Debugging techniques
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
