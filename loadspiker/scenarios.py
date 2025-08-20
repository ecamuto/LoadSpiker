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


class DatabaseScenario(Scenario):
    """Scenario for testing database performance"""
    
    def __init__(self, connection_string: str, name: str = "Database Test"):
        super().__init__(name)
        self.connection_string = connection_string
        self.db_type = self._detect_db_type(connection_string)
        self.queries: List[str] = []
        
    def _detect_db_type(self, connection_string: str) -> str:
        """Detect database type from connection string"""
        if connection_string.startswith("mysql://"):
            return "mysql"
        elif connection_string.startswith("postgresql://"):
            return "postgresql"
        elif connection_string.startswith("mongodb://"):
            return "mongodb"
        else:
            return "unknown"
    
    def add_query(self, query: str):
        """Add a database query to the scenario"""
        self.queries.append(query)
        return self
    
    def select_query(self, table: str, columns: str = "*", where: str = ""):
        """Add a SELECT query"""
        query = f"SELECT {columns} FROM {table}"
        if where:
            query += f" WHERE {where}"
        return self.add_query(query)
    
    def insert_query(self, table: str, columns: List[str], values: List[str]):
        """Add an INSERT query"""
        columns_str = ", ".join(columns)
        values_str = ", ".join([f"'{v}'" if isinstance(v, str) else str(v) for v in values])
        query = f"INSERT INTO {table} ({columns_str}) VALUES ({values_str})"
        return self.add_query(query)
    
    def update_query(self, table: str, set_clause: str, where: str = ""):
        """Add an UPDATE query"""
        query = f"UPDATE {table} SET {set_clause}"
        if where:
            query += f" WHERE {where}"
        return self.add_query(query)
    
    def delete_query(self, table: str, where: str = ""):
        """Add a DELETE query"""
        query = f"DELETE FROM {table}"
        if where:
            query += f" WHERE {where}"
        return self.add_query(query)
    
    def build_database_operations(self, user_id: int = 0) -> List[Dict[str, Any]]:
        """Build database operations for the scenario"""
        operations = []
        
        # Add connection operation
        operations.append({
            "type": "database_connect",
            "connection_string": self.connection_string,
            "db_type": self.db_type
        })
        
        # Add query operations
        for query in self.queries:
            processed_query = self._substitute_variables(query, 
                self.data_manager.get_all_user_data(user_id) if self.data_manager.list_sources() else {})
            operations.append({
                "type": "database_query",
                "connection_string": self.connection_string,
                "query": processed_query
            })
        
        # Add disconnect operation
        operations.append({
            "type": "database_disconnect",
            "connection_string": self.connection_string
        })
        
        return operations


class MixedProtocolScenario(Scenario):
    """Scenario for testing multiple protocols in a single test"""
    
    def __init__(self, name: str = "Mixed Protocol Test"):
        super().__init__(name)
        self.operations: List[Dict[str, Any]] = []
    
    def add_http_request(self, url: str, method: str = "GET", 
                        headers: Optional[Dict[str, str]] = None, body: str = ""):
        """Add an HTTP request operation"""
        self.operations.append({
            "type": "http",
            "url": url,
            "method": method,
            "headers": headers or {},
            "body": body
        })
        return self
    
    def add_websocket_operation(self, url: str, operation: str, message: str = "", subprotocol: str = ""):
        """Add a WebSocket operation (connect, send, close)"""
        self.operations.append({
            "type": "websocket",
            "url": url,
            "operation": operation,  # "connect", "send", "close"
            "message": message,
            "subprotocol": subprotocol
        })
        return self
    
    def add_database_operation(self, connection_string: str, operation: str, 
                             query: str = "", db_type: str = "auto"):
        """Add a database operation (connect, query, disconnect)"""
        self.operations.append({
            "type": "database",
            "connection_string": connection_string,
            "operation": operation,  # "connect", "query", "disconnect"
            "query": query,
            "db_type": db_type
        })
        return self
    
    def build_mixed_operations(self, user_id: int = 0) -> List[Dict[str, Any]]:
        """Build mixed protocol operations for execution"""
        processed_operations = []
        user_data = self.data_manager.get_all_user_data(user_id) if self.data_manager.list_sources() else {}
        
        for operation in self.operations:
            processed_op = operation.copy()
            
            # Apply variable substitution to relevant fields
            if "url" in processed_op:
                processed_op["url"] = self._substitute_variables(processed_op["url"], user_data)
            if "query" in processed_op:
                processed_op["query"] = self._substitute_variables(processed_op["query"], user_data)
            if "message" in processed_op:
                processed_op["message"] = self._substitute_variables(processed_op["message"], user_data)
            if "body" in processed_op:
                processed_op["body"] = self._substitute_variables(processed_op["body"], user_data)
            
            processed_operations.append(processed_op)
        
        return processed_operations


