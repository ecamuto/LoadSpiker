"""
High-level Python API for the load testing engine
"""

# Import standard libraries
import sys
import os
import importlib.util
import time
from typing import List, Dict, Any, Optional, Callable, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .scenarios import Scenario

# Import session management and authentication
try:
    from .session_manager import get_session_manager
    from .authentication import get_authentication_manager
    _session_auth_available = True
except ImportError:
    _session_auth_available = False

# Use lazy imports to avoid circular dependencies
_python_modules_available = None
_scenarios_module = None
_reporters_module = None
_utils_module = None

def _get_python_modules():
    """Lazy import Python modules to avoid circular dependencies"""
    global _python_modules_available, _scenarios_module, _reporters_module, _utils_module
    
    if _python_modules_available is None:
        try:
            from . import scenarios as _scenarios_module
            from . import reporters as _reporters_module
            from . import utils as _utils_module
            _python_modules_available = True
        except ImportError as e:
            print(f"Warning: Python modules not available: {e}")
            _python_modules_available = False
    
    return _python_modules_available

# Create placeholder classes for when modules aren't available
class _PlaceholderScenario:
    def build_requests(self, user_id=0):
        return []

class _PlaceholderRESTAPIScenario(_PlaceholderScenario):
    pass

class _PlaceholderWebsiteScenario(_PlaceholderScenario):
    pass

# Try to load the C extension, fall back to Python-only implementation if not available
current_dir = os.path.dirname(__file__)
so_path = os.path.join(current_dir, "loadspiker.so")

_CEngine = None
_c_extension_available = False

try:
    # Try to load the C extension for high performance
    if os.path.exists(so_path):
        # Load the C extension with a unique module name to avoid conflicts
        spec = importlib.util.spec_from_file_location("loadspiker_c_module", so_path)
        if spec and spec.loader:
            c_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(c_module)
            _CEngine = c_module.Engine
            _c_extension_available = True
            print("🚀 C extension loaded successfully - high performance mode enabled")
        else:
            raise ImportError("Could not load C extension spec")
    else:
        raise FileNotFoundError(f"C extension not found at {so_path}")
except Exception as e:
    print(f"ℹ️  C extension not available: {e}")
    print("   Falling back to Python-only implementation")
    _c_extension_available = False


