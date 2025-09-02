# LoadSpiker API Documentation

This document provides comprehensive API documentation for LoadSpiker's Python interface.

## Table of Contents

- [Engine](#engine)
- [Session Management](#session-management)
- [Authentication](#authentication)
- [Scenarios](#scenarios)
- [Assertions](#assertions)
- [Performance Assertions](#performance-assertions)
- [Reporters](#reporters)
- [Utilities](#utilities)

## Engine

The `Engine` class is the core component for executing load tests with multi-protocol support.

### Constructor

```python
Engine(max_connections: int = 1000, worker_threads: int = 10)
```

**Parameters:**
- `max_connections` (int): Maximum number of concurrent connections (default: 1000)
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

### Database Methods

#### database_connect

```python
database_connect(connection_string: str, db_type: str = "auto") -> Dict[str, Any]
```

Connect to a database for load testing.

**Parameters:**
- `connection_string` (str): Database connection string (e.g., "mysql://user:pass@host:port/database")
- `db_type` (str): Database type ("mysql", "postgresql", "mongodb", or "auto" to detect from URL)

**Returns:**
Dictionary containing connection response data including success status, response time, and connection details.

### MQTT Methods

LoadSpiker provides comprehensive MQTT (Message Queuing Telemetry Transport) protocol support for testing message queue systems, IoT applications, and publish-subscribe architectures.

#### mqtt_connect

```python
mqtt_connect(
    broker_host: str, 
    broker_port: int = 1883,
    client_id: str = "loadspiker_client",
    username: str = None,
    password: str = None,
    keep_alive: int = 60
) -> Dict[str, Any]
```

Connect to an MQTT broker for load testing.

#### mqtt_publish

```python
mqtt_publish(
    broker_host: str,
    broker_port: int = 1883,
    client_id: str = "loadspiker_client", 
    topic: str = "",
    payload: str = "",
    qos: int = 0,
    retain: bool = False
) -> Dict[str, Any]
```

Publish a message to an MQTT topic.

### TCP/UDP Methods

LoadSpiker includes comprehensive TCP and UDP socket testing capabilities for network protocol testing.

## Session Management

LoadSpiker provides comprehensive session management capabilities for handling stateful HTTP interactions, cookies, tokens, and request correlation. This enables advanced load testing scenarios that require maintaining state across multiple requests, similar to real user behavior.

### Overview

The session management system provides:

- **Thread-Safe Session Storage**: Isolated session state per virtual user
- **Automatic Cookie Handling**: Set-Cookie headers automatically processed and sent
- **Token Management**: Bearer tokens, API keys, and custom tokens with expiration tracking
- **Request Correlation**: Extract values from responses for use in subsequent requests
- **Multi-User Isolation**: Complete separation of session data between virtual users

### SessionManager

The central class for managing user sessions and state.

```python
from loadspiker.session_manager import get_session_manager

session_manager = get_session_manager()
```

#### Methods

##### get_session

```python
get_session(user_id: Union[str, int]) -> SessionStore
```

Get or create a session for a specific user.

**Parameters:**
- `user_id` (Union[str, int]): Unique identifier for the user/session

**Returns:**
- `SessionStore`: Session storage object for the user

##### prepare_request_headers

```python
prepare_request_headers(user_id: Union[str, int], base_headers: Dict[str, str] = None) -> Dict[str, str]
```

Prepare HTTP headers including session cookies and authentication tokens.

##### auto_handle_cookies

```python
auto_handle_cookies(user_id: Union[str, int], response: Dict[str, Any]) -> None
```

Automatically extract and store cookies from response headers.

##### process_response

```python
process_response(user_id: Union[str, int], response: Dict[str, Any], extract_rules: List[Dict[str, str]] = None) -> None
```

Process response and extract values according to correlation rules.

### SessionStore

Individual session storage for a user, providing thread-safe access to cookies, tokens, and custom data.

#### Methods

##### set/get

```python
set(key: str, value: Any) -> None
get(key: str, default: Any = None) -> Any
```

Store and retrieve arbitrary session data.

##### set_token/get_token

```python
set_token(token_type: str, token_value: str, expires_at: float = None) -> None
get_token(token_type: str) -> str
```

Manage authentication tokens with optional expiration.

##### set_cookie/get_cookie

```python
set_cookie(name: str, value: str, domain: str = "", path: str = "/") -> None
get_cookie(name: str) -> str
```

Manage HTTP cookies.

### Session Management Example

```python
from loadspiker import Engine
from loadspiker.session_manager import get_session_manager

engine = Engine()
session_manager = get_session_manager()

# Simulate login request that returns session cookie and user data
login_response = engine.execute_request(
    url="https://api.example.com/login",
    method="POST",
    headers={"Content-Type": "application/json"},
    body='{"username": "testuser", "password": "testpass"}'
)

# Auto-handle cookies from login response
session_manager.auto_handle_cookies("user1", login_response)

# Extract user data using correlation rules
extract_rules = [
    {"type": "json_path", "path": "user.id", "variable": "user_id"},
    {"type": "json_path", "path": "access_token", "variable": "token"},
    {"type": "json_path", "path": "user.profile.email", "variable": "email"}
]

session_manager.process_response("user1", login_response, extract_rules)

# Prepare headers for subsequent request with session data
headers = session_manager.prepare_request_headers("user1", {
    "Content-Type": "application/json"
})

# Make authenticated request using session
profile_response = engine.execute_request(
    url="https://api.example.com/profile",
    method="GET",
    headers=headers  # Includes session cookies and tokens automatically
)

# Access session data
session = session_manager.get_session("user1")
user_id = session.get("user_id")
email = session.get("email")
print(f"User {user_id} with email {email} profile retrieved")
```

### Request Correlation

Request correlation allows extracting values from one response to use in subsequent requests:

```python
# Extract correlation rules
correlation_rules = [
    # Extract from JSON response
    {"type": "json_path", "path": "data.user.id", "variable": "user_id"},
    {"type": "json_path", "path": "pagination.next_page", "variable": "next_page"},
    
    # Extract from headers
    {"type": "header", "name": "X-Request-ID", "variable": "request_id"},
    {"type": "header", "name": "Location", "variable": "created_resource_url"},
    
    # Extract from cookies
    {"type": "cookie", "name": "csrf_token", "variable": "csrf"},
    
    # Extract using regex
    {"type": "regex", "pattern": r'<input name="token" value="([^"]+)"', "variable": "form_token"}
]

# Process response with correlation
session_manager.process_response("user1", response, correlation_rules)

# Use extracted values in next request
session = session_manager.get_session("user1")
user_id = session.get("user_id")
csrf_token = session.get("csrf")

next_response = engine.execute_request(
    url=f"https://api.example.com/users/{user_id}/update",
    method="POST",
    headers=session_manager.prepare_request_headers("user1"),
    body=f'{{"csrf_token": "{csrf_token}", "name": "Updated Name"}}'
)
```

## Authentication

LoadSpiker provides a comprehensive authentication system supporting multiple authentication methods and flows commonly used in enterprise applications and APIs.

### Overview

The authentication system supports:

- **Basic Authentication**: HTTP Basic Auth with username/password
- **Bearer Token Authentication**: JWT, OAuth tokens, API tokens
- **API Key Authentication**: Custom API keys in headers or query parameters
- **Form-Based Authentication**: Traditional login forms with session cookies
- **OAuth 2.0 Flows**: Authorization code flow and client credentials
- **Custom Authentication**: User-defined authentication logic

### AuthenticationManager

Central manager for handling multiple authentication flows.

```python
from loadspiker.authentication import get_authentication_manager

auth_manager = get_authentication_manager()
```

#### Methods

##### register_flow

```python
register_flow(name: str, flow: AuthenticationFlow) -> None
```

Register an authentication flow with a given name.

##### authenticate

```python
authenticate(flow_name: str, engine, user_id: Union[str, int], **kwargs) -> Dict[str, Any]
```

Authenticate using a specific flow.

**Parameters:**
- `flow_name` (str): Name of the registered authentication flow
- `engine`: LoadSpiker engine instance
- `user_id` (Union[str, int]): User identifier
- `**kwargs`: Authentication-specific parameters

**Returns:**
- `Dict[str, Any]`: Authentication result with success status and details

##### is_authenticated

```python
is_authenticated(user_id: Union[str, int], flow_name: str = "") -> bool
```

Check if a user is currently authenticated.

##### logout

```python
logout(user_id: Union[str, int], flow_name: str = "") -> None
```

Logout user from specific flow or all flows.

##### get_auth_headers

```python
get_auth_headers(user_id: Union[str, int]) -> Dict[str, str]
```

Get authentication headers for requests.

### Authentication Flows

#### Basic Authentication

HTTP Basic Authentication using username and password.

```python
from loadspiker.authentication import create_basic_auth

# Create basic auth flow
basic_auth = create_basic_auth("username", "password")
auth_manager.register_flow("basic", basic_auth)

# Authenticate
result = auth_manager.authenticate("basic", engine, user_id="user1")
print(f"Basic auth result: {result}")

# Get auth headers for requests
headers = auth_manager.get_auth_headers("user1")
# headers will include: {'Authorization': 'Basic dXNlcm5hbWU6cGFzc3dvcmQ='}
```

#### Bearer Token Authentication

Support for JWT tokens, OAuth tokens, and other bearer tokens.

```python
from loadspiker.authentication import create_bearer_auth

# Direct token usage
bearer_auth = create_bearer_auth(token="eyJhbGciOiJIUzI1NiIs...")
auth_manager.register_flow("bearer", bearer_auth)

# Token endpoint usage (OAuth client credentials)
bearer_auth = create_bearer_auth(
    token_endpoint="https://auth.example.com/oauth/token",
    client_id="my_client_id",
    client_secret="my_client_secret"
)

# Authenticate with token endpoint
result = auth_manager.authenticate("bearer", engine, user_id="user1", 
                                 grant_type="client_credentials",
                                 scope="read write")
```

#### API Key Authentication

API key authentication via headers or query parameters.

```python
from loadspiker.authentication import create_api_key_auth

# API key in header
api_key_auth = create_api_key_auth("sk-1234567890abcdef", "X-API-Key")
auth_manager.register_flow("api_key", api_key_auth)

# Authenticate
result = auth_manager.authenticate("api_key", engine, user_id="user1")

# Headers will include: {'X-API-Key': 'sk-1234567890abcdef'}
```

#### Form-Based Authentication

Traditional login forms with session cookies.

```python
from loadspiker.authentication import create_form_auth

# Create form auth flow
form_auth = create_form_auth(
    login_url="https://example.com/login",
    username_field="email",
    password_field="password",
    success_indicator="Welcome"  # Text indicating successful login
)
auth_manager.register_flow("form", form_auth)

# Authenticate with credentials
result = auth_manager.authenticate("form", engine, user_id="user1",
                                 username="user@example.com",
                                 password="password123")

# Session cookies are automatically managed
```

#### OAuth 2.0 Authorization Code Flow

OAuth 2.0 authorization code flow (simplified for testing).

```python
from loadspiker.authentication import create_oauth2_auth

# Create OAuth2 flow
oauth2_auth = create_oauth2_auth(
    auth_url="https://auth.example.com/oauth/authorize",
    token_url="https://auth.example.com/oauth/token",
    client_id="my_client_id",
    client_secret="my_client_secret",
    redirect_uri="https://myapp.example.com/callback"
)
auth_manager.register_flow("oauth2", oauth2_auth)

# Generate authorization URL
result = auth_manager.authenticate("oauth2", engine, user_id="user1")
print(f"Visit: {result['authorization_url']}")

# After obtaining authorization code manually
result = auth_manager.authenticate("oauth2", engine, user_id="user1",
                                 authorization_code="abc123def456")
```

#### Custom Authentication

User-defined authentication logic for complex scenarios.

```python
from loadspiker.authentication import create_custom_auth

def my_custom_auth(engine, user_id, session_manager, **kwargs):
    """Custom authentication logic"""
    api_key = kwargs.get('api_key')
    secret = kwargs.get('secret')
    
    # Custom validation logic
    if not api_key or not secret:
        return {'success': False, 'message': 'API key and secret required'}
    
    # Make custom auth request
    auth_response = engine.execute_request(
        url="https://api.example.com/authenticate",
        method="POST",
        headers={"Content-Type": "application/json"},
        body=f'{{"api_key": "{api_key}", "secret": "{secret}"}}'
    )
    
    if auth_response.get('status_code') == 200:
        # Extract token from response
        import json
        data = json.loads(auth_response.get('body', '{}'))
        token = data.get('access_token')
        
        # Store in session
        session = session_manager.get_session(user_id)
        session.set_token('custom', token)
        
        return {
            'success': True,
            'auth_type': 'custom',
            'message': 'Custom authentication successful'
        }
    else:
        return {'success': False, 'message': 'Authentication failed'}

# Create custom auth flow
custom_auth = create_custom_auth(my_custom_auth)
auth_manager.register_flow("custom", custom_auth)

# Authenticate
result = auth_manager.authenticate("custom", engine, user_id="user1",
                                 api_key="my_api_key",
                                 secret="my_secret")
```

### Complete Authentication Example

```python
from loadspiker import Engine
from loadspiker.authentication import (
    get_authentication_manager, create_basic_auth, create_bearer_auth,
    create_api_key_auth, create_form_auth
)

engine = Engine()
auth_manager = get_authentication_manager()

# Register multiple authentication methods
auth_manager.register_flow("basic", create_basic_auth("user", "pass"))
auth_manager.register_flow("api_key", create_api_key_auth("sk-123", "X-API-Key"))
auth_manager.register_flow("form", create_form_auth("https://app.com/login"))

# Test different authentication methods
for user_id, auth_method in [("user1", "basic"), ("user2", "api_key"), ("user3", "form")]:
    if auth_method == "form":
        result = auth_manager.authenticate(auth_method, engine, user_id,
                                         username="testuser", password="testpass")
    else:
        result = auth_manager.authenticate(auth_method, engine, user_id)
    
    print(f"{user_id} authenticated with {auth_method}: {result['success']}")
    
    # Make authenticated request
    if result['success']:
        headers = auth_manager.get_auth_headers(user_id)
        response = engine.execute_request(
            url="https://api.example.com/protected",
            headers=headers
        )
        print(f"Protected resource access: {response['status_code']}")
```

### Integration with Engine

When session management and authentication are available, the LoadSpiker engine automatically integrates them:

```python
from loadspiker import Engine

engine = Engine()

# Check if session management is available
if hasattr(engine._engine, 'session_manager') and engine._engine.session_manager:
    print("Session management is integrated")
    
    # Session manager is automatically used for request preparation
    # and response processing when available

if hasattr(engine._engine, 'auth_manager') and engine._engine.auth_manager:
    print("Authentication manager is integrated")
    
    # Authentication flows can be used directly with the engine
```

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

#### ResponseTimeAssertion

Validates response time is within acceptable limits.

```python
ResponseTimeAssertion(max_time_ms: int, message: str = "")
```

#### JSONPathAssertion

Validates JSON responses using JSONPath-like syntax.

```python
JSONPathAssertion(path: str, expected_value: Any = None, exists: bool = True, message: str = "")
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

#### json_path

```python
json_path(path: str, expected_value: Any = None, exists: bool = True, message: str = "") -> JSONPathAssertion
```

Create a JSON path assertion.

### Running Assertions

#### run_assertions

```python
run_assertions(response: Dict[str, Any], assertions: List[Assertion], fail_fast: bool = True) -> Tuple[bool, List[str]]
```

Run a list of assertions against a response.

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

## Performance Assertions

The LoadSpiker performance assertion system provides comprehensive validation of aggregate performance metrics from load testing scenarios.

### Overview

Performance assertions analyze aggregated metrics such as throughput, response times, error rates, and success rates to determine if a load test meets performance requirements.

### Core Performance Assertion Classes

#### ThroughputAssertion

Validates that the system maintains a minimum throughput (requests per second).

```python
ThroughputAssertion(min_rps: float, message: str = "")
```

#### AverageResponseTimeAssertion

Validates that average response time stays below acceptable limits.

```python
AverageResponseTimeAssertion(max_avg_ms: float, message: str = "")
```

#### ErrorRateAssertion

Validates that error rate stays below acceptable thresholds.

```python
ErrorRateAssertion(max_error_rate: float, message: str = "")
```

### Convenience Functions

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

### Complete Example

```python
from loadspiker import Engine, Scenario
from loadspiker.performance_assertions import (
    throughput_at_least, avg_response_time_under, error_rate_below,
    run_performance_assertions
)

# Create engine and scenario
engine = Engine(max_connections=100, worker_threads=8)
scenario = Scenario("API Performance Test")
scenario.get("https://api.example.com/users")

# Run load test
results = engine.run_scenario(scenario, users=50, duration=120)

# Define performance requirements
performance_requirements = [
    throughput_at_least(10.0, "Must handle at least 10 requests per second"),
    avg_response_time_under(1000.0, "Average response time must be under 1 second"),
    error_rate_below(5.0, "Error rate must be below 5%")
]

# Check performance requirements
success, failures = run_performance_assertions(results, performance_requirements)

if success:
    print("✅ All performance requirements met!")
else:
    print("❌ Performance requirements not met:")
    for failure in failures:
        print(f"  - {failure}")
```

## Reporters

Classes for generating test reports in various formats.

### ConsoleReporter

Real-time console output during test execution.

```python
ConsoleReporter(show_progress: bool = True)
```

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

## Error Handling

All methods may raise the following exceptions:

- `RuntimeError`: For engine initialization or request execution failures
- `ValueError`: For invalid parameter values
- `ImportError`: If the C extension module cannot be loaded

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

### Session Management Best Practices

1. **Session Isolation**: Use unique user IDs for each virtual user to maintain proper session isolation
2. **Cookie Management**: Let LoadSpiker handle cookies automatically, only manually manage when necessary
3. **Token Expiration**: Monitor token expiration times and refresh when needed
4. **Request Correlation**: Use correlation rules to extract dynamic values for realistic testing

### Authentication Best Practices

1. **Authentication Flow Selection**: Choose the appropriate authentication method based on your application
2. **Token Management**: Store sensitive tokens securely and use proper expiration handling
3. **Multi-User Testing**: Test with multiple authentication scenarios to simulate real user behavior
4. **Session Validation**: Verify authentication state before making protected requests
