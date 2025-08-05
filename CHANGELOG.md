# Changelog

All notable changes to LoadSpiker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive contributing guidelines (CONTRIBUTING.md)
- Debug build configuration with AddressSanitizer support
- Detailed troubleshooting documentation
- Enhanced memory safety in C engine core

### Fixed
- Buffer overflow vulnerabilities in HTTP response handling
- Memory leaks in cURL header processing
- Segmentation faults in request execution
- Uninitialized memory access in response buffers
- Thread safety issues in worker queue management

### Changed
- Improved error handling throughout C codebase
- Enhanced buffer management with proper bounds checking
- Better string handling with null termination guarantees
- More robust memory allocation with error checking

### Security
- Fixed potential buffer overflows in write_callback function
- Added proper input validation for all C function parameters
- Improved memory initialization to prevent information leaks

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
