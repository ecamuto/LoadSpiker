# LoadSpiker API Documentation

This document provides comprehensive API documentation for LoadSpiker's Python interface.

## Table of Contents

- [Engine](#engine)
- [Scenarios](#scenarios)
- [Assertions](#assertions)
- [Performance Assertions](#performance-assertions)
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

## Performance Assertions

The LoadSpiker performance assertion system provides comprehensive validation of aggregate performance metrics from load testing scenarios. Unlike regular assertions that validate individual responses, performance assertions evaluate overall test performance against defined thresholds.

### Overview

Performance assertions analyze aggregated metrics such as throughput, response times, error rates, and success rates to determine if a load test meets performance requirements. This enables:

- **SLA Validation**: Ensure your application meets service level agreements
- **Performance Regression Detection**: Catch performance degradations early
- **Capacity Planning**: Validate system capacity under load
- **CI/CD Integration**: Automated performance gates in deployment pipelines

### Core Performance Assertion Classes

#### ThroughputAssertion

Validates that the system maintains a minimum throughput (requests per second).

```python
ThroughputAssertion(min_rps: float, message: str = "")
```

**Parameters:**
- `min_rps` (float): Minimum required requests per second
- `message` (str): Custom error message for assertion failures

**Example:**
```python
from loadspiker.performance_assertions import ThroughputAssertion

# Require at least 100 RPS
throughput_check = ThroughputAssertion(100.0, "System must handle at least 100 RPS")
success = throughput_check.check_metrics(metrics)
```

#### AverageResponseTimeAssertion

Validates that average response time stays below acceptable limits.

```python
AverageResponseTimeAssertion(max_avg_ms: float, message: str = "")
```

**Parameters:**
- `max_avg_ms` (float): Maximum acceptable average response time in milliseconds
- `message` (str): Custom error message for assertion failures

#### ErrorRateAssertion

Validates that error rate stays below acceptable thresholds.

```python
ErrorRateAssertion(max_error_rate: float, message: str = "")
```

**Parameters:**
- `max_error_rate` (float): Maximum acceptable error rate as a percentage (0-100)
- `message` (str): Custom error message for assertion failures

#### SuccessRateAssertion

Validates that success rate meets minimum requirements.

```python
SuccessRateAssertion(min_success_rate: float, message: str = "")
```

**Parameters:**
- `min_success_rate` (float): Minimum required success rate as a percentage (0-100)
- `message` (str): Custom error message for assertion failures

#### MaxResponseTimeAssertion

Validates that maximum response time stays below acceptable limits.

```python
MaxResponseTimeAssertion(max_time_ms: float, message: str = "")
```

**Parameters:**
- `max_time_ms` (float): Maximum acceptable response time in milliseconds
- `message` (str): Custom error message for assertion failures

#### TotalRequestsAssertion

Validates that a minimum number of requests were processed (useful for ensuring test completion).

```python
TotalRequestsAssertion(min_requests: int, message: str = "")
```

**Parameters:**
- `min_requests` (int): Minimum required number of total requests
- `message` (str): Custom error message for assertion failures

#### CustomPerformanceAssertion

Allows custom performance validation logic using user-defined functions.

```python
CustomPerformanceAssertion(assertion_func: Callable[[Dict[str, Any]], bool], message: str = "")
```

**Parameters:**
- `assertion_func` (Callable): Function that takes metrics dict and returns bool
- `message` (str): Custom error message for assertion failures

**Example:**
```python
from loadspiker.performance_assertions import CustomPerformanceAssertion

def check_performance_ratio(metrics):
    """Custom assertion: Check if RPS to avg response time ratio is acceptable"""
    rps = metrics.get('requests_per_second', 0.0)
    avg_time = metrics.get('avg_response_time_ms', 0.0)
    if avg_time == 0:
        return True
    ratio = rps / avg_time
    return ratio > 0.1  # At least 0.1 RPS per ms of response time

ratio_assertion = CustomPerformanceAssertion(
    check_performance_ratio,
    "Performance ratio (RPS/avg_response_time) should be > 0.1"
)
```

### Performance Assertion Groups

#### PerformanceAssertionGroup

Groups multiple performance assertions with AND/OR logic for complex validation scenarios.

```python
PerformanceAssertionGroup(logic: str = "AND")
```

**Parameters:**
- `logic` (str): Logic operator ("AND" or "OR")

**Methods:**

##### add

```python
add(assertion: PerformanceAssertion) -> PerformanceAssertionGroup
```

Add a performance assertion to the group.

##### check_all_metrics

```python
check_all_metrics(metrics: Dict[str, Any]) -> bool
```

Check all assertions in the group against metrics according to the logic operator.

##### get_failure_report

```python
get_failure_report() -> str
```

Get detailed failure report for failed assertions.

**Example:**
```python
from loadspiker.performance_assertions import (
    PerformanceAssertionGroup, throughput_at_least, 
    avg_response_time_under, error_rate_below
)

# AND group - all must pass for production readiness
production_ready = PerformanceAssertionGroup("AND")
production_ready.add(throughput_at_least(50.0, "Must handle 50+ RPS"))
production_ready.add(avg_response_time_under(500.0, "Avg response < 500ms"))
production_ready.add(error_rate_below(1.0, "Error rate < 1%"))

success = production_ready.check_all_metrics(metrics)
if not success:
    print(production_ready.get_failure_report())

# OR group - at least one must pass for basic functionality
basic_functionality = PerformanceAssertionGroup("OR")
basic_functionality.add(throughput_at_least(1.0))
basic_functionality.add(error_rate_below(50.0))
```

### Convenience Functions

LoadSpiker provides convenience functions for creating common performance assertions:

#### throughput_at_least

```python
throughput_at_least(min_rps: float, message: str = "") -> ThroughputAssertion
```

Create a throughput assertion.

#### avg_response_time_under

```python
avg_response_time_under(max_ms: float, message: str = "") -> AverageResponseTimeAssertion
```

Create an average response time assertion.

#### error_rate_below

```python
error_rate_below(max_rate: float, message: str = "") -> ErrorRateAssertion
```

Create an error rate assertion.

#### success_rate_at_least

```python
success_rate_at_least(min_rate: float, message: str = "") -> SuccessRateAssertion
```

Create a success rate assertion.

#### max_response_time_under

```python
max_response_time_under(max_ms: float, message: str = "") -> MaxResponseTimeAssertion
```

Create a maximum response time assertion.

#### total_requests_at_least

```python
total_requests_at_least(min_requests: int, message: str = "") -> TotalRequestsAssertion
```

Create a total requests assertion.

#### custom_performance_assertion

```python
custom_performance_assertion(func: Callable[[Dict[str, Any]], bool], message: str = "") -> CustomPerformanceAssertion
```

Create a custom performance assertion.

### Running Performance Assertions

#### run_performance_assertions

```python
run_performance_assertions(
    metrics: Dict[str, Any], 
    assertions: List[PerformanceAssertion], 
    fail_fast: bool = True
) -> Tuple[bool, List[str]]
```

Run a list of performance assertions against metrics.

**Parameters:**
- `metrics` (Dict[str, Any]): Performance metrics dictionary from load test
- `assertions` (List[PerformanceAssertion]): List of performance assertions to check
- `fail_fast` (bool): Stop on first failure if True

**Returns:**
- Tuple of (success: bool, failure_messages: List[str])

### Complete Example

Here's a comprehensive example showing how to use performance assertions with load testing:

```python
from loadspiker import Engine, Scenario
from loadspiker.performance_assertions import (
    throughput_at_least, avg_response_time_under, error_rate_below,
    success_rate_at_least, max_response_time_under, total_requests_at_least,
    PerformanceAssertionGroup, run_performance_assertions
)

# Create engine and scenario
engine = Engine(max_connections=100, worker_threads=8)
scenario = Scenario("API Performance Test")
scenario.get("https://api.example.com/users")
scenario.post("https://api.example.com/users", body='{"name": "Test User"}')

# Run load test
print("Running load test...")
results = engine.run_scenario(scenario, users=50, duration=120)

# Define performance requirements
performance_requirements = [
    throughput_at_least(10.0, "Must handle at least 10 requests per second"),
    avg_response_time_under(1000.0, "Average response time must be under 1 second"),
    max_response_time_under(5000.0, "Maximum response time must be under 5 seconds"),
    error_rate_below(5.0, "Error rate must be below 5%"),
    success_rate_at_least(95.0, "Success rate must be at least 95%"),
    total_requests_at_least(100, "Test must process at least 100 requests")
]

# Check performance requirements
print("\nValidating performance requirements...")
success, failures = run_performance_assertions(results, performance_requirements)

if success:
    print("✅ All performance requirements met!")
    print(f"Throughput: {results['requests_per_second']:.2f} RPS")
    print(f"Average Response Time: {results['avg_response_time_ms']:.2f}ms")
    print(f"Error Rate: {(results['failed_requests']/results['total_requests']*100):.2f}%")
else:
    print("❌ Performance requirements not met:")
    for failure in failures:
        print(f"  - {failure}")

# Advanced example with assertion groups
print("\nChecking production readiness...")

# Production-ready criteria (all must pass)
production_criteria = PerformanceAssertionGroup("AND")
production_criteria.add(throughput_at_least(25.0, "Production needs 25+ RPS"))
production_criteria.add(avg_response_time_under(500.0, "Production needs <500ms avg"))
production_criteria.add(error_rate_below(1.0, "Production needs <1% errors"))

# Basic functionality criteria (at least one must pass)
basic_criteria = PerformanceAssertionGroup("OR")
basic_criteria.add(throughput_at_least(1.0, "Basic: at least 1 RPS"))
basic_criteria.add(success_rate_at_least(50.0, "Basic: at least 50% success"))

prod_ready = production_criteria.check_all_metrics(results)
basic_working = basic_criteria.check_all_metrics(results)

print(f"Production Ready: {'✅' if prod_ready else '❌'}")
print(f"Basic Functionality: {'✅' if basic_working else '❌'}")

if not prod_ready:
    print("\nProduction readiness issues:")
    print(production_criteria.get_failure_report())
```

### Metrics Dictionary Format

Performance assertions expect metrics in the following format:

```python
metrics = {
    'total_requests': int,           # Total number of requests made
    'successful_requests': int,      # Number of successful requests (2xx/3xx status)
    'failed_requests': int,          # Number of failed requests (4xx/5xx/timeouts)
    'requests_per_second': float,    # Current throughput (RPS)
    'avg_response_time_ms': float,   # Average response time in milliseconds
    'max_response_time_us': int,     # Maximum response time in microseconds
    'min_response_time_us': int      # Minimum response time in microseconds (optional)
}
```

### Best Practices

#### Setting Realistic Thresholds

1. **Baseline Testing**: Run initial tests to understand current performance
2. **SLA Alignment**: Set thresholds based on actual SLA requirements
3. **Environment Considerations**: Adjust thresholds for test vs production environments
4. **Gradual Tightening**: Start with loose thresholds and tighten over time

#### Combining Assertions

```python
# Common patterns for different scenarios

# High-performance API requirements
api_performance = [
    throughput_at_least(100.0),
    avg_response_time_under(200.0),
    error_rate_below(0.1),
    max_response_time_under(1000.0)
]

# Basic web application requirements
web_performance = [
    throughput_at_least(10.0),
    avg_response_time_under(2000.0),
    error_rate_below(5.0),
    success_rate_at_least(95.0)
]

# Stress test validation (ensuring graceful degradation)
stress_test_validation = [
    error_rate_below(20.0),  # Allow higher error rates under stress
    total_requests_at_least(1000),  # Ensure test actually ran
    # Custom assertion for graceful degradation
    custom_performance_assertion(
        lambda m: m.get('avg_response_time_ms', 0) < m.get('max_response_time_us', 0) / 1000 * 2,
        "Average response time should not be too close to maximum"
    )
]
```

#### CI/CD Integration

```python
# Example for CI/CD pipeline integration
def validate_deployment_performance():
    """Performance gate for deployment pipeline"""
    
    # Run smoke test
    results = run_smoke_test()
    
    # Define deployment criteria
    deployment_gate = [
        throughput_at_least(5.0, "Deployment: minimum 5 RPS"),
        avg_response_time_under(3000.0, "Deployment: avg response < 3s"),
        error_rate_below(10.0, "Deployment: error rate < 10%"),
        success_rate_at_least(90.0, "Deployment: success rate >= 90%")
    ]
    
    success, failures = run_performance_assertions(results, deployment_gate)
    
    if not success:
        print("🚫 Deployment blocked due to performance issues:")
        for failure in failures:
            print(f"   {failure}")
        return False
    
    print("✅ Performance gate passed - deployment approved")
    return True
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

## Testing

### Comprehensive Test Suite

LoadSpiker includes an exhaustive pytest-based test suite for performance assertions with **99 comprehensive tests** covering all functionality:

#### Running Tests
```bash
# Install pytest (if not already installed)
pip install pytest

# Run the complete performance assertion test suite
python -m pytest tests/test_performance_assertions.py -v

# Expected output: 99 tests passed
```

#### Test Coverage
- **Base Class Testing (6 tests)**: Initialization, error handling, abstract methods
- **Individual Assertion Testing (42 tests)**: All 7 assertion types with pass/fail scenarios
- **Group Logic Testing (10 tests)**: AND/OR logic, chaining, failure reporting
- **Convenience Functions Testing (7 tests)**: Helper function validation
- **Batch Processing Testing (6 tests)**: `run_performance_assertions` with various options
- **Edge Cases Testing (6 tests)**: Large/small numbers, None values, float precision
- **Integration Scenarios Testing (6 tests)**: Real-world use cases and workflows

#### Test Categories

**Regression Testing**: Protects against future code changes
**Production Scenarios**: SLA validation, deployment gates, stress testing
**Error Handling**: None values, missing keys, invalid inputs
**Performance**: Boundary conditions, edge cases

The test suite serves as both validation and executable documentation, demonstrating proper usage patterns and expected behaviors for all performance assertion features.

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
