"""
LoadSpiker - High-performance load testing tool
"""

from .engine import Engine

# Import other modules with graceful error handling
try:
    from .scenarios import Scenario, HTTPRequest, RESTAPIScenario, WebsiteScenario
    _scenarios_available = True
except ImportError:
    _scenarios_available = False

try:
    from .reporters import ConsoleReporter, JSONReporter, HTMLReporter
    _reporters_available = True
except ImportError:
    _reporters_available = False

try:
    from .utils import ramp_up, constant_load
    _utils_available = True
except ImportError:
    _utils_available = False

__version__ = "1.0.0"

# Build __all__ list based on what's available
__all__ = ["Engine"]
if _scenarios_available:
    __all__.extend(["Scenario", "HTTPRequest", "RESTAPIScenario", "WebsiteScenario"])
if _reporters_available:
    __all__.extend(["ConsoleReporter", "JSONReporter", "HTMLReporter"])
if _utils_available:
    __all__.extend(["ramp_up", "constant_load"])
