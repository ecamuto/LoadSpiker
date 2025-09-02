"""
Session Management system for LoadSpiker load testing

This module provides session management capabilities including:
- Cookie handling and storage
- Authentication token management
- Session state persistence
- Request correlation and value extraction
"""

import json
import re
import threading
import time
from typing import Dict, Any, Optional, List, Union, Callable
from urllib.parse import urlparse, parse_qs
from http.cookies import SimpleCookie


class SessionStore:
    """Thread-safe storage for session data"""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._cookies: Dict[str, str] = {}
        self._tokens: Dict[str, str] = {}
        self._custom_data: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._created_at = time.time()
        self._last_accessed = time.time()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from session storage"""
        with self._lock:
            self._last_accessed = time.time()
            return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in session storage"""
        with self._lock:
            self._data[key] = value
            self._last_accessed = time.time()
    
    def delete(self, key: str) -> None:
        """Delete a value from session storage"""
        with self._lock:
            self._data.pop(key, None)
            self._last_accessed = time.time()
    
    def get_cookie(self, name: str) -> Optional[str]:
        """Get a cookie value"""
        with self._lock:
            return self._cookies.get(name)
    
    def set_cookie(self, name: str, value: str, domain: str = "", path: str = "/") -> None:
        """Set a cookie value"""
        with self._lock:
            self._cookies[name] = value
            # Store additional cookie metadata if needed
            if domain or path != "/":
                self.set(f"_cookie_meta_{name}", {"domain": domain, "path": path})
            self._last_accessed = time.time()
    
    def get_all_cookies(self) -> Dict[str, str]:
        """Get all cookies"""
        with self._lock:
            return self._cookies.copy()
    
    def clear_cookies(self) -> None:
        """Clear all cookies"""
        with self._lock:
            self._cookies.clear()
            self._last_accessed = time.time()
    
    def get_token(self, token_type: str) -> Optional[str]:
        """Get an authentication token"""
        with self._lock:
            return self._tokens.get(token_type)
    
    def set_token(self, token_type: str, token_value: str, expires_at: Optional[float] = None) -> None:
        """Set an authentication token"""
        with self._lock:
            self._tokens[token_type] = token_value
            if expires_at:
                self.set(f"_token_expires_{token_type}", expires_at)
            self._last_accessed = time.time()
    
    def get_all_tokens(self) -> Dict[str, str]:
        """Get all tokens"""
        with self._lock:
            return self._tokens.copy()
    
    def clear_tokens(self) -> None:
        """Clear all tokens"""
        with self._lock:
            self._tokens.clear()
            self._last_accessed = time.time()
    
    def is_token_expired(self, token_type: str) -> bool:
        """Check if a token is expired"""
        with self._lock:
            expires_at = self.get(f"_token_expires_{token_type}")
            if expires_at is None:
                return False
            return time.time() > expires_at
    
    def clear(self) -> None:
        """Clear all session data"""
        with self._lock:
            self._data.clear()
            self._cookies.clear()
            self._tokens.clear()
            self._custom_data.clear()
            self._last_accessed = time.time()
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information"""
        with self._lock:
            return {
                "created_at": self._created_at,
                "last_accessed": self._last_accessed,
                "data_keys": list(self._data.keys()),
                "cookie_count": len(self._cookies),
                "token_count": len(self._tokens)
            }


class ResponseExtractor:
    """Extract values from HTTP responses for correlation"""
    
    @staticmethod
    def extract_json_path(response_body: str, json_path: str) -> Any:
        """Extract value using JSON path (dot notation)"""
        try:
            data = json.loads(response_body)
            return ResponseExtractor._get_nested_value(data, json_path)
        except (json.JSONDecodeError, KeyError, TypeError, IndexError):
            return None
    
    @staticmethod
    def _get_nested_value(data: Any, path: str) -> Any:
        """Get nested value using dot notation (e.g., 'user.name' or 'items[0].id')"""
        parts = path.split('.')
        current = data
        
        for part in parts:
            if '[' in part and ']' in part:
                # Handle array indexing like 'items[0]'
                key, index_part = part.split('[', 1)
                index = int(index_part.rstrip(']'))
                if key:
                    current = current[key]
                current = current[index]
            else:
                current = current[part]
        
        return current
    
    @staticmethod
    def extract_regex(response_body: str, pattern: str, group: int = 1) -> Optional[str]:
        """Extract value using regular expression"""
        try:
            match = re.search(pattern, response_body)
            if match and len(match.groups()) >= group:
                return match.group(group)
            elif match and group == 0:
                return match.group(0)
        except (re.error, IndexError):
            pass
        return None
    
    @staticmethod
    def extract_header(headers: Union[Dict[str, str], str], header_name: str) -> Optional[str]:
        """Extract value from response headers"""
        if isinstance(headers, str):
            # Parse header string
            headers_dict = {}
            for line in headers.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers_dict[key.strip().lower()] = value.strip()
            headers = headers_dict
        
        return headers.get(header_name.lower())
    
    @staticmethod
    def extract_cookie_from_headers(headers: Union[Dict[str, str], str], cookie_name: str) -> Optional[str]:
        """Extract cookie value from Set-Cookie headers"""
        set_cookie_header = ResponseExtractor.extract_header(headers, 'set-cookie')
        if not set_cookie_header:
            return None
        
        try:
            cookie = SimpleCookie()
            cookie.load(set_cookie_header)
            if cookie_name in cookie:
                return cookie[cookie_name].value
        except Exception:
            # Fallback to simple parsing
            for part in set_cookie_header.split(';'):
                if '=' in part:
                    name, value = part.strip().split('=', 1)
                    if name == cookie_name:
                        return value
        
        return None
    
    @staticmethod
    def extract_url_parameter(url: str, param_name: str) -> Optional[str]:
        """Extract parameter from URL query string"""
        try:
            parsed_url = urlparse(url)
            params = parse_qs(parsed_url.query)
            values = params.get(param_name, [])
            return values[0] if values else None
        except Exception:
            return None


class SessionManager:
    """Manages user sessions for load testing scenarios"""
    
    def __init__(self):
        self._sessions: Dict[str, SessionStore] = {}
        self._lock = threading.RLock()
        self._default_session_timeout = 3600  # 1 hour
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def get_session(self, user_id: Union[str, int]) -> SessionStore:
        """Get or create a session for a user"""
        user_key = str(user_id)
        
        with self._lock:
            if user_key not in self._sessions:
                self._sessions[user_key] = SessionStore()
            
            # Periodic cleanup
            if time.time() - self._last_cleanup > self._cleanup_interval:
                self._cleanup_expired_sessions()
            
            return self._sessions[user_key]
    
    def clear_session(self, user_id: Union[str, int]) -> None:
        """Clear a specific user session"""
        user_key = str(user_id)
        with self._lock:
            if user_key in self._sessions:
                self._sessions[user_key].clear()
                del self._sessions[user_key]
    
    def clear_all_sessions(self) -> None:
        """Clear all user sessions"""
        with self._lock:
            for session in self._sessions.values():
                session.clear()
            self._sessions.clear()
    
    def _cleanup_expired_sessions(self) -> None:
        """Remove expired sessions"""
        current_time = time.time()
        expired_users = []
        
        for user_id, session in self._sessions.items():
            session_info = session.get_session_info()
            if current_time - session_info['last_accessed'] > self._default_session_timeout:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            self._sessions.pop(user_id, None)
        
        self._last_cleanup = current_time
    
    def process_response(self, user_id: Union[str, int], response: Dict[str, Any], 
                        extract_rules: Optional[List[Dict[str, Any]]] = None) -> None:
        """Process response and extract values according to rules"""
        if not extract_rules:
            return
        
        session = self.get_session(user_id)
        
        for rule in extract_rules:
            try:
                value = self._extract_value_by_rule(response, rule)
                if value is not None:
                    variable_name = rule.get('variable', rule.get('name'))
                    if variable_name:
                        session.set(variable_name, value)
            except Exception as e:
                # Log error but don't fail the test
                print(f"Warning: Failed to extract value with rule {rule}: {e}")
    
    def _extract_value_by_rule(self, response: Dict[str, Any], rule: Dict[str, Any]) -> Any:
        """Extract value from response using extraction rule"""
        extract_type = rule.get('type', 'json_path')
        
        if extract_type == 'json_path':
            path = rule.get('path', rule.get('json_path'))
            return ResponseExtractor.extract_json_path(response.get('body', ''), path)
        
        elif extract_type == 'regex':
            pattern = rule.get('pattern', rule.get('regex'))
            group = rule.get('group', 1)
            return ResponseExtractor.extract_regex(response.get('body', ''), pattern, group)
        
        elif extract_type == 'header':
            header_name = rule.get('header_name', rule.get('name'))
            return ResponseExtractor.extract_header(response.get('headers', {}), header_name)
        
        elif extract_type == 'cookie':
            cookie_name = rule.get('cookie_name', rule.get('name'))
            return ResponseExtractor.extract_cookie_from_headers(response.get('headers', {}), cookie_name)
        
        elif extract_type == 'status_code':
            return response.get('status_code')
        
        elif extract_type == 'response_time':
            return response.get('response_time_ms', response.get('response_time_us', 0) / 1000)
        
        else:
            raise ValueError(f"Unknown extraction type: {extract_type}")
    
    def prepare_request_headers(self, user_id: Union[str, int], 
                               base_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Prepare request headers with session cookies and tokens"""
        headers = base_headers.copy() if base_headers else {}
        session = self.get_session(user_id)
        
        # Add cookies
        cookies = session.get_all_cookies()
        if cookies:
            cookie_header = '; '.join([f"{name}={value}" for name, value in cookies.items()])
            if 'Cookie' in headers:
                headers['Cookie'] = f"{headers['Cookie']}; {cookie_header}"
            else:
                headers['Cookie'] = cookie_header
        
        # Add authorization token if available
        bearer_token = session.get_token('bearer')
        if bearer_token and not session.is_token_expired('bearer'):
            headers['Authorization'] = f"Bearer {bearer_token}"
        
        # Add API key if available
        api_key = session.get_token('api_key')
        if api_key:
            api_key_header = session.get('api_key_header', 'X-API-Key')
            headers[api_key_header] = api_key
        
        # Add other tokens as headers
        for token_type, token_value in session.get_all_tokens().items():
            if token_type not in ['bearer', 'api_key'] and not session.is_token_expired(token_type):
                header_name = session.get(f'{token_type}_header', f'X-{token_type.title()}-Token')
                headers[header_name] = token_value
        
        return headers
    
    def auto_handle_cookies(self, user_id: Union[str, int], response: Dict[str, Any]) -> None:
        """Automatically extract and store cookies from response"""
        headers = response.get('headers', {})
        if isinstance(headers, str):
            # Parse header string to find Set-Cookie headers
            for line in headers.split('\n'):
                if line.lower().startswith('set-cookie:'):
                    cookie_value = line.split(':', 1)[1].strip()
                    self._parse_and_store_cookie(user_id, cookie_value)
        elif isinstance(headers, dict):
            # Handle both single Set-Cookie and multiple cookies
            set_cookie_headers = []
            for key, value in headers.items():
                if key.lower() == 'set-cookie':
                    if isinstance(value, list):
                        set_cookie_headers.extend(value)
                    else:
                        set_cookie_headers.append(value)
            
            for cookie_value in set_cookie_headers:
                self._parse_and_store_cookie(user_id, cookie_value)
    
    def _parse_and_store_cookie(self, user_id: Union[str, int], cookie_header: str) -> None:
        """Parse and store a cookie from Set-Cookie header"""
        try:
            cookie = SimpleCookie()
            cookie.load(cookie_header)
            
            session = self.get_session(user_id)
            for morsel in cookie.values():
                session.set_cookie(morsel.key, morsel.value, morsel.get('domain', ''), morsel.get('path', '/'))
        except Exception:
            # Fallback to simple parsing
            cookie_part = cookie_header.split(';')[0].strip()
            if '=' in cookie_part:
                name, value = cookie_part.split('=', 1)
                session = self.get_session(user_id)
                session.set_cookie(name.strip(), value.strip())
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get statistics about all sessions"""
        with self._lock:
            active_sessions = len(self._sessions)
            total_cookies = sum(len(session.get_all_cookies()) for session in self._sessions.values())
            total_tokens = sum(len(session.get_all_tokens()) for session in self._sessions.values())
            
            return {
                'active_sessions': active_sessions,
                'total_cookies': total_cookies,
                'total_tokens': total_tokens,
                'last_cleanup': self._last_cleanup
            }


# Global session manager instance
_global_session_manager = SessionManager()


def get_session_manager() -> SessionManager:
    """Get the global session manager instance"""
    return _global_session_manager


def reset_session_manager() -> None:
    """Reset the global session manager (useful for testing)"""
    global _global_session_manager
    _global_session_manager.clear_all_sessions()