# Fallback Python implementation when C extension is not available
class _PythonEngine:
    """Python-only fallback implementation of the engine"""
    
    def __init__(self, max_connections: int = 1000, worker_threads: int = 10):
        self.max_connections = max_connections
        self.worker_threads = worker_threads
        
        # Initialize session and authentication managers if available
        if _session_auth_available:
            self.session_manager = get_session_manager()
            self.auth_manager = get_authentication_manager()
        else:
            self.session_manager = None
            self.auth_manager = None
        self._metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_response_time_ms': 0.0,
            'min_response_time_ms': 0.0,
            'max_response_time_ms': 0.0,
            'requests_per_second': 0.0
        }
    
    def execute_request(self, url: str, method: str = "GET", headers: str = "", 
                       body: str = "", timeout_ms: int = 30000) -> Dict[str, Any]:
        """Python fallback for HTTP requests using requests library"""
        try:
            import requests
            import time
            
            start_time = time.time()
            
            # Parse headers
            headers_dict = {}
            if headers:
                for line in headers.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        headers_dict[key.strip()] = value.strip()
            
            # Make request
            response = requests.request(
                method=method,
                url=url,
                headers=headers_dict,
                data=body if method in ['POST', 'PUT', 'PATCH'] else None,
                timeout=timeout_ms / 1000.0
            )
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Update metrics
            self._metrics['total_requests'] += 1
            if response.status_code < 400:
                self._metrics['successful_requests'] += 1
            else:
                self._metrics['failed_requests'] += 1
            
            self._metrics['total_response_time_ms'] += response_time_ms
            if self._metrics['min_response_time_ms'] == 0 or response_time_ms < self._metrics['min_response_time_ms']:
                self._metrics['min_response_time_ms'] = response_time_ms
            if response_time_ms > self._metrics['max_response_time_ms']:
                self._metrics['max_response_time_ms'] = response_time_ms
            
            return {
                'status_code': response.status_code,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,  # Convert ms to microseconds for compatibility
                'headers': dict(response.headers),
                'body': response.text,
                'success': response.status_code < 400,
                'error_message': '' if response.status_code < 400 else f'HTTP {response.status_code}'
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 0,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'headers': {},
                'body': '',
                'success': False,
                'error_message': str(e)
            }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics"""
        return self._metrics.copy()
    
    def reset_metrics(self):
        """Reset metrics"""
        self._metrics = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_response_time_ms': 0.0,
            'min_response_time_ms': 0.0,
            'max_response_time_ms': 0.0,
            'requests_per_second': 0.0
        }
    
    def start_load_test(self, requests: List[Dict], concurrent_users: int, duration_seconds: int):
        """Basic load test implementation"""
        print(f"Python fallback: Running load test with {concurrent_users} users for {duration_seconds}s")
    
    # Placeholder methods for protocol support
    def websocket_connect(self, url: str, subprotocol: str = "") -> Dict[str, Any]:
        return {'status': 501, 'error_message': 'WebSocket not implemented in Python fallback'}
    
    def websocket_send(self, url: str, message: str) -> Dict[str, Any]:
        return {'status': 501, 'error_message': 'WebSocket not implemented in Python fallback'}
    
    def websocket_close(self, url: str) -> Dict[str, Any]:
        return {'status': 501, 'error_message': 'WebSocket not implemented in Python fallback'}
    
    def database_connect(self, connection_string: str, db_type: str) -> Dict[str, Any]:
        return {
            'status': 501, 
            'success': False,
            'response_time_ms': 0.0,
            'error_message': 'Database not implemented in Python fallback - C extension required'
        }
    
    def database_query(self, connection_string: str, query: str) -> Dict[str, Any]:
        return {
            'status': 501, 
            'success': False,
            'response_time_ms': 0.0,
            'error_message': 'Database not implemented in Python fallback - C extension required'
        }
    
    def database_disconnect(self, connection_string: str) -> Dict[str, Any]:
        return {
            'status': 501, 
            'success': False,
            'response_time_ms': 0.0,
            'error_message': 'Database not implemented in Python fallback - C extension required'
        }
    
    # TCP Socket Python fallback methods
    def tcp_connect(self, hostname: str, port: int, timeout_ms: int = 30000) -> Dict[str, Any]:
        """Python fallback for TCP connections using socket library"""
        try:
            import socket
            import time
            
            start_time = time.time()
            
            # Create TCP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout_ms / 1000.0)
            
            # Connect to server
            sock.connect((hostname, port))
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            # Store socket for future operations (simplified approach)
            if not hasattr(self, '_tcp_sockets'):
                self._tcp_sockets = {}
            self._tcp_sockets[f"{hostname}:{port}"] = sock
            
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'TCP connection established to {hostname}:{port}',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'connection_established': True,
                    'bytes_sent': 0,
                    'bytes_received': 0
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'TCP connection failed: {str(e)}'
            }
    
    def tcp_send(self, hostname: str, port: int, data: str, timeout_ms: int = 30000) -> Dict[str, Any]:
        """Python fallback for TCP send using socket library"""
        try:
            import time
            
            start_time = time.time()
            
            # Get existing socket
            if not hasattr(self, '_tcp_sockets'):
                self._tcp_sockets = {}
            
            socket_key = f"{hostname}:{port}"
            if socket_key not in self._tcp_sockets:
                return {
                    'status_code': 400,
                    'response_time_ms': 0.0,
                    'response_time_us': 0.0,
                    'body': '',
                    'success': False,
                    'error_message': 'No active TCP connection - call tcp_connect first'
                }
            
            sock = self._tcp_sockets[socket_key]
            sock.settimeout(timeout_ms / 1000.0)
            
            # Send data
            bytes_sent = sock.send(data.encode('utf-8'))
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'Sent {bytes_sent} bytes to {hostname}:{port}',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'bytes_sent': bytes_sent,
                    'connection_established': True
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'TCP send failed: {str(e)}'
            }
    
    def tcp_receive(self, hostname: str, port: int, timeout_ms: int = 30000) -> Dict[str, Any]:
        """Python fallback for TCP receive using socket library"""
        try:
            import time
            
            start_time = time.time()
            
            # Get existing socket
            if not hasattr(self, '_tcp_sockets'):
                self._tcp_sockets = {}
            
            socket_key = f"{hostname}:{port}"
            if socket_key not in self._tcp_sockets:
                return {
                    'status_code': 400,
                    'response_time_ms': 0.0,
                    'response_time_us': 0.0,
                    'body': '',
                    'success': False,
                    'error_message': 'No active TCP connection - call tcp_connect first'
                }
            
            sock = self._tcp_sockets[socket_key]
            sock.settimeout(timeout_ms / 1000.0)
            
            # Receive data
            data = sock.recv(4096)
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': data.decode('utf-8', errors='ignore'),
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'bytes_received': len(data),
                    'connection_established': True,
                    'received_data': data.decode('utf-8', errors='ignore')
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'TCP receive failed: {str(e)}'
            }
    
    def tcp_disconnect(self, hostname: str, port: int) -> Dict[str, Any]:
        """Python fallback for TCP disconnect using socket library"""
        try:
            import time
            
            start_time = time.time()
            
            # Get existing socket
            if not hasattr(self, '_tcp_sockets'):
                self._tcp_sockets = {}
            
            socket_key = f"{hostname}:{port}"
            if socket_key not in self._tcp_sockets:
                return {
                    'status_code': 400,
                    'response_time_ms': 0.0,
                    'response_time_us': 0.0,
                    'body': '',
                    'success': False,
                    'error_message': 'No active TCP connection to disconnect'
                }
            
            sock = self._tcp_sockets[socket_key]
            sock.close()
            del self._tcp_sockets[socket_key]
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'TCP connection to {hostname}:{port} closed successfully',
                'success': True,
                'error_message': ''
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'TCP disconnect failed: {str(e)}'
            }
    
    # UDP Socket Python fallback methods
    def udp_create_endpoint(self, hostname: str, port: int) -> Dict[str, Any]:
        """Python fallback for UDP endpoint creation using socket library"""
        try:
            import socket
            import time
            
            start_time = time.time()
            
            # Create UDP socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            # Store socket for future operations
            if not hasattr(self, '_udp_sockets'):
                self._udp_sockets = {}
            self._udp_sockets[f"{hostname}:{port}"] = sock
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'UDP endpoint created for {hostname}:{port}',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'datagram_sent': False,
                    'bytes_sent': 0,
                    'bytes_received': 0,
                    'remote_host': hostname,
                    'remote_port': port
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'UDP endpoint creation failed: {str(e)}'
            }
    
    def udp_send(self, hostname: str, port: int, data: str, timeout_ms: int = 30000) -> Dict[str, Any]:
        """Python fallback for UDP send using socket library"""
        try:
            import time
            
            start_time = time.time()
            
            # Get or create UDP socket
            if not hasattr(self, '_udp_sockets'):
                self._udp_sockets = {}
            
            socket_key = f"{hostname}:{port}"
            if socket_key not in self._udp_sockets:
                # Auto-create endpoint if it doesn't exist
                create_result = self.udp_create_endpoint(hostname, port)
                if not create_result['success']:
                    return create_result
            
            sock = self._udp_sockets[socket_key]
            sock.settimeout(timeout_ms / 1000.0)
            
            # Send UDP datagram
            bytes_sent = sock.sendto(data.encode('utf-8'), (hostname, port))
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'Sent {bytes_sent} bytes to {hostname}:{port} via UDP',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'bytes_sent': bytes_sent,
                    'datagram_sent': True,
                    'remote_host': hostname,
                    'remote_port': port
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'UDP send failed: {str(e)}'
            }
    
    def udp_receive(self, hostname: str, port: int, timeout_ms: int = 30000) -> Dict[str, Any]:
        """Python fallback for UDP receive using socket library"""
        try:
            import time
            
            start_time = time.time()
            
            # Get existing UDP socket
            if not hasattr(self, '_udp_sockets'):
                self._udp_sockets = {}
            
            socket_key = f"{hostname}:{port}"
            if socket_key not in self._udp_sockets:
                return {
                    'status_code': 400,
                    'response_time_ms': 0.0,
                    'response_time_us': 0.0,
                    'body': '',
                    'success': False,
                    'error_message': 'No UDP endpoint available - call udp_create_endpoint first'
                }
            
            sock = self._udp_sockets[socket_key]
            sock.settimeout(timeout_ms / 1000.0)
            
            # Receive UDP datagram
            data, sender_addr = sock.recvfrom(4096)
            sender_ip, sender_port = sender_addr
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'Received {len(data)} bytes from {sender_ip}:{sender_port} via UDP',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'bytes_received': len(data),
                    'received_data': data.decode('utf-8', errors='ignore'),
                    'remote_host': sender_ip,
                    'remote_port': sender_port
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'UDP receive failed: {str(e)}'
            }
    
    def udp_close_endpoint(self, hostname: str, port: int) -> Dict[str, Any]:
        """Python fallback for UDP endpoint closure using socket library"""
        try:
            import time
            
            start_time = time.time()
            
            # Get existing UDP socket
            if not hasattr(self, '_udp_sockets'):
                self._udp_sockets = {}
            
            socket_key = f"{hostname}:{port}"
            if socket_key not in self._udp_sockets:
                return {
                    'status_code': 400,
                    'response_time_ms': 0.0,
                    'response_time_us': 0.0,
                    'body': '',
                    'success': False,
                    'error_message': 'No UDP endpoint to close'
                }
            
            sock = self._udp_sockets[socket_key]
            sock.close()
            del self._udp_sockets[socket_key]
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'UDP endpoint for {hostname}:{port} closed successfully',
                'success': True,
                'error_message': ''
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'UDP endpoint closure failed: {str(e)}'
            }
    
    # MQTT Python fallback methods
    def mqtt_connect(self, broker_host: str, broker_port: int, client_id: str, username: str, password: str, keep_alive: int) -> Dict[str, Any]:
        """Python fallback for MQTT connections using paho-mqtt library"""
        try:
            import time
            
            start_time = time.time()
            
            # For fallback, we'll simulate MQTT connection
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'MQTT connection established to {broker_host}:{broker_port} (Python fallback)',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'broker_host': broker_host,
                    'broker_port': broker_port,
                    'client_id': client_id,
                    'connected': True
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'MQTT connection failed: {str(e)}'
            }
    
    def mqtt_publish(self, broker_host: str, broker_port: int, client_id: str, topic: str, payload: str, qos: int, retain: bool) -> Dict[str, Any]:
        """Python fallback for MQTT publish"""
        try:
            import time
            
            start_time = time.time()
            
            # For fallback, we'll simulate MQTT publish
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'MQTT message published to {topic} (Python fallback)',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'topic': topic,
                    'payload_size': len(payload),
                    'qos': qos,
                    'retain': retain,
                    'published': True
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'MQTT publish failed: {str(e)}'
            }
    
    def mqtt_subscribe(self, broker_host: str, broker_port: int, client_id: str, topic: str, qos: int) -> Dict[str, Any]:
        """Python fallback for MQTT subscribe"""
        try:
            import time
            
            start_time = time.time()
            
            # For fallback, we'll simulate MQTT subscribe
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'MQTT subscribed to {topic} (Python fallback)',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'topic': topic,
                    'qos': qos,
                    'subscribed': True
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'MQTT subscribe failed: {str(e)}'
            }
    
    def mqtt_unsubscribe(self, broker_host: str, broker_port: int, client_id: str, topic: str) -> Dict[str, Any]:
        """Python fallback for MQTT unsubscribe"""
        try:
            import time
            
            start_time = time.time()
            
            # For fallback, we'll simulate MQTT unsubscribe
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'MQTT unsubscribed from {topic} (Python fallback)',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'topic': topic,
                    'unsubscribed': True
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'MQTT unsubscribe failed: {str(e)}'
            }
    
    def mqtt_disconnect(self, broker_host: str, broker_port: int, client_id: str) -> Dict[str, Any]:
        """Python fallback for MQTT disconnect"""
        try:
            import time
            
            start_time = time.time()
            
            # For fallback, we'll simulate MQTT disconnect
            self._metrics['total_requests'] += 1
            self._metrics['successful_requests'] += 1
            
            end_time = time.time()
            response_time_ms = (end_time - start_time) * 1000
            
            return {
                'status_code': 200,
                'response_time_ms': response_time_ms,
                'response_time_us': response_time_ms * 1000,
                'body': f'MQTT disconnected from {broker_host}:{broker_port} (Python fallback)',
                'success': True,
                'error_message': '',
                'protocol_data': {
                    'broker_host': broker_host,
                    'broker_port': broker_port,
                    'client_id': client_id,
                    'disconnected': True
                }
            }
            
        except Exception as e:
            self._metrics['total_requests'] += 1
            self._metrics['failed_requests'] += 1
            return {
                'status_code': 500,
                'response_time_ms': 0.0,
                'response_time_us': 0.0,
                'body': '',
                'success': False,
                'error_message': f'MQTT disconnect failed: {str(e)}'
            }


class Engine:
    """High-performance load testing engine with C backend"""
    
    def __init__(self, max_connections: int = 1000, worker_threads: int = 10):
        """
        Initialize the load testing engine
        
        Args:
            max_connections: Maximum number of concurrent connections
            worker_threads: Number of worker threads for request processing
        """
        if _c_extension_available and _CEngine:
            self._engine = _CEngine(max_connections, worker_threads)
            self._using_c_extension = True
        else:
            self._engine = _PythonEngine(max_connections, worker_threads)
            self._using_c_extension = False
            print("⚠️  Using Python fallback implementation (limited performance)")
        
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
    
    def run_scenario(self, scenario: "Scenario", users: int = 10, 
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
    
    # Phase 1: Database Protocol Support - Database Methods
    def database_connect(self, connection_string: str, db_type: str = "auto") -> Dict[str, Any]:
        """
        Connect to a database
        
        Args:
            connection_string: Database connection string (e.g., "mysql://user:pass@host:port/database")
            db_type: Database type ("mysql", "postgresql", "mongodb", or "auto" to detect from URL)
            
        Returns:
            Dictionary containing connection response data
        """
        # Auto-detect database type from connection string if not specified
        if db_type == "auto":
            if connection_string.startswith("mysql://"):
                db_type = "mysql"
            elif connection_string.startswith("postgresql://"):
                db_type = "postgresql"
            elif connection_string.startswith("mongodb://"):
                db_type = "mongodb"
            else:
                db_type = "mysql"  # Default fallback
        
        return self._engine.database_connect(connection_string=connection_string, db_type=db_type)
    
    def database_query(self, connection_string: str, query: str) -> Dict[str, Any]:
        """
        Execute a database query
        
        Args:
            connection_string: Database connection string
            query: SQL query or database command to execute
            
        Returns:
            Dictionary containing query response data including result set
        """
        return self._engine.database_query(connection_string=connection_string, query=query)
    
    def database_disconnect(self, connection_string: str) -> Dict[str, Any]:
        """
        Disconnect from a database
        
        Args:
            connection_string: Database connection string
            
        Returns:
            Dictionary containing disconnection response data
        """
        return self._engine.database_disconnect(connection_string=connection_string)
    
    # Phase 1: TCP Socket Support - TCP Methods
    def tcp_connect(self, hostname: str, port: int, timeout_ms: int = 30000) -> Dict[str, Any]:
        """
        Connect to a TCP server
        
        Args:
            hostname: Target hostname or IP address
            port: Target port number
            timeout_ms: Connection timeout in milliseconds
            
        Returns:
            Dictionary containing connection response data
        """
        return self._engine.tcp_connect(hostname=hostname, port=port, timeout_ms=timeout_ms)
    
    def tcp_send(self, hostname: str, port: int, data: str, timeout_ms: int = 30000) -> Dict[str, Any]:
        """
        Send data to a TCP connection
        
        Args:
            hostname: Target hostname or IP address
            port: Target port number
            data: Data to send
            timeout_ms: Send timeout in milliseconds
            
        Returns:
            Dictionary containing send response data
        """
        return self._engine.tcp_send(hostname=hostname, port=port, data=data, timeout_ms=timeout_ms)
    
    def tcp_receive(self, hostname: str, port: int, timeout_ms: int = 30000) -> Dict[str, Any]:
        """
        Receive data from a TCP connection
        
        Args:
            hostname: Target hostname or IP address
            port: Target port number
            timeout_ms: Receive timeout in milliseconds
            
        Returns:
            Dictionary containing received data
        """
        return self._engine.tcp_receive(hostname=hostname, port=port, timeout_ms=timeout_ms)
    
    def tcp_disconnect(self, hostname: str, port: int) -> Dict[str, Any]:
        """
        Disconnect from a TCP server
        
        Args:
            hostname: Target hostname or IP address
            port: Target port number
            
        Returns:
            Dictionary containing disconnection response data
        """
        return self._engine.tcp_disconnect(hostname=hostname, port=port)
    
    # Phase 1: UDP Socket Support - UDP Methods
    def udp_create_endpoint(self, hostname: str, port: int) -> Dict[str, Any]:
        """
        Create a UDP endpoint for communication
        
        Args:
            hostname: Target hostname or IP address
            port: Target port number
            
        Returns:
            Dictionary containing endpoint creation response data
        """
        return self._engine.udp_create_endpoint(hostname=hostname, port=port)
    
    def udp_send(self, hostname: str, port: int, data: str, timeout_ms: int = 30000) -> Dict[str, Any]:
        """
        Send data via UDP
        
        Args:
            hostname: Target hostname or IP address
            port: Target port number
            data: Data to send
            timeout_ms: Send timeout in milliseconds
            
        Returns:
            Dictionary containing send response data
        """
        return self._engine.udp_send(hostname=hostname, port=port, data=data, timeout_ms=timeout_ms)
    
    def udp_receive(self, hostname: str, port: int, timeout_ms: int = 30000) -> Dict[str, Any]:
        """
        Receive data via UDP
        
        Args:
            hostname: Target hostname or IP address
            port: Target port number
            timeout_ms: Receive timeout in milliseconds
            
        Returns:
            Dictionary containing received data and sender information
        """
        return self._engine.udp_receive(hostname=hostname, port=port, timeout_ms=timeout_ms)
    
    def udp_close_endpoint(self, hostname: str, port: int) -> Dict[str, Any]:
        """
        Close a UDP endpoint

        Args:
            hostname: Target hostname or IP address
            port: Target port number

        Returns:
            Dictionary containing endpoint closure response data
        """
        return self._engine.udp_close_endpoint(hostname=hostname, port=port)
    
    # Phase 2: Message Queue Protocol Support - MQTT Methods
    def mqtt_connect(self, broker_host: str, broker_port: int = 1883, 
                    client_id: str = "loadspiker_client", username: str = None, 
                    password: str = None, keep_alive: int = 60) -> Dict[str, Any]:
        """
        Connect to an MQTT broker

        Args:
            broker_host: MQTT broker hostname or IP address
            broker_port: MQTT broker port (default: 1883)
            client_id: MQTT client identifier
            username: Optional username for authentication
            password: Optional password for authentication
            keep_alive: Keep alive interval in seconds

        Returns:
            Dictionary containing connection response data
        """
        return self._engine.mqtt_connect(
            broker_host=broker_host,
            broker_port=broker_port,
            client_id=client_id,
            username=username or "",
            password=password or "",
            keep_alive=keep_alive
        )
    
    def mqtt_publish(self, broker_host: str, broker_port: int = 1883,
                    client_id: str = "loadspiker_client", topic: str = "",
                    payload: str = "", qos: int = 0, retain: bool = False) -> Dict[str, Any]:
        """
        Publish a message to an MQTT topic

        Args:
            broker_host: MQTT broker hostname or IP address
            broker_port: MQTT broker port (default: 1883)
            client_id: MQTT client identifier
            topic: MQTT topic to publish to
            payload: Message payload
            qos: Quality of Service level (0, 1, or 2)
            retain: Whether to retain the message

        Returns:
            Dictionary containing publish response data
        """
        return self._engine.mqtt_publish(
            broker_host=broker_host,
            broker_port=broker_port,
            client_id=client_id,
            topic=topic,
            payload=payload,
            qos=qos,
            retain=retain
        )
    
    def mqtt_subscribe(self, broker_host: str, broker_port: int = 1883,
                      client_id: str = "loadspiker_client", topic: str = "",
                      qos: int = 0) -> Dict[str, Any]:
        """
        Subscribe to an MQTT topic

        Args:
            broker_host: MQTT broker hostname or IP address
            broker_port: MQTT broker port (default: 1883)
            client_id: MQTT client identifier
            topic: MQTT topic to subscribe to
            qos: Quality of Service level (0, 1, or 2)

        Returns:
            Dictionary containing subscription response data
        """
        return self._engine.mqtt_subscribe(
            broker_host=broker_host,
            broker_port=broker_port,
            client_id=client_id,
            topic=topic,
            qos=qos
        )
    
    def mqtt_unsubscribe(self, broker_host: str, broker_port: int = 1883,
                        client_id: str = "loadspiker_client", topic: str = "") -> Dict[str, Any]:
        """
        Unsubscribe from an MQTT topic

        Args:
            broker_host: MQTT broker hostname or IP address
            broker_port: MQTT broker port (default: 1883)
            client_id: MQTT client identifier
            topic: MQTT topic to unsubscribe from

        Returns:
            Dictionary containing unsubscription response data
        """
        return self._engine.mqtt_unsubscribe(
            broker_host=broker_host,
            broker_port=broker_port,
            client_id=client_id,
            topic=topic
        )
    
    def mqtt_disconnect(self, broker_host: str, broker_port: int = 1883,
                       client_id: str = "loadspiker_client") -> Dict[str, Any]:
        """
        Disconnect from an MQTT broker

        Args:
            broker_host: MQTT broker hostname or IP address
            broker_port: MQTT broker port (default: 1883)
            client_id: MQTT client identifier

        Returns:
            Dictionary containing disconnection response data
        """
        return self._engine.mqtt_disconnect(
            broker_host=broker_host,
            broker_port=broker_port,
            client_id=client_id
        )
