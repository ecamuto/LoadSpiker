"""
Test scenario definitions and request builders
"""

from typing import List, Dict, Any, Optional, Callable
import json
import random
import time


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
    
    def setup(self, func: Callable):
        """Set setup function to run before scenario"""
        self.setup_func = func
        return self
    
    def teardown(self, func: Callable):
        """Set teardown function to run after scenario"""
        self.teardown_func = func
        return self
    
    def build_requests(self) -> List[Dict[str, Any]]:
        """Build requests list for the C engine"""
        if self.setup_func:
            self.setup_func(self)
        
        # Apply variable substitution
        processed_requests = []
        for request in self.requests:
            processed_request = self._process_request(request)
            processed_requests.append(processed_request.to_dict())
        
        return processed_requests
    
    def _process_request(self, request: HTTPRequest) -> HTTPRequest:
        """Process request with variable substitution"""
        url = self._substitute_variables(request.url)
        body = self._substitute_variables(request.body)
        
        headers = {}
        for k, v in request.headers.items():
            headers[k] = self._substitute_variables(v)
        
        return HTTPRequest(url, request.method, headers, body, request.timeout_ms)
    
    def _substitute_variables(self, text: str) -> str:
        """Substitute variables in text using ${var} syntax"""
        import re
        
        def replace_var(match):
            var_name = match.group(1)
            if var_name in self.variables:
                return str(self.variables[var_name])
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