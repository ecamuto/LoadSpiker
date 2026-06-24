from setuptools import setup, Extension
import subprocess
import sys
import os


# =============================================================================
# Build Configuration
# =============================================================================

# Debug mode: Set LOADSPIKER_DEBUG=1 to build with debug symbols
DEBUG_MODE = os.environ.get('LOADSPIKER_DEBUG', '0') == '1'

# Verbose mode: Set LOADSPIKER_VERBOSE=1 for detailed build output
VERBOSE_MODE = os.environ.get('LOADSPIKER_VERBOSE', '0') == '1'


# =============================================================================
# Dependency Checking
# =============================================================================

def check_pkg_config_available():
    """Check if pkg-config is available on the system"""
    try:
        subprocess.check_output(['pkg-config', '--version'], stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_libcurl_available():
    """Check if libcurl is available via pkg-config"""
    try:
        subprocess.check_output(['pkg-config', '--exists', 'libcurl'], stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_dependencies():
    """
    Check for required system dependencies and provide helpful error messages.
    
    This function validates that all required build dependencies are available
    before attempting compilation.
    """
    errors = []
    warnings = []
    
    # Check for pkg-config
    if not check_pkg_config_available():
        warnings.append(
            "pkg-config not found. Using fallback configuration.\n"
            "   Install with:\n"
            "     - macOS:  brew install pkg-config\n"
            "     - Ubuntu: sudo apt-get install pkg-config\n"
            "     - CentOS: sudo yum install pkgconfig"
        )
    else:
        # Check for libcurl (only if pkg-config is available)
        if not check_libcurl_available():
            errors.append(
                "libcurl not found. This is a required dependency.\n"
                "   Install with:\n"
                "     - macOS:  brew install curl\n"
                "     - Ubuntu: sudo apt-get install libcurl4-openssl-dev\n"
                "     - CentOS: sudo yum install libcurl-devel"
            )
    
    # Print warnings
    if warnings and VERBOSE_MODE:
        print("\n⚠️  Build Warnings:")
        for warning in warnings:
            print(f"   {warning}\n")
    
    # Print errors and exit if any
    if errors:
        print("\n❌ Missing Dependencies:")
        for error in errors:
            print(f"   {error}\n")
        print("Please install the missing dependencies and try again.")
        print("Or run: make install-deps")
        sys.exit(1)
    
    if VERBOSE_MODE:
        print("✅ All dependencies found")


def get_pkg_config_flags(package):
    """
    Get compiler and linker flags from pkg-config with intelligent fallback.
    
    Args:
        package: Name of the package (e.g., 'libcurl')
        
    Returns:
        Tuple of (cflags, libs) lists
    """
    try:
        cflags = subprocess.check_output(
            ['pkg-config', '--cflags', package],
            stderr=subprocess.DEVNULL
        ).decode().strip().split()
        libs = subprocess.check_output(
            ['pkg-config', '--libs', package],
            stderr=subprocess.DEVNULL
        ).decode().strip().split()
        
        if VERBOSE_MODE:
            print(f"📦 {package} found via pkg-config")
            print(f"   CFLAGS: {' '.join(cflags)}")
            print(f"   LIBS:   {' '.join(libs)}")
        
        return cflags, libs
    except (subprocess.CalledProcessError, FileNotFoundError):
        if VERBOSE_MODE:
            print(f"⚠️  {package}: using fallback configuration")
        
        # Platform-specific fallbacks
        if package == 'libcurl':
            if sys.platform == 'darwin':
                # macOS with Homebrew
                homebrew_prefix = os.environ.get('HOMEBREW_PREFIX', '/opt/homebrew')
                return (
                    [f'-I{homebrew_prefix}/include'],
                    [f'-L{homebrew_prefix}/lib', '-lcurl']
                )
            elif sys.platform.startswith('linux'):
                # Linux standard paths
                return ['-I/usr/include'], ['-lcurl']
            else:
                # Generic fallback
                return [], ['-lcurl']
        
        return [], []


# =============================================================================
# Check dependencies before proceeding
# =============================================================================

check_dependencies()


# =============================================================================
# Optional feature detection (real WebSocket via libcurl, real PostgreSQL)
# =============================================================================

def _run(cmd):
    """Run a command, return stripped stdout or None on failure."""
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _curl_config_bin():
    """Prefer Homebrew's curl-config (WS-capable) over the system one."""
    candidates = [
        os.path.join(os.environ.get('HOMEBREW_PREFIX', '/opt/homebrew'),
                     'opt', 'curl', 'bin', 'curl-config'),
        'curl-config',
    ]
    for c in candidates:
        if _run([c, '--version']):
            return c
    return None


def get_curl_flags():
    """Return (cflags, libs, has_websockets).

    Uses curl-config (preferring Homebrew's, which ships the WebSocket API)
    and falls back to pkg-config. has_websockets is True when libcurl >= 7.86,
    where curl_ws_send/curl_ws_recv became available.
    """
    cc = _curl_config_bin()
    if cc:
        cflags = (_run([cc, '--cflags']) or '').split()
        libs = (_run([cc, '--libs']) or '-lcurl').split()
        version = _run([cc, '--version']) or ''        # e.g. "libcurl 8.20.0"
        has_ws = False
        try:
            nums = version.split()[-1].split('.')
            major, minor = int(nums[0]), int(nums[1])
            has_ws = (major, minor) >= (7, 86)
        except (ValueError, IndexError):
            has_ws = False
        if VERBOSE_MODE:
            print(f"📦 libcurl via {cc}: {version} (websockets={has_ws})")
        return cflags, libs, has_ws
    # Fallback to the pkg-config path (no WS guarantee)
    cflags, libs = get_pkg_config_flags('libcurl')
    return cflags, libs, False


def get_libpq_flags():
    """Return (include_dirs, libs) for libpq, or ([], []) if not found.

    Prefers Homebrew's keg-only pg_config; falls back to pg_config on PATH.
    """
    candidates = [
        os.path.join(os.environ.get('HOMEBREW_PREFIX', '/opt/homebrew'),
                     'opt', 'libpq', 'bin', 'pg_config'),
        'pg_config',
    ]
    for pg in candidates:
        incdir = _run([pg, '--includedir'])
        libdir = _run([pg, '--libdir'])
        if incdir and libdir and os.path.exists(os.path.join(incdir, 'libpq-fe.h')):
            if VERBOSE_MODE:
                print(f"📦 libpq via {pg}: include={incdir} lib={libdir}")
            return [incdir], [f'-L{libdir}', '-lpq']
    if VERBOSE_MODE:
        print("ℹ️  libpq not found — PostgreSQL support will be simulated")
    return [], []


# =============================================================================
# Compiler Configuration
# =============================================================================

# Get curl flags (and whether the WebSocket API is available)
curl_cflags, curl_libs, curl_has_ws = get_curl_flags()

# Get libpq flags (optional — enables real PostgreSQL when present)
libpq_include_dirs, libpq_libs = get_libpq_flags()

# Warning flags - catch common bugs at compile time
WARNING_FLAGS = [
    '-Wall',                              # Enable all common warnings
    '-Wextra',                            # Enable extra warnings
    '-Werror=implicit-function-declaration',  # Error on missing declarations
    '-Werror=return-type',                # Error on missing return statements
    '-Wno-unused-parameter',              # Allow unused params (common in callbacks)
]

# Platform-specific warning flags
if sys.platform == 'darwin':
    WARNING_FLAGS.append('-Wno-deprecated-declarations')  # macOS SDK deprecations

# Build configuration based on debug mode
if DEBUG_MODE:
    print("🐛 Building in DEBUG mode")
    OPTIMIZATION_FLAGS = ['-g', '-O0', '-DDEBUG']
    LINK_FLAGS = ['-g']
else:
    OPTIMIZATION_FLAGS = ['-O2', '-DNDEBUG']
    LINK_FLAGS = []

# Combine all compile arguments
extra_compile_args = (
    curl_cflags + 
    OPTIMIZATION_FLAGS + 
    WARNING_FLAGS + 
    ['-pthread', '-std=c11']
)

# Combine all link arguments
extra_link_args = curl_libs + libpq_libs + LINK_FLAGS + ['-pthread']

# Feature macros consumed by the C sources via #ifdef
feature_macros = [('_GNU_SOURCE', None)]
if curl_has_ws:
    feature_macros.append(('HAVE_CURL_WEBSOCKETS', '1'))
if libpq_libs:
    feature_macros.append(('HAVE_LIBPQ', '1'))

if VERBOSE_MODE:
    print(f"🔧 Compile flags: {' '.join(extra_compile_args)}")
    print(f"🔗 Link flags: {' '.join(extra_link_args)}")


# =============================================================================
# Extension Module Definition
# =============================================================================

loadspiker_c_extension = Extension(
    'loadspiker.loadspiker_c',
    sources=[
        'src/python_extension.c',
        'src/engine.c',
        'src/protocols/tcp.c',
        'src/protocols/udp.c', 
        'src/protocols/mqtt.c',
        'src/protocols/database.c',
        'src/protocols/websocket.c'
    ],
    include_dirs=['src', 'src/protocols'] + libpq_include_dirs,
    extra_compile_args=extra_compile_args,
    extra_link_args=extra_link_args,
    define_macros=feature_macros
)

setup(
    name='loadspiker',
    version='1.0.0',
    license='MIT',
    description='High-performance load testing tool with C engine and Python scripting',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='LoadSpiker Team',
    author_email='team@loadspiker.com',
    url='https://github.com/loadspiker/loadspiker',
    packages=['loadspiker'],
    ext_modules=[loadspiker_c_extension],
    scripts=['cli.py'],
    entry_points={
        'console_scripts': [
            'loadspiker=cli:main',
        ],
    },
    install_requires=[
        'pkgconfig',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: C',
        'Topic :: Software Development :: Testing',
        'Topic :: System :: Benchmark',
    ],
    python_requires='>=3.7',
    keywords='load testing performance benchmark http',
)
