# LoadSpiker API Documentation

This document provides comprehensive API documentation for LoadSpiker's Python interface.

## Table of Contents

- [Engine](#engine)
- [Scenarios](#scenarios)
- [Reporters](#reporters)
- [Utilities](#utilities)

## Engine

The `Engine` class is the core component for executing load tests.

### Constructor

```python
Engine(max_connections: int = 1000, worker_threads: int = 10)
```

**Parameters:**
- `max_connections` (int): Maximum number of concurrent HTTP connections (default: 1000)
- `worker_threads` (int): Number of worker threads for request processing (default: 10)

**Example:**
```python
from LoadSpiker import Engine

# Create engine with custom settings
engine = Engine(max_connections=500, worker_threads=8)
```

### Methods

#### execute_request

```python
execute_request(
    url: str, 
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: str = "",
    timeout_ms: int = 30000
) -> Dict[str, Any]
```

Execute a single HTTP request synchronously.

**Parameters:**
- `url` (str): Target URL for the request
- `method` (str): HTTP method (GET, POST, PUT, DELETE, etc.)
- `headers` (Optional[Dict[str, str]]): HTTP headers as key-value pairs
- `body` (str): Request body content
- `timeout_ms` (int): Request timeout in milliseconds

**Returns:**
Dictionary with the following keys:
- `status_code` (int): HTTP status code
- `headers` (str): Response headers
- `body` (str): Response body content
- `response_time_us` (int): Response time in microseconds
- `success` (bool): Whether the request was successful
- `error_message` (str): Error details if request failed

**Example:**
```python
response = engine.execute_request(
    url="https://api.example.com/users",
    method="POST",
    headers={"Content-Type": "application/json"},
    body='{"name": "John Doe"}',
    timeout_ms=5000
)

print(f"Status: {response['status_code']}")
print(f"Response time: {response['response_time_us']/1000:.2f}ms")
```

#### get_metrics

```python
get_metrics() -> Dict[str, Any]
```

Get current performance metrics.

**Returns:**
Dictionary with metrics:
- `total_requests` (int): Total number of requests made
- `successful_requests` (int): Number of successful requests
- `failed_requests` (int): Number of failed requests
- `requests_per_second` (float): Current requests per second
- `avg_response_time_ms` (float): Average response time in milliseconds
- `min_response_time_us` (int): Minimum response time in microseconds
- `max_response_time_us` (int): Maximum response time in microseconds

#### reset_metrics

```python
reset_metrics() -> None
```

Reset all performance metrics to zero.

## Scenarios

The scenario system provides structured ways to define test patterns.

### Scenario

Base class for creating test scenarios.

```python
Scenario(name: str)
```

#### Methods

##### get

```python
get(url: str, headers: Optional[Dict[str, str]] = None) -> None
```

Add a GET request to the scenario.

##### post

```python
post(
    url: str,
    body: str = "",
    headers: Optional[Dict[str, str]] = None
) -> None
```

Add a POST request to the scenario.

##### put

```python
put(
    url: str,
    body: str = "",
    headers: Optional[Dict[str, str]] = None
) -> None
```

Add a PUT request to the scenario.

##### delete

```python
delete(url: str, headers: Optional[Dict[str, str]] = None) -> None
```

Add a DELETE request to the scenario.

**Example:**
```python
from LoadSpiker import Scenario

scenario = Scenario("API Test")
scenario.get("https://api.example.com/users")
scenario.post("https://api.example.com/users", body='{"name": "Test"}')
scenario.put("https://api.example.com/users/1", body='{"name": "Updated"}')
scenario.delete("https://api.example.com/users/1")
```

## Reporters

Classes for generating test reports in various formats.

### ConsoleReporter

Real-time console output during test execution.

```python
ConsoleReporter(show_progress: bool = True)
```

#### Methods

##### start_reporting

```python
start_reporting() -> None
```

Begin real-time reporting.

##### report_metrics

```python
report_metrics(metrics: Dict[str, Any]) -> None
```

Display current metrics.

##### end_reporting

```python
end_reporting() -> None
```

Stop reporting and show final summary.

### JSONReporter

Export results to JSON format.

```python
JSONReporter(filename: str)
```

### HTMLReporter

Generate HTML reports with charts and graphs.

```python
HTMLReporter(filename: str)
```

**Example:**
```python
from LoadSpiker.reporters import ConsoleReporter, JSONReporter, HTMLReporter

# Use multiple reporters
console_reporter = ConsoleReporter(show_progress=True)
json_reporter = JSONReporter("results.json")
html_reporter = HTMLReporter("report.html")

console_reporter.start_reporting()
# Run your tests here
metrics = engine.get_metrics()
console_reporter.report_metrics(metrics)
json_reporter.report_metrics(metrics)
html_reporter.report_metrics(metrics)
console_reporter.end_reporting()
```

## Utilities

Helper functions for common load testing patterns.

### ramp_up

```python
ramp_up(start_users: int, end_users: int, duration: int) -> Iterator[Tuple[int, int]]
```

Generate a gradual ramp-up pattern.

### spike_test

```python
spike_test(base_users: int, spike_users: int, spike_duration: int, base_duration: int) -> Iterator[Tuple[int, int]]
```

Generate a spike testing pattern.

### constant_load

```python
constant_load(users: int, duration: int) -> Iterator[Tuple[int, int]]
```

Generate a constant load pattern.

**Example:**
```python
from LoadSpiker.utils import ramp_up, spike_test, constant_load

# Gradual ramp-up from 1 to 100 users over 5 minutes
for users, duration in ramp_up(1, 100, 300):
    results = engine.run_scenario(scenario, users, duration)

# Spike test: 20 base users, spike to 100 for 60 seconds
for users, duration in spike_test(20, 100, 60, 120):
    results = engine.run_scenario(scenario, users, duration)

# Constant load of 50 users for 10 minutes
for users, duration in constant_load(50, 600):
    results = engine.run_scenario(scenario, users, duration)
```

## Error Handling

All methods may raise the following exceptions:

- `RuntimeError`: For engine initialization or request execution failures
- `ValueError`: For invalid parameter values
- `ImportError`: If the C extension module cannot be loaded

**Example:**
```python
try:
    engine = Engine(max_connections=1000, worker_threads=10)
    response = engine.execute_request("https://api.example.com/test")
except RuntimeError as e:
    print(f"Engine error: {e}")
except ImportError as e:
    print(f"Module import error: {e}")
```

## Best Practices

### Performance Tips

1. **Connection Pooling**: Use appropriate `max_connections` based on your target server capacity
2. **Worker Threads**: Start with `worker_threads = CPU_cores * 2` and adjust based on testing
3. **Timeout Settings**: Set reasonable timeouts to avoid hanging requests
4. **Memory Management**: Monitor memory usage during long-running tests

### Thread Safety

- Each `Engine` instance is thread-safe
- Multiple threads can call `execute_request()` concurrently
- Metrics are automatically synchronized across threads

### Resource Management

Always clean up resources properly:

```python
try:
    engine = Engine(max_connections=100, worker_threads=4)
    # Run your tests
    results = engine.run_scenario(scenario, users=10, duration=60)
finally:
    # Engine cleanup is handled automatically
    pass
