"""
LoadSpiker - High-performance load testing tool
"""

# Import the Python wrapper Engine class explicitly
from .engine import Engine

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
        "ramp_up", "constant_load"
    ]
else:
    # Export placeholder classes from engine.py
    from .engine import Scenario, RESTAPIScenario, WebsiteScenario
    __all__ = ["Engine", "Scenario", "RESTAPIScenario", "WebsiteScenario"]

__version__ = "1.0.0"

# Note: Engine methods may vary depending on which class is loaded
