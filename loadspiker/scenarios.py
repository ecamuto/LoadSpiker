"""
Test scenario definitions and request builders
"""

from typing import List, Dict, Any, Optional, Callable
import json
import random
import time
import re
# Import data sources with fallback to avoid circular import issues
try:
    from .data_sources import DataManager, DataStrategy
except ImportError:
    # Fallback to direct import
    try:
        import data_sources
        DataManager = data_sources.DataManager
        DataStrategy = data_sources.DataStrategy
    except ImportError:
        # Create stubs if import fails
        class DataManager:
            def __init__(self):
                self.data_sources = {}
            def add_csv_source(self, *args, **kwargs):
                pass
            def get_all_user_data(self, user_id):
                return {}
            def list_sources(self):
                return []
            def get_source_info(self, name=None):
                return {'total_rows': 0, 'strategy': 'sequential', 'columns': []}
        
        class DataStrategy:
            SEQUENTIAL = "sequential"
            RANDOM = "random"
            CIRCULAR = "circular"
            UNIQUE = "unique"
            SHARED = "shared"
            
            @classmethod
            def __call__(cls, value):
                return value


class HTTPRequest:
    """Represents an HTTP request configuration"""
    
    def __init__(self, url: str, method: str = "GET", 
                 headers: Optional[Dict[str, str]] = None,
                 body: str = "", timeout_ms: int = 30000):
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.body = body
        self.timeout_ms = timeout_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format expected by C engine"""
        headers_str = "\n".join([f"{k}: {v}" for k, v in self.headers.items()])
        return {
            "url": self.url,
            "method": self.method,
            "headers": headers_str,
            "body": self.body,
            "timeout_ms": self.timeout_ms
        }


class Scenario:
    """Base class for load test scenarios"""
    
    def __init__(self, name: str = ""):
        self.name = name
        self.requests: List[HTTPRequest] = []
        self.setup_func: Optional[Callable] = None
        self.teardown_func: Optional[Callable] = None
        self.variables: Dict[str, Any] = {}
        self.data_manager = DataManager()
    
    def add_request(self, request: HTTPRequest):
        """Add a request to the scenario"""
        self.requests.append(request)
        return self
    
    def get(self, url: str, headers: Optional[Dict[str, str]] = None, 
            timeout_ms: int = 30000):
        """Add a GET request"""
        self.requests.append(HTTPRequest(url, "GET", headers, "", timeout_ms))
        return self
    
    def post(self, url: str, body: str = "", 
             headers: Optional[Dict[str, str]] = None, timeout_ms: int = 30000):
        """Add a POST request"""
        self.requests.append(HTTPRequest(url, "POST", headers, body, timeout_ms))
        return self
    
    def put(self, url: str, body: str = "", 
            headers: Optional[Dict[str, str]] = None, timeout_ms: int = 30000):
        """Add a PUT request"""
        self.requests.append(HTTPRequest(url, "PUT", headers, body, timeout_ms))
        return self
    
    def delete(self, url: str, headers: Optional[Dict[str, str]] = None, 
               timeout_ms: int = 30000):
        """Add a DELETE request"""
        self.requests.append(HTTPRequest(url, "DELETE", headers, "", timeout_ms))
        return self
    
    def set_variable(self, name: str, value: Any):
        """Set a scenario variable"""
        self.variables[name] = value
        return self
    
    def get_variable(self, name: str, default: Any = None):
        """Get a scenario variable"""
        return self.variables.get(name, default)
    
    def load_data_file(self, file_path: str, name: str = "data", 
                      strategy: str = "sequential", **options):
        """Load data file for data-driven testing"""
        # Convert string strategy to enum - DataStrategy is now available from module imports
        strategy_enum = DataStrategy(strategy.lower()) if hasattr(DataStrategy, '__call__') else strategy.lower()
        
        # Add CSV data source
        self.data_manager.add_csv_source(file_path, name, strategy_enum, **options)
        return self
    
    def get_data_info(self, source_name: str = None) -> Dict[str, Any]:
        """Get information about loaded data"""
        return self.data_manager.get_source_info(source_name)
    
    def setup(self, func: Callable):
        """Set setup function to run before scenario"""
        self.setup_func = func
        return self
    
    def teardown(self, func: Callable):
        """Set teardown function to run after scenario"""
        self.teardown_func = func
        return self
    
    def build_requests(self, user_id: int = 0) -> List[Dict[str, Any]]:
        """Build requests list for the C engine with user-specific data"""
        if self.setup_func:
            self.setup_func(self)
        
        # Get user-specific data
        user_data = {}
        if self.data_manager.list_sources():
            user_data = self.data_manager.get_all_user_data(user_id)
        
        # Apply variable substitution with user data
        processed_requests = []
        for request in self.requests:
            processed_request = self._process_request(request, user_data)
            processed_requests.append(processed_request.to_dict())
        
        return processed_requests
    
    def _process_request(self, request: HTTPRequest, user_data: Dict[str, Dict[str, Any]] = None) -> HTTPRequest:
        """Process request with variable substitution"""
        url = self._substitute_variables(request.url, user_data)
        body = self._substitute_variables(request.body, user_data)
        
        headers = {}
        for k, v in request.headers.items():
            headers[k] = self._substitute_variables(v, user_data)
        
        return HTTPRequest(url, request.method, headers, body, request.timeout_ms)
    
    def _substitute_variables(self, text: str, user_data: Dict[str, Dict[str, Any]] = None) -> str:
        """Substitute variables in text using ${var} syntax"""
        if not text:
            return text
            
        def replace_var(match):
            var_name = match.group(1)
            
            # Check for data source variables (e.g., ${data.username}, ${users.email})
            if user_data and '.' in var_name:
                source_name, field_name = var_name.split('.', 1)
                if source_name in user_data and field_name in user_data[source_name]:
                    value = user_data[source_name][field_name]
                    return str(value) if value is not None else ""
            
            # Check scenario variables
            if var_name in self.variables:
                return str(self.variables[var_name])
                
            # Return original if not found
            return match.group(0)
        
        return re.sub(r'\$\{([^}]+)\}', replace_var, text)


class RESTAPIScenario(Scenario):
    """Scenario for testing REST APIs"""
    
    def __init__(self, base_url: str, name: str = "REST API Test"):
        super().__init__(name)
        self.base_url = base_url.rstrip('/')
        
    def get_resource(self, path: str, headers: Optional[Dict[str, str]] = None):
        """GET a resource"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        return self.get(url, headers)
    
    def create_resource(self, path: str, data: Dict[str, Any], 
                       headers: Optional[Dict[str, str]] = None):
        """POST to create a resource"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        return self.post(url, json.dumps(data), default_headers)
    
    def update_resource(self, path: str, data: Dict[str, Any], 
                       headers: Optional[Dict[str, str]] = None):
        """PUT to update a resource"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        default_headers = {"Content-Type": "application/json"}
        if headers:
            default_headers.update(headers)
        return self.put(url, json.dumps(data), default_headers)
    
    def delete_resource(self, path: str, headers: Optional[Dict[str, str]] = None):
        """DELETE a resource"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        return self.delete(url, headers)


class WebsiteScenario(Scenario):
    """Scenario for testing websites with realistic user behavior"""
    
    def __init__(self, base_url: str, name: str = "Website Test"):
        super().__init__(name)
        self.base_url = base_url.rstrip('/')
        
    def browse_page(self, path: str, think_time: float = 0):
        """Browse to a page with optional think time"""
        url = f"{self.base_url}/{path.lstrip('/')}"
        self.get(url, headers={"User-Agent": "LoadTest/1.0"})
        if think_time > 0:
            time.sleep(think_time)
        return self
    
    def search(self, query: str, search_path: str = "/search"):
        """Perform a search"""
        url = f"{self.base_url}{search_path}?q={query}"
        return self.get(url, headers={"User-Agent": "LoadTest/1.0"})
    
    def login(self, username: str, password: str, login_path: str = "/login"):
        """Perform login"""
        url = f"{self.base_url}{login_path}"
        data = f"username={username}&password={password}"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "LoadTest/1.0"
        }
        return self.post(url, data, headers)


def create_scenario_from_har(har_file_path: str) -> Scenario:
    """Create a scenario from a HAR (HTTP Archive) file"""
    import json
    
    with open(har_file_path, 'r') as f:
        har_data = json.load(f)
    
    scenario = Scenario("HAR-based scenario")
    
    for entry in har_data['log']['entries']:
        request = entry['request']
        url = request['url']
        method = request['method']
        
        headers = {}
        for header in request['headers']:
            headers[header['name']] = header['value']
        
        body = ""
        if 'postData' in request and 'text' in request['postData']:
            body = request['postData']['text']
        
        scenario.add_request(HTTPRequest(url, method, headers, body))
    
    return scenario
