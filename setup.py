from setuptools import setup, Extension
import subprocess
import sys

def get_pkg_config_flags(package):
    """Get pkg-config flags with fallback"""
    try:
        cflags = subprocess.check_output(['pkg-config', '--cflags', package]).decode().strip().split()
        libs = subprocess.check_output(['pkg-config', '--libs', package]).decode().strip().split()
        return cflags, libs
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"Warning: pkg-config not found or {package} not available, using fallback")
        if package == 'libcurl':
            return ['-I/usr/include/curl'], ['-lcurl']
        return [], []

# Get curl flags
curl_cflags, curl_libs = get_pkg_config_flags('libcurl')

loadtest_extension = Extension(
    'loadtest',
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
    extra_compile_args=curl_cflags + ['-O2', '-pthread', '-std=c11'],
    extra_link_args=curl_libs + ['-pthread'],
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
    ext_modules=[loadtest_extension],
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
