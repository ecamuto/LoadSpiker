# Changelog

All notable changes to LoadSpiker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Comprehensive Assertion System**: Full-featured assertion framework for response validation
  - Status code assertions (`status_is`, `StatusCodeAssertion`)
  - Response time validation (`response_time_under`, `ResponseTimeAssertion`)
  - Body content checking (`body_contains`, `BodyContainsAssertion`)
  - Regular expression matching (`body_matches`, `RegexAssertion`)
  - JSON path validation (`json_path`, `JSONPathAssertion`)
  - HTTP header verification (`header_exists`, `HeaderAssertion`)
  - Custom assertion support (`custom_assertion`, `CustomAssertion`)
  - Assertion groups with AND/OR logic (`AssertionGroup`)
  - Detailed error reporting with specific failure messages
  - Integration with scenario system for automated testing
- Comprehensive contributing guidelines (CONTRIBUTING.md)
- Debug build configuration with AddressSanitizer support
- Detailed troubleshooting documentation
- Enhanced memory safety in C engine core
- **Real RFC 6455 WebSocket** via libcurl's WebSocket API (`HAVE_CURL_WEBSOCKETS`), GIL released during I/O; simulated fallback where libcurl lacks WS
- **Real PostgreSQL** via libpq (`HAVE_LIBPQ`), **real MySQL/MariaDB** via libmysqlclient (`HAVE_MYSQL`), and **real MongoDB** via libmongoc (`HAVE_MONGOC`, query string is a JSON command document); per-user DB isolation via `conn_id`; each backend degrades to a simulated path when its client lib is absent
- **TLS for TCP and MQTT** via a shared OpenSSL transport (`src/protocols/tls_transport.c`, gated by `HAVE_OPENSSL`): `tcp_connect(..., use_tls=True, tls_verify=...)` and `mqtt_connect(..., use_tls=True, tls_verify=...)` (mqtts); TLS 1.2+, SNI, platform CA store, hostname verification; builds without OpenSSL fail TLS requests with an explicit error instead of degrading silently
- **Dynamic HTTP response buffers**: response bodies/headers grow to the actual response size (previously truncated at 64 KiB / 8 KiB), with a 256 MiB per-response safety cap; `http_response_t` now owns heap buffers released via `http_response_free()`
- C-core ramp-up (`ramp_up_seconds`) with a duration-sustained load model (replaces the Python burst loop)
- AddressSanitizer harness for the MQTT encoders (`make test-asan`, `tests/asan_check.c`)
- Security regression tests (`tests/test_security_regressions.py`) and a GitHub Actions CI workflow
- `Engine.reset_connection_pools()` to clear the process-global protocol pools
- `Engine.capabilities()` runtime capability introspection (per-protocol `real`/`simulated`/`not_implemented` + `tls` bool, derived from the compile-time feature macros), and one-time stderr warnings when a simulated WebSocket or database operation actually executes — synthetic numbers can no longer pass silently for a real load test
- All non-HTTP protocols (TCP/UDP/MQTT/Database) bridged through the Python extension

### Fixed
- Buffer overflow vulnerabilities in HTTP response handling
- Memory leaks in cURL header processing
- Segmentation faults in request execution
- Uninitialized memory access in response buffers
- Thread safety issues in worker queue management
- MQTT packet-encoder stack overflows (over-length CONNECT/PUBLISH/SUBSCRIBE now rejected); CONNACK/SUBACK read-to-length validation
- Double-unlock of the MQTT pool mutex on the successful `mqtt_connect` path (undefined behavior)
- Binary/NUL-safe TCP/UDP sends (length carried instead of `strlen`)
- Per-protocol pool concurrency: mutex narrowed to the slot lookup, blocking I/O outside the lock; per-user TCP/UDP/Database isolation
- Python-layer audit: opt-in CSV type coercion, OAuth2 `state` validation, Bearer token redaction, HTMLReporter `</script>` escaping, CLI config key validation
- Flaky socket tests (process-global pools reset between tests)
- Malformed `requirements.txt` (`pkgconfig>=1.5.0pytest` collapsed onto one line)

### Changed
- Improved error handling throughout C codebase
- Enhanced buffer management with proper bounds checking
- Better string handling with null termination guarantees
- More robust memory allocation with error checking
- Deduplicated protocol pool boilerplate into `src/protocols/pool_common.h`
- Reconciled docs (README, `docs/site/*`, `docs/CODE_ANALYSIS.md`) with the real capability matrix

### Security
- Fixed potential buffer overflows in write_callback function
- Added proper input validation for all C function parameters
- Improved memory initialization to prevent information leaks
- SQL injection is now relevant for real PostgreSQL (`PQexec`): scenarios should use parameterized queries / trusted literals — see `docs/CODE_ANALYSIS.md`

## [1.0.0] - TBD

### Added
- Initial release of LoadSpiker
- High-performance C-based HTTP engine with libcurl
- Python API for easy test scripting
- Multiple load testing patterns (constant, ramp-up, spike)
- Real-time metrics collection and reporting
- Support for multiple report formats (Console, JSON, HTML)
- REST API testing scenarios
- Website testing scenarios with user behavior simulation
- Command-line interface for quick testing
- Multi-threaded request processing
- Connection pooling and reuse
- Comprehensive test examples

### Features
- **Performance**: 10,000+ requests/second capability
- **Concurrency**: Support for thousands of concurrent connections
- **Flexibility**: Python scripting with C performance
- **Reporting**: Multiple output formats with detailed metrics
- **Scenarios**: Built-in support for common testing patterns
- **CLI**: Full-featured command-line interface
- **Configuration**: JSON and Python-based configuration files

### Core Components
- **C Engine**: High-performance HTTP client with async I/O
- **Python Extension**: Seamless integration between Python and C
- **Scenario System**: Flexible test scenario definition
- **Reporting System**: Multiple output formats with rich metrics
- **CLI Interface**: User-friendly command-line tool

### Requirements
- Python 3.7+
- libcurl development headers
- GCC or Clang compiler
- pthread support
- pkg-config

### Supported Platforms
- Linux (Ubuntu, CentOS, Debian)
- macOS (Intel and Apple Silicon)
- Windows (with appropriate build tools)
