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
# Compiler Configuration
# =============================================================================

# Get curl flags
curl_cflags, curl_libs = get_pkg_config_flags('libcurl')

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
extra_link_args = curl_libs + LINK_FLAGS + ['-pthread']

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
    include_dirs=['src', 'src/protocols'],
    extra_compile_args=extra_compile_args,
    extra_link_args=extra_link_args,
    define_macros=[('_GNU_SOURCE', None)]
)

setup(
    name='loadspiker',
    version='1.0.0',
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
        'License :: OSI Approved :: MIT License',
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