class TCPScenario(Scenario):
    """Scenario for testing TCP socket connections"""
    
    def __init__(self, hostname: str, port: int, name: str = "TCP Socket Test"):
        super().__init__(name)
        self.hostname = hostname
        self.port = port
        self.tcp_operations: List[Dict[str, Any]] = []
        
    def add_connect(self, timeout_ms: int = 30000):
        """Add a TCP connect operation"""
        self.tcp_operations.append({
            "type": "tcp_connect",
            "hostname": self.hostname,
            "port": self.port,
            "timeout_ms": timeout_ms
        })
        return self
    
    def add_send(self, data: str, timeout_ms: int = 30000):
        """Add a TCP send operation"""
        self.tcp_operations.append({
            "type": "tcp_send",
            "hostname": self.hostname,
            "port": self.port,
            "data": data,
            "timeout_ms": timeout_ms
        })
        return self
    
    def add_receive(self, timeout_ms: int = 30000):
        """Add a TCP receive operation"""
        self.tcp_operations.append({
            "type": "tcp_receive",
            "hostname": self.hostname,
            "port": self.port,
            "timeout_ms": timeout_ms
        })
        return self
    
    def add_disconnect(self):
        """Add a TCP disconnect operation"""
        self.tcp_operations.append({
            "type": "tcp_disconnect",
            "hostname": self.hostname,
            "port": self.port
        })
        return self
    
    def add_echo_test(self, message: str = "Hello TCP Server", timeout_ms: int = 30000):
        """Add a complete echo test (connect, send, receive, disconnect)"""
        self.add_connect(timeout_ms)
        self.add_send(message, timeout_ms)
        self.add_receive(timeout_ms)
        self.add_disconnect()
        return self
    
    def build_tcp_operations(self, user_id: int = 0) -> List[Dict[str, Any]]:
        """Build TCP operations for execution"""
        processed_operations = []
        user_data = self.data_manager.get_all_user_data(user_id) if self.data_manager.list_sources() else {}
        
        for operation in self.tcp_operations:
            processed_op = operation.copy()
            
            # Apply variable substitution to data field
            if "data" in processed_op:
                processed_op["data"] = self._substitute_variables(processed_op["data"], user_data)
            
            # Apply variable substitution to hostname (in case it's parameterized)
            processed_op["hostname"] = self._substitute_variables(str(processed_op["hostname"]), user_data)
            
            processed_operations.append(processed_op)
        
        return processed_operations


