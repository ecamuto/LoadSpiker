"""
LoadSpiker - High-performance load testing tool
"""

import sys
import os

# Add the loadspiker directory to Python path for imports
_loadspiker_dir = os.path.dirname(__file__)
if _loadspiker_dir not in sys.path:
    sys.path.insert(0, _loadspiker_dir)

# Import the Python wrapper Engine class explicitly
from .engine import Engine

# Import assertions system (always available)
from .assertions import *

# Import performance assertions (standalone, always available)
try:
    from .performance_assertions import (
        PerformanceAssertion, ThroughputAssertion, AverageResponseTimeAssertion,
        ErrorRateAssertion, MaxResponseTimeAssertion, SuccessRateAssertion,
        TotalRequestsAssertion, CustomPerformanceAssertion, PerformanceAssertionGroup,
        throughput_at_least, avg_response_time_under, error_rate_below,
        success_rate_at_least, max_response_time_under, total_requests_at_least,
        custom_performance_assertion, run_performance_assertions
    )
    _performance_assertions_available = True
except ImportError as e:
    print(f"Warning: Performance assertions not available: {e}")
    _performance_assertions_available = False

# Import the classes that are now loaded in engine.py
from .engine import _python_modules_available

# Import data sources with fallback
try:
    from .data_sources import DataManager, DataStrategy, CSVDataSource, load_csv_data, get_user_data
except ImportError:
    try:
        import data_sources as _ds
        DataManager = _ds.DataManager
        DataStrategy = _ds.DataStrategy
        CSVDataSource = _ds.CSVDataSource
        load_csv_data = _ds.load_csv_data
        get_user_data = _ds.get_user_data
    except ImportError:
        # Create stubs
        class DataStrategy:
            SEQUENTIAL = "sequential"
            RANDOM = "random"
            CIRCULAR = "circular" 
            UNIQUE = "unique"
            SHARED = "shared"
            def __call__(self, value): return value
        class DataManager:
            def add_csv_source(self, *args, **kwargs): pass
            def get_all_user_data(self, user_id): return {}
            def list_sources(self): return []
            def get_source_info(self, name=None): return {'total_rows': 0, 'strategy': 'sequential', 'columns': []}
        class CSVDataSource: pass
        def load_csv_data(*args): pass
        def get_user_data(*args): return {}

# Import scenarios with fallback
try:
    from .scenarios import Scenario, HTTPRequest, RESTAPIScenario, WebsiteScenario
except ImportError:
    try:
        import scenarios as _sc
        Scenario = _sc.Scenario
        HTTPRequest = _sc.HTTPRequest
        RESTAPIScenario = _sc.RESTAPIScenario
        WebsiteScenario = _sc.WebsiteScenario
    except ImportError:
        from .engine import _PlaceholderScenario, _PlaceholderRESTAPIScenario, _PlaceholderWebsiteScenario
        Scenario = _PlaceholderScenario
        HTTPRequest = None
        RESTAPIScenario = _PlaceholderRESTAPIScenario
        WebsiteScenario = _PlaceholderWebsiteScenario

# Import assertions with fallback
try:
    from .assertions import *
except ImportError:
    try:
        import assertions as _assert
        # Copy all public attributes
        for name in dir(_assert):
            if not name.startswith('_'):
                globals()[name] = getattr(_assert, name)
    except ImportError:
        # Create minimal assertion stubs
        class Assertion: pass
        class StatusCodeAssertion(Assertion): pass
        class ResponseTimeAssertion(Assertion): pass
        class BodyContainsAssertion(Assertion): pass
        class RegexAssertion(Assertion): pass
        class JSONPathAssertion(Assertion): pass
        class HeaderAssertion(Assertion): pass
        class CustomAssertion(Assertion): pass
        class AssertionGroup: pass
        def status_is(*args): return StatusCodeAssertion()
        def response_time_under(*args): return ResponseTimeAssertion()
        def body_contains(*args): return BodyContainsAssertion()
        def body_matches(*args): return RegexAssertion()
        def json_path(*args): return JSONPathAssertion()
        def header_exists(*args): return HeaderAssertion()
        def custom_assertion(*args): return CustomAssertion()
        def run_assertions(*args): return True, []

# Import reporters with fallback
try:
    from .reporters import ConsoleReporter, JSONReporter, HTMLReporter
except ImportError:
    try:
        import reporters as _rep
        ConsoleReporter = _rep.ConsoleReporter
        JSONReporter = _rep.JSONReporter
        HTMLReporter = _rep.HTMLReporter
    except ImportError:
        ConsoleReporter = None
        JSONReporter = None
        HTMLReporter = None

# Import utils with fallback
try:
    from .utils import ramp_up, constant_load
except ImportError:
    try:
        import utils as _utils
        ramp_up = _utils.ramp_up
        constant_load = _utils.constant_load
    except ImportError:
        ramp_up = None
        constant_load = None

__all__ = [
    "Engine",
    "Scenario", "HTTPRequest", "RESTAPIScenario", "WebsiteScenario",
    "ConsoleReporter", "JSONReporter", "HTMLReporter",
    "ramp_up", "constant_load",
    # Data source classes
    "DataManager", "DataStrategy", "CSVDataSource", "load_csv_data", "get_user_data",
    # Assertion classes (if successfully imported)
]

# Add assertion items to __all__ if they were imported
if 'Assertion' in globals():
    __all__.extend([
        "Assertion", "StatusCodeAssertion", "ResponseTimeAssertion",
        "BodyContainsAssertion", "RegexAssertion", "JSONPathAssertion", 
        "HeaderAssertion", "CustomAssertion", "AssertionGroup",
        "status_is", "response_time_under", "body_contains", "body_matches",
        "json_path", "header_exists", "custom_assertion", "run_assertions"
    ])

# Add performance assertion items to __all__ if they were imported
if 'PerformanceAssertion' in globals():
    __all__.extend([
        "PerformanceAssertion", "ThroughputAssertion", "AverageResponseTimeAssertion",
        "ErrorRateAssertion", "MaxResponseTimeAssertion", "SuccessRateAssertion",
        "TotalRequestsAssertion", "CustomPerformanceAssertion", "PerformanceAssertionGroup",
        "throughput_at_least", "avg_response_time_under", "error_rate_below",
        "success_rate_at_least", "max_response_time_under", "total_requests_at_least",
        "custom_performance_assertion", "run_performance_assertions"
    ])

__version__ = "1.0.0"

# Note: Engine methods may vary depending on which class is loaded
