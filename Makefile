.PHONY: build install clean test example docs

# Build configuration
CC = gcc
CFLAGS = -O3 -Wall -Wextra -pthread -fPIC
DEBUG_CFLAGS = -g -O0 -Wall -Wextra -pthread -fPIC -fsanitize=address -fno-omit-frame-pointer
CURL_CFLAGS = $(shell pkg-config --cflags libcurl)
CURL_LIBS = $(shell pkg-config --libs libcurl)
PYTHON_INCLUDES = $(shell python3-config --includes)
PYTHON_LIBS = $(shell python3-config --ldflags --embed)

# Directories
SRC_DIR = src
BUILD_DIR = obj
EXAMPLE_DIR = examples

# Source files
ENGINE_SOURCES = $(SRC_DIR)/engine.c $(SRC_DIR)/protocols/websocket.c
EXTENSION_SOURCES = $(SRC_DIR)/python_extension.c
ALL_SOURCES = $(ENGINE_SOURCES) $(EXTENSION_SOURCES)

# Build targets
ENGINE_OBJ = $(BUILD_DIR)/engine.o
WEBSOCKET_OBJ = $(BUILD_DIR)/websocket.o
EXTENSION_OBJ = $(BUILD_DIR)/python_extension.o
LOADSPIKER_SO = $(BUILD_DIR)/loadspiker.so
DEBUG_ENGINE_OBJ = $(BUILD_DIR)/engine_debug.o
DEBUG_WEBSOCKET_OBJ = $(BUILD_DIR)/websocket_debug.o
DEBUG_EXTENSION_OBJ = $(BUILD_DIR)/python_extension_debug.o
DEBUG_LOADSPIKER_SO = $(BUILD_DIR)/loadspiker_debug.so

# Default target
all: build

# Create build directory
$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

# Compile engine
$(ENGINE_OBJ): $(SRC_DIR)/engine.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CURL_CFLAGS) -c $< -o $@

# Compile WebSocket protocol
$(WEBSOCKET_OBJ): $(SRC_DIR)/protocols/websocket.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

# Compile Python extension
$(EXTENSION_OBJ): $(EXTENSION_SOURCES) $(SRC_DIR)/engine.h | $(BUILD_DIR)
	$(CC) $(CFLAGS) $(CURL_CFLAGS) $(PYTHON_INCLUDES) -c $< -o $@

# Link shared library
$(LOADSPIKER_SO): $(ENGINE_OBJ) $(WEBSOCKET_OBJ) $(EXTENSION_OBJ)
	$(CC) -shared $(ENGINE_OBJ) $(WEBSOCKET_OBJ) $(EXTENSION_OBJ) $(CURL_LIBS) $(PYTHON_LIBS) -o $(LOADSPIKER_SO)

# Build everything
build: $(LOADSPIKER_SO)
	@echo "✅ Build completed successfully"
	@echo "📦 Extension: $(LOADSPIKER_SO)"

# Debug build targets
$(DEBUG_ENGINE_OBJ): $(SRC_DIR)/engine.c | $(BUILD_DIR)
	$(CC) $(DEBUG_CFLAGS) $(CURL_CFLAGS) -c $< -o $@

$(DEBUG_WEBSOCKET_OBJ): $(SRC_DIR)/protocols/websocket.c | $(BUILD_DIR)
	$(CC) $(DEBUG_CFLAGS) -c $< -o $@

$(DEBUG_EXTENSION_OBJ): $(EXTENSION_SOURCES) $(SRC_DIR)/engine.h | $(BUILD_DIR)
	$(CC) $(DEBUG_CFLAGS) $(CURL_CFLAGS) $(PYTHON_INCLUDES) -c $< -o $@

$(DEBUG_LOADSPIKER_SO): $(DEBUG_ENGINE_OBJ) $(DEBUG_WEBSOCKET_OBJ) $(DEBUG_EXTENSION_OBJ)
	$(CC) -shared $(DEBUG_ENGINE_OBJ) $(DEBUG_WEBSOCKET_OBJ) $(DEBUG_EXTENSION_OBJ) $(CURL_LIBS) $(PYTHON_LIBS) -fsanitize=address -o $(DEBUG_LOADSPIKER_SO)

# Build debug version
debug: $(DEBUG_LOADSPIKER_SO)
	@echo "🐛 Debug build completed successfully"
	@echo "📦 Debug Extension: $(DEBUG_LOADSPIKER_SO)"
	@echo "⚠️  Run with: ASAN_OPTIONS=abort_on_error=1:halt_on_error=1 python3 your_test.py"

# Install using pip
install: build
	python3 setup_env.py
	@echo "✅ LoadSpiker development environment ready"
	@echo "   Run: source activate_env.sh"
	@echo "   Or:  PYTHONPATH=$(PWD) python3 cli.py --help"

# Install system dependencies
install-deps:
	@echo "🔧 Installing system dependencies..."
	@if command -v apt-get >/dev/null 2>&1; then \
		sudo apt-get update && sudo apt-get install -y libcurl4-openssl-dev python3-dev pkg-config; \
	elif command -v yum >/dev/null 2>&1; then \
		sudo yum install -y libcurl-devel python3-devel pkgconfig; \
	elif command -v brew >/dev/null 2>&1; then \
		brew install curl pkg-config; \
	else \
		echo "❌ Please install libcurl-dev, python3-dev, and pkg-config manually"; \
		exit 1; \
	fi
	@echo "✅ System dependencies installed"

# Clean build artifacts
clean:
	rm -rf $(BUILD_DIR) build dist *.egg-info
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "🧹 Cleaned build artifacts"

# Run tests
test: install
	@echo "🧪 Running tests..."
	python3 -m pytest tests/ -v
	@echo "✅ Tests completed"

# Run example
example: install
	@echo "🚀 Running example..."
	python3 $(EXAMPLE_DIR)/simple_test.py

# Quick test with httpbin
quick-test: install
	@echo "⚡ Running quick test against httpbin.org..."
	PYTHONPATH=$(PWD) python3 cli.py https://httpbin.org/get -u 5 -d 10

# Generate documentation
docs:
	@echo "📚 Generating documentation..."
	@if command -v sphinx-build >/dev/null 2>&1; then \
		cd docs && make html; \
		echo "✅ Documentation generated in docs/_build/html/"; \
	else \
		echo "❌ Sphinx not installed. Run: pip install sphinx"; \
	fi

# Development setup
dev-setup: install-deps
	pip3 install -e .
	pip3 install pytest sphinx
	@echo "🛠️  Development environment ready"

# Package for distribution
package: clean build
	python3 setup.py sdist bdist_wheel
	@echo "📦 Package created in dist/"

# Show help
help:
	@echo "LoadSpiker Build System"
	@echo "======================="
	@echo ""
	@echo "Available targets:"
	@echo "  build       - Build the C extension"
	@echo "  debug       - Build debug version with AddressSanitizer"
	@echo "  install     - Install LoadSpiker"
	@echo "  install-deps- Install system dependencies"
	@echo "  clean       - Clean build artifacts"
	@echo "  test        - Run test suite"
	@echo "  example     - Run example script"
	@echo "  quick-test  - Quick test with httpbin"
	@echo "  docs        - Generate documentation"
	@echo "  dev-setup   - Set up development environment"
	@echo "  package     - Create distribution package"
	@echo "  help        - Show this help"
	@echo ""
	@echo "Examples:"
	@echo "  make install-deps  # Install system dependencies"
	@echo "  make install       # Build and install"
	@echo "  make debug         # Build with debugging enabled"
	@echo "  make quick-test    # Run quick test"