class UDPScenario(Scenario):
    """Scenario for testing UDP socket communication"""
    
    def __init__(self, hostname: str, port: int, name: str = "UDP Socket Test"):
        super().__init__(name)
        self.hostname = hostname
        self.port = port
        self.udp_operations: List[Dict[str, Any]] = []
        
    def add_create_endpoint(self):
        """Add a UDP endpoint creation operation"""
        self.udp_operations.append({
            "type": "udp_create_endpoint",
            "hostname": self.hostname,
            "port": self.port
        })
        return self
    
    def add_send(self, data: str, timeout_ms: int = 30000):
        """Add a UDP send operation"""
        self.udp_operations.append({
            "type": "udp_send",
            "hostname": self.hostname,
            "port": self.port,
            "data": data,
            "timeout_ms": timeout_ms
        })
        return self
    
    def add_receive(self, timeout_ms: int = 30000):
        """Add a UDP receive operation"""
        self.udp_operations.append({
            "type": "udp_receive",
            "hostname": self.hostname,
            "port": self.port,
            "timeout_ms": timeout_ms
        })
        return self
    
    def add_close_endpoint(self):
        """Add a UDP endpoint closure operation"""
        self.udp_operations.append({
            "type": "udp_close_endpoint",
            "hostname": self.hostname,
            "port": self.port
        })
        return self
    
    def add_echo_test(self, message: str = "Hello UDP Server", timeout_ms: int = 30000):
        """Add a complete echo test (create endpoint, send, receive, close)"""
        self.add_create_endpoint()
        self.add_send(message, timeout_ms)
        self.add_receive(timeout_ms)
        self.add_close_endpoint()
        return self
    
    def add_broadcast_test(self, message: str = "Broadcast message", timeout_ms: int = 30000):
        """Add a broadcast test (useful for testing UDP multicast)"""
        self.add_create_endpoint()
        self.add_send(message, timeout_ms)
        self.add_close_endpoint()
        return self
    
    def build_udp_operations(self, user_id: int = 0) -> List[Dict[str, Any]]:
        """Build UDP operations for execution"""
        processed_operations = []
        user_data = self.data_manager.get_all_user_data(user_id) if self.data_manager.list_sources() else {}
        
        for operation in self.udp_operations:
            processed_op = operation.copy()
            
            # Apply variable substitution to data field
            if "data" in processed_op:
                processed_op["data"] = self._substitute_variables(processed_op["data"], user_data)
            
            # Apply variable substitution to hostname (in case it's parameterized)
            processed_op["hostname"] = self._substitute_variables(str(processed_op["hostname"]), user_data)
            
            processed_operations.append(processed_op)
        
        return processed_operations


