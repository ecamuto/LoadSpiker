"""
High-level Python API for the load testing engine
"""

# Import standard libraries
import sys
import os
import importlib.util
import time
from typing import List, Dict, Any, Optional, Callable

# Import scenarios FIRST to ensure they're available before C extension loading
try:
    from .scenarios import Scenario, RESTAPIScenario, WebsiteScenario, HTTPRequest
    from .reporters import ConsoleReporter, JSONReporter, HTMLReporter
    from .utils import ramp_up, constant_load
    _python_modules_available = True
except ImportError as e:
    print(f"Warning: Python modules not available: {e}")
    # Create placeholders for scenarios if not available
    class Scenario:
        def build_requests(self):
            return []
    class RESTAPIScenario(Scenario):
        pass
    class WebsiteScenario(Scenario):
        pass
    _python_modules_available = False

# Now load the C extension from the _c_ext subdirectory
current_dir = os.path.dirname(__file__)
so_path = os.path.join(current_dir, "_c_ext", "loadspiker_c.so")

try:
    # Load the C extension with the original module name but assign to different namespace
    spec = importlib.util.spec_from_file_location("loadspiker", so_path)
    _loadspiker_module = importlib.util.module_from_spec(spec)
    
    # Clear any existing loadspiker module from sys.modules to avoid conflicts
    if "loadspiker" in sys.modules:
        del sys.modules["loadspiker"]
    
    spec.loader.exec_module(_loadspiker_module)
    _CEngine = _loadspiker_module.Engine
    
    # Remove from sys.modules again to prevent package conflicts
    if "loadspiker" in sys.modules:
        del sys.modules["loadspiker"]
        
except Exception as e:
    raise ImportError(f"Could not import LoadSpiker C extension from {so_path}: {e}")


class Engine:
    """High-performance load testing engine with C backend"""
    
    def __init__(self, max_connections: int = 1000, worker_threads: int = 10):
        """
        Initialize the load testing engine
        
        Args:
            max_connections: Maximum number of concurrent connections
            worker_threads: Number of worker threads for request processing
        """
        self._engine = _CEngine(max_connections, worker_threads)
        self.max_connections = max_connections
        self.worker_threads = worker_threads
    
    def execute_request(self, url: str, method: str = "GET", 
                       headers: Optional[Dict[str, str]] = None,
                       body: str = "", timeout_ms: int = 30000) -> Dict[str, Any]:
        """
        Execute a single HTTP request
        
        Args:
            url: Target URL
            method: HTTP method (GET, POST, PUT, DELETE, etc.)
            headers: HTTP headers as dictionary
            body: Request body
            timeout_ms: Request timeout in milliseconds
            
        Returns:
            Dictionary containing response data
        """
        headers_str = ""
        if headers:
            headers_str = "\n".join([f"{k}: {v}" for k, v in headers.items()])
        
        return self._engine.execute_request(
            url=url,
            method=method,
            headers=headers_str,
            body=body,
            timeout_ms=timeout_ms
        )
    
    def run_scenario(self, scenario: Scenario, users: int = 10, 
                    duration: int = 60, ramp_up_duration: int = 0) -> Dict[str, Any]:
        """
        Run a load test scenario
        
        Args:
            scenario: Test scenario to execute
            users: Number of concurrent users
            duration: Test duration in seconds
            ramp_up_duration: Time to gradually increase load
            
        Returns:
            Test results and metrics
        """
        requests = scenario.build_requests()
        
        if ramp_up_duration > 0:
            self._run_with_ramp_up(requests, users, duration, ramp_up_duration)
        else:
            self._engine.start_load_test(
                requests=requests,
                concurrent_users=users,
                duration_seconds=duration
            )
        
        return self.get_metrics()
    
    def _run_with_ramp_up(self, requests: List[Dict[str, Any]], 
                         target_users: int, duration: int, ramp_up_duration: int):
        """Run test with gradual user ramp-up"""
        start_time = time.time()
        ramp_end_time = start_time + ramp_up_duration
        test_end_time = start_time + duration
        
        current_users = 1
        
        while time.time() < test_end_time:
            if time.time() < ramp_end_time:
                progress = (time.time() - start_time) / ramp_up_duration
                current_users = max(1, int(target_users * progress))
            else:
                current_users = target_users
            
            # Run for a short burst with current user count
            self._engine.start_load_test(
                requests=requests,
                concurrent_users=current_users,
                duration_seconds=min(5, int(test_end_time - time.time()))
            )
            
            time.sleep(1)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current performance metrics"""
        return self._engine.get_metrics()
    
    def reset_metrics(self):
        """Reset performance metrics"""
        self._engine.reset_metrics()
    
    def run_custom_test(self, test_func: Callable, users: int = 10, 
                       duration: int = 60) -> Dict[str, Any]:
        """
        Run a custom test function

        Args:
            test_func: Function that takes (engine, user_id) as parameters
            users: Number of concurrent users
            duration: Test duration in seconds
            
        Returns:
            Test results and metrics
        """
        import threading
        import time
        
        self.reset_metrics()
        start_time = time.time()
        end_time = start_time + duration
        
        def worker(user_id: int):
            while time.time() < end_time:
                try:
                    test_func(self, user_id)
                except Exception as e:
                    print(f"Error in user {user_id}: {e}")
                time.sleep(0.1)  # Small delay to prevent overwhelming
        
        threads = []
        for i in range(users):
            thread = threading.Thread(target=worker, args=(i,))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()
        
        return self.get_metrics()
    
    # Phase 1: Multi-Protocol Support - WebSocket Methods
    def websocket_connect(self, url: str, subprotocol: str = "") -> Dict[str, Any]:
        """
        Connect to a WebSocket server
        
        Args:
            url: WebSocket URL (ws:// or wss://)
            subprotocol: Optional WebSocket subprotocol
            
        Returns:
            Dictionary containing connection response data
        """
        return self._engine.websocket_connect(url=url, subprotocol=subprotocol)
    
    def websocket_send(self, url: str, message: str) -> Dict[str, Any]:
        """
        Send a message to a WebSocket connection
        
        Args:
            url: WebSocket URL
            message: Message to send
            
        Returns:
            Dictionary containing send response data
        """
        return self._engine.websocket_send(url=url, message=message)
    
    def websocket_close(self, url: str) -> Dict[str, Any]:
        """
        Close a WebSocket connection
        
        Args:
            url: WebSocket URL
            
        Returns:
            Dictionary containing close response data
        """
        return self._engine.websocket_close(url=url)
