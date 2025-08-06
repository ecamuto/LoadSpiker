"""
LoadSpiker - High-performance load testing tool
"""

# Import the Python wrapper Engine class explicitly
from .engine import Engine

# Import assertions system (always available)
from .assertions import *

# Import the classes that are now loaded in engine.py
from .engine import _python_modules_available

if _python_modules_available:
    from .scenarios import Scenario, HTTPRequest, RESTAPIScenario, WebsiteScenario
    from .reporters import ConsoleReporter, JSONReporter, HTMLReporter
    from .utils import ramp_up, constant_load
    
    __all__ = [
        "Engine", 
        "Scenario", "HTTPRequest", "RESTAPIScenario", "WebsiteScenario",
        "ConsoleReporter", "JSONReporter", "HTMLReporter",
        "ramp_up", "constant_load",
        # Assertion classes
        "Assertion", "StatusCodeAssertion", "ResponseTimeAssertion", 
        "BodyContainsAssertion", "RegexAssertion", "JSONPathAssertion",
        "HeaderAssertion", "CustomAssertion", "AssertionGroup",
        # Assertion convenience functions
        "status_is", "response_time_under", "body_contains", "body_matches",
        "json_path", "header_exists", "custom_assertion", "run_assertions"
    ]
else:
    # Export placeholder classes from engine.py
    from .engine import Scenario, RESTAPIScenario, WebsiteScenario
    __all__ = [
        "Engine", "Scenario", "RESTAPIScenario", "WebsiteScenario",
        # Assertion classes (always available)
        "Assertion", "StatusCodeAssertion", "ResponseTimeAssertion", 
        "BodyContainsAssertion", "RegexAssertion", "JSONPathAssertion",
        "HeaderAssertion", "CustomAssertion", "AssertionGroup",
        # Assertion convenience functions
        "status_is", "response_time_under", "body_contains", "body_matches",
        "json_path", "header_exists", "custom_assertion", "run_assertions"
    ]

__version__ = "1.0.0"

# Note: Engine methods may vary depending on which class is loaded