class MQTTScenario(Scenario):
    """Scenario for testing MQTT message queue performance"""
    
    def __init__(self, broker_host: str, broker_port: int = 1883, 
                 client_id: str = "loadspiker_client", name: str = "MQTT Test"):
        super().__init__(name)
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.mqtt_operations: List[Dict[str, Any]] = []
        
    def add_connect(self, username: str = "", password: str = "", keep_alive: int = 60):
        """Add an MQTT connect operation"""
        self.mqtt_operations.append({
            "type": "mqtt_connect",
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "client_id": self.client_id,
            "username": username,
            "password": password,
            "keep_alive": keep_alive
        })
        return self
    
    def add_publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """Add an MQTT publish operation"""
        self.mqtt_operations.append({
            "type": "mqtt_publish",
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "client_id": self.client_id,
            "topic": topic,
            "payload": payload,
            "qos": qos,
            "retain": retain
        })
        return self
    
    def add_subscribe(self, topic: str, qos: int = 0):
        """Add an MQTT subscribe operation"""
        self.mqtt_operations.append({
            "type": "mqtt_subscribe",
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "client_id": self.client_id,
            "topic": topic,
            "qos": qos
        })
        return self
    
    def add_unsubscribe(self, topic: str):
        """Add an MQTT unsubscribe operation"""
        self.mqtt_operations.append({
            "type": "mqtt_unsubscribe",
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "client_id": self.client_id,
            "topic": topic
        })
        return self
    
    def add_disconnect(self):
        """Add an MQTT disconnect operation"""
        self.mqtt_operations.append({
            "type": "mqtt_disconnect",
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "client_id": self.client_id
        })
        return self
    
    def add_publish_test(self, topic: str, payload: str = "Test message", 
                        qos: int = 0, retain: bool = False, username: str = "", 
                        password: str = "", keep_alive: int = 60):
        """Add a complete publish test (connect, publish, disconnect)"""
        self.add_connect(username, password, keep_alive)
        self.add_publish(topic, payload, qos, retain)
        self.add_disconnect()
        return self
    
    def add_subscribe_test(self, topic: str, qos: int = 0, username: str = "", 
                          password: str = "", keep_alive: int = 60):
        """Add a complete subscribe test (connect, subscribe, unsubscribe, disconnect)"""
        self.add_connect(username, password, keep_alive)
        self.add_subscribe(topic, qos)
        self.add_unsubscribe(topic)
        self.add_disconnect()
        return self
    
    def add_pub_sub_test(self, topic: str, payload: str = "Test message", 
                        qos: int = 0, retain: bool = False, username: str = "", 
                        password: str = "", keep_alive: int = 60):
        """Add a complete publish-subscribe test"""
        self.add_connect(username, password, keep_alive)
        self.add_subscribe(topic, qos)
        self.add_publish(topic, payload, qos, retain)
        self.add_unsubscribe(topic)
        self.add_disconnect()
        return self
    
    def add_burst_publish_test(self, topic: str, message_count: int = 10, 
                              base_payload: str = "Burst message", qos: int = 0, 
                              retain: bool = False, username: str = "", 
                              password: str = "", keep_alive: int = 60):
        """Add a burst publish test (connect, multiple publishes, disconnect)"""
        self.add_connect(username, password, keep_alive)
        
        for i in range(message_count):
            payload = f"{base_payload} #{i+1}"
            self.add_publish(topic, payload, qos, retain)
        
        self.add_disconnect()
        return self
    
    def add_topic_pattern_test(self, topic_pattern: str, payload: str = "Pattern test", 
                              topic_count: int = 5, qos: int = 0, retain: bool = False,
                              username: str = "", password: str = "", keep_alive: int = 60):
        """Add a topic pattern test with multiple topics"""
        self.add_connect(username, password, keep_alive)
        
        # Subscribe to pattern (using + or # wildcards)
        self.add_subscribe(topic_pattern, qos)
        
        # Publish to multiple specific topics that match the pattern
        for i in range(topic_count):
            # Replace wildcards with specific values for publishing
            specific_topic = topic_pattern.replace('+', f'topic{i}').replace('#', f'subtopic{i}/data')
            self.add_publish(specific_topic, f"{payload} for {specific_topic}", qos, retain)
        
        self.add_unsubscribe(topic_pattern)
        self.add_disconnect()
        return self
    
    def build_mqtt_operations(self, user_id: int = 0) -> List[Dict[str, Any]]:
        """Build MQTT operations for execution"""
        processed_operations = []
        user_data = self.data_manager.get_all_user_data(user_id) if self.data_manager.list_sources() else {}
        
        for operation in self.mqtt_operations:
            processed_op = operation.copy()
            
            # Apply variable substitution to relevant fields
            if "topic" in processed_op:
                processed_op["topic"] = self._substitute_variables(processed_op["topic"], user_data)
            if "payload" in processed_op:
                processed_op["payload"] = self._substitute_variables(processed_op["payload"], user_data)
            if "client_id" in processed_op:
                processed_op["client_id"] = self._substitute_variables(processed_op["client_id"], user_data)
            if "username" in processed_op:
                processed_op["username"] = self._substitute_variables(processed_op["username"], user_data)
            if "password" in processed_op:
                processed_op["password"] = self._substitute_variables(processed_op["password"], user_data)
            
            # Apply variable substitution to broker_host (in case it's parameterized)
            processed_op["broker_host"] = self._substitute_variables(str(processed_op["broker_host"]), user_data)
            
            processed_operations.append(processed_op)
        
        return processed_operations


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
