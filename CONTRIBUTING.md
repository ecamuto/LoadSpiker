# Contributing to LoadSpiker

Thank you for your interest in contributing to LoadSpiker! This document provides guidelines for contributing to the project.

## Development Setup

### Prerequisites

- GCC or Clang compiler
- Python 3.7+
- libcurl development headers
- pkg-config
- Make

### Setting up the Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd LoadSpiker

# Install system dependencies
make install-deps

# Set up development environment
make dev-setup

# Build the project
make build

# Run tests
make test
```

## Project Structure

```
LoadSpiker/
├── src/                    # C source code
│   ├── engine.c           # Core HTTP engine implementation
│   ├── engine.h           # Engine header definitions
│   └── python_extension.c # Python C extension wrapper
├── loadspiker/            # Python package
│   ├── __init__.py        # Package initialization
│   ├── engine.py          # High-level Python API
│   ├── scenarios.py       # Test scenario definitions
│   ├── reporters.py       # Result reporting
│   └── utils.py           # Utility functions
├── examples/              # Example usage scripts
├── tests/                 # Test suite
└── docs/                  # Documentation
```

## Development Workflow

### 1. Building and Testing

```bash
# Clean previous builds
make clean

# Build the C extension
make build

# Install for testing
make install

# Run the test suite
make test

# Run specific tests
python3 test_simple.py
python3 examples/simple_test.py
```

### 2. Debug Builds

For debugging memory issues and segmentation faults:

```bash
# Build with debug symbols and AddressSanitizer
make debug

# Copy debug build to package
cp obj/loadtest_debug.so loadspiker/loadtest.so

# Run with memory checking (macOS)
DYLD_INSERT_LIBRARIES=/Library/Developer/CommandLineTools/usr/lib/clang/17/lib/darwin/libclang_rt.asan_osx_dynamic.dylib python3 your_test.py

# Run with memory checking (Linux)
ASAN_OPTIONS=abort_on_error=1:halt_on_error=1 python3 your_test.py
```

### 3. Code Style Guidelines

#### C Code Style
- Use 4 spaces for indentation
- Include comprehensive comments for all functions
- Use meaningful variable names
- Check all malloc/calloc return values
- Always initialize pointers to NULL
- Use const correctness where applicable

Example:
```c
/**
 * Allocates and initializes a new HTTP response buffer
 * 
 * @param capacity Maximum buffer size in bytes
 * @return Pointer to initialized buffer, or NULL on allocation failure
 */
static response_buffer_t* create_response_buffer(size_t capacity) {
    response_buffer_t* buffer = malloc(sizeof(response_buffer_t));
    if (!buffer) {
        return NULL;
    }
    
    buffer->data = malloc(capacity);
    if (!buffer->data) {
        free(buffer);
        return NULL;
    }
    
    buffer->size = 0;
    buffer->capacity = capacity;
    buffer->data[0] = '\0';
    
    return buffer;
}
```

#### Python Code Style
- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Include comprehensive docstrings
- Use meaningful variable and function names

Example:
```python
def execute_request(self, url: str, method: str = "GET", 
                   headers: Optional[Dict[str, str]] = None,
                   body: str = "", timeout_ms: int = 30000) -> Dict[str, Any]:
    """
    Execute a single HTTP request
    
    Args:
        url: Target URL for the request
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        headers: Optional HTTP headers as key-value pairs
        body: Request body content
        timeout_ms: Request timeout in milliseconds
        
    Returns:
        Dictionary containing response data with keys:
        - status_code: HTTP status code
        - headers: Response headers
        - body: Response body content
        - response_time_us: Response time in microseconds
        - success: Boolean indicating request success
        - error_message: Error details if request failed
        
    Raises:
        RuntimeError: If the request execution fails
    """
```

## Contributing Process

### 1. Before Starting Work

1. Check existing issues to avoid duplicate work
2. Create an issue to discuss major changes
3. Fork the repository
4. Create a feature branch: `git checkout -b feature/your-feature-name`

### 2. Making Changes

1. Write your code following the style guidelines
2. Add tests for new functionality
3. Update documentation as needed
4. Ensure all tests pass: `make test`
5. Test with both release and debug builds

### 3. Memory Safety (Critical for C Code)

Always check for:
- Buffer overflows and underflows
- Null pointer dereferences
- Memory leaks (ensure every malloc has a corresponding free)
- Use-after-free errors
- Thread safety in multi-threaded code

### 4. Submitting Changes

1. Commit your changes with clear, descriptive messages
2. Push to your fork: `git push origin feature/your-feature-name`
3. Create a pull request with:
   - Clear description of changes
   - Test results
   - Any breaking changes noted

## Testing Guidelines

### Unit Tests
- Test both success and failure cases
- Include edge cases and boundary conditions
- Test with various input sizes and types

### Integration Tests
- Test the full request/response cycle
- Test with real HTTP endpoints
- Test concurrent usage scenarios

### Performance Tests
- Benchmark critical code paths
- Test memory usage under load
- Verify no performance regressions

## Common Issues and Solutions

### Segmentation Faults
- Often caused by uninitialized pointers or buffer overflows
- Use debug builds with AddressSanitizer
- Check all string operations for proper null termination
- Validate all input parameters in C functions

### Memory Leaks
- Every malloc/strdup must have corresponding free
- Clean up cURL handles and resources
- Free dynamically allocated strings

### Thread Safety
- Use proper mutex locking around shared data
- Avoid race conditions in queue operations
- Ensure atomic operations where needed

## Documentation Standards

- Update README.md for user-facing changes
- Add inline comments for complex algorithms
- Update API documentation for new features
- Include usage examples for new functionality

## Release Process

1. Update version numbers
2. Update CHANGELOG.md
3. Run full test suite
4. Create release notes
5. Tag the release

## Getting Help

- Check existing issues and documentation
- Ask questions in pull request discussions
- Refer to the troubleshooting section in README.md

## Code Review Checklist

Before submitting a pull request, ensure:

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] Memory leaks checked (for C code)
- [ ] Documentation updated
- [ ] No compiler warnings
- [ ] Thread safety considered
- [ ] Error handling implemented
- [ ] Input validation added

Thank you for contributing to LoadSpiker!
