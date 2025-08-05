from setuptools import setup, Extension
import pkg_config

# Get curl flags from pkg-config
curl_cflags = pkg_config.parse('libcurl')['cflags']
curl_libs = pkg_config.parse('libcurl')['libs']

loadtest_extension = Extension(
    'loadtest',
    sources=[
        'src/python_extension.c',
        'src/engine.c'
    ],
    include_dirs=['src'],
    extra_compile_args=curl_cflags + ['-O3', '-pthread'],
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
