# LoadSpiker API Documentation

This document provides comprehensive API documentation for LoadSpiker's Python interface.

## Table of Contents

- [Engine](#engine)
- [Scenarios](#scenarios)
- [Assertions](#assertions)
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

## Assertions

The LoadSpiker assertion system provides comprehensive response validation capabilities for load testing scenarios.

### Core Assertion Classes

#### StatusCodeAssertion

Validates HTTP status codes against expected values.

```python
StatusCodeAssertion(expected_status: int, message: str = "")
```

**Parameters:**
- `expected_status` (int): Expected HTTP status code
- `message` (str): Custom error message for assertion failures

**Example:**
```python
from loadspiker.assertions import StatusCodeAssertion

assertion = StatusCodeAssertion(200, "Expected successful response")
success = assertion.check(response)
```

#### ResponseTimeAssertion

Validates response time is within acceptable limits.

```python
ResponseTimeAssertion(max_time_ms: int, message: str = "")
```

**Parameters:**
- `max_time_ms` (int): Maximum acceptable response time in milliseconds
- `message` (str): Custom error message for assertion failures

#### BodyContainsAssertion

Validates that response body contains specific text.

```python
BodyContainsAssertion(expected_text: str, case_sensitive: bool = True, message: str = "")
```

**Parameters:**
- `expected_text` (str): Text that should be present in response body
- `case_sensitive` (bool): Whether search should be case sensitive
- `message` (str): Custom error message for assertion failures

#### RegexAssertion

Validates response body against regular expression patterns.

```python
RegexAssertion(pattern: str, message: str = "")
```

**Parameters:**
- `pattern` (str): Regular expression pattern to match
- `message` (str): Custom error message for assertion failures

#### JSONPathAssertion

Validates JSON responses using JSONPath-like syntax.

```python
JSONPathAssertion(path: str, expected_value: Any = None, exists: bool = True, message: str = "")
```

**Parameters:**
- `path` (str): JSONPath to validate (e.g., "user.name", "items[0].id")
- `expected_value` (Any): Expected value at the path (optional)
- `exists` (bool): Whether the path should exist
- `message` (str): Custom error message for assertion failures

**Example:**
```python
from loadspiker.assertions import JSONPathAssertion

# Check if user.id exists
id_assertion = JSONPathAssertion("user.id", exists=True)

# Check if user.name equals "John"
name_assertion = JSONPathAssertion("user.name", "John")

# Check array element
item_assertion = JSONPathAssertion("items[0].price", 29.99)
```

#### HeaderAssertion

Validates HTTP response headers.

```python
HeaderAssertion(header_name: str, expected_value: str = None, exists: bool = True, message: str = "")
```

**Parameters:**
- `header_name` (str): Name of the header to check
- `expected_value` (str): Expected header value (optional)
- `exists` (bool): Whether the header should exist
- `message` (str): Custom error message for assertion failures

#### CustomAssertion

Allows custom validation logic using user-defined functions.

```python
CustomAssertion(assertion_func: Callable[[Dict[str, Any]], bool], message: str = "")
```

**Parameters:**
- `assertion_func` (Callable): Function that takes response dict and returns bool
- `message` (str): Custom error message for assertion failures

**Example:**
```python
from loadspiker.assertions import CustomAssertion

def check_response_size(response):
    body_size = len(response.get('body', ''))
    return 100 < body_size < 10000

size_assertion = CustomAssertion(check_response_size, "Response size should be reasonable")
```

### Assertion Groups

#### AssertionGroup

Groups multiple assertions with AND/OR logic.

```python
AssertionGroup(logic: str = "AND")
```

**Parameters:**
- `logic` (str): Logic operator ("AND" or "OR")

**Methods:**

##### add

```python
add(assertion: Assertion) -> AssertionGroup
```

Add an assertion to the group.

##### check_all

```python
check_all(response: Dict[str, Any]) -> bool
```

Check all assertions in the group according to the logic operator.

##### get_failure_report

```python
get_failure_report() -> str
```

Get detailed failure report for failed assertions.

**Example:**
```python
from loadspiker.assertions import AssertionGroup, status_is, response_time_under, body_contains

# AND group - all must pass
and_group = AssertionGroup("AND")
and_group.add(status_is(200))
and_group.add(response_time_under(1000))
and_group.add(body_contains("success"))

success = and_group.check_all(response)
if not success:
    print(and_group.get_failure_report())

# OR group - at least one must pass
or_group = AssertionGroup("OR")
or_group.add(status_is(200))
or_group.add(status_is(201))
or_group.add(status_is(202))
```

### Convenience Functions

LoadSpiker provides convenience functions for creating common assertions quickly:

#### status_is

```python
status_is(code: int, message: str = "") -> StatusCodeAssertion
```

Create a status code assertion.

#### response_time_under

```python
response_time_under(max_ms: int, message: str = "") -> ResponseTimeAssertion
```

Create a response time assertion.

#### body_contains

```python
body_contains(text: str, case_sensitive: bool = True, message: str = "") -> BodyContainsAssertion
```

Create a body content assertion.

#### body_matches

```python
body_matches(pattern: str, message: str = "") -> RegexAssertion
```

Create a regex pattern assertion.

#### json_path

```python
json_path(path: str, expected_value: Any = None, exists: bool = True, message: str = "") -> JSONPathAssertion
```

Create a JSON path assertion.

#### header_exists

```python
header_exists(name: str, value: str = None, message: str = "") -> HeaderAssertion
```

Create a header assertion.

#### custom_assertion

```python
custom_assertion(func: Callable[[Dict[str, Any]], bool], message: str = "") -> CustomAssertion
```

Create a custom assertion.

### Running Assertions

#### run_assertions

```python
run_assertions(response: Dict[str, Any], assertions: List[Assertion], fail_fast: bool = True) -> Tuple[bool, List[str]]
```

Run a list of assertions against a response.

**Parameters:**
- `response` (Dict[str, Any]): HTTP response dictionary
- `assertions` (List[Assertion]): List of assertions to check
- `fail_fast` (bool): Stop on first failure if True

**Returns:**
- Tuple of (success: bool, failure_messages: List[str])

**Example:**
```python
from loadspiker import Engine
from loadspiker.assertions import (
    status_is, response_time_under, json_path, body_contains, run_assertions
)

engine = Engine()
response = engine.execute_request("https://api.example.com/users/123")

assertions = [
    status_is(200, "Expected successful response"),
    response_time_under(1000, "Response should be under 1 second"),
    json_path("user.id", 123),
    json_path("user.email", exists=True),
    body_contains("user")
]

success, failures = run_assertions(response, assertions)

if not success:
    print("Assertion failures:")
    for failure in failures:
        print(f"  - {failure}")
else:
    print("All assertions passed!")
```

### Integration with Scenarios

Assertions can be integrated with scenario systems for automated testing:

```python
from loadspiker import Engine, Scenario
from loadspiker.assertions import status_is, json_path, response_time_under

engine = Engine()
scenario = Scenario("User API Test")

# Add requests with assertions to scenario
scenario.get("https://api.example.com/users", assertions=[
    status_is(200),
    response_time_under(500),
    json_path("users", exists=True)
])

scenario.post("https://api.example.com/users", 
              body='{"name": "Test User"}',
              assertions=[
                  status_is(201),
                  json_path("user.id", exists=True),
                  json_path("user.name", "Test User")
              ])

# Run scenario with assertions
results = engine.run_scenario(scenario, users=10, duration=60)
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
