"""
Authentication Flow system for LoadSpiker load testing

This module provides various authentication mechanisms including:
- Basic Authentication (username/password)
- Bearer Token Authentication (JWT, OAuth)
- API Key Authentication
- OAuth 2.0 flows
- Form-based Authentication
- Custom Authentication flows
"""

import json
import time
import base64
import hashlib
import secrets
import urllib.parse
from typing import Dict, Any, Optional, List, Union, Callable
from abc import ABC, abstractmethod

# Import session manager
from .session_manager import get_session_manager, SessionStore


class AuthenticationError(Exception):
    """Custom exception for authentication failures"""
    pass


class AuthenticationFlow(ABC):
    """Base class for all authentication flows"""
    
    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__
        self.session_manager = get_session_manager()
    
    @abstractmethod
    def authenticate(self, engine, user_id: Union[str, int], **kwargs) -> Dict[str, Any]:
        """
        Perform authentication and return result
        
        Args:
            engine: LoadSpiker engine instance
            user_id: User/session identifier
            **kwargs: Authentication-specific parameters
            
        Returns:
            Dictionary with authentication result
        """
        pass
    
    def is_authenticated(self, user_id: Union[str, int]) -> bool:
        """Check if user is currently authenticated"""
        session = self.session_manager.get_session(user_id)
        return session.get('authenticated', False)
    
    def logout(self, user_id: Union[str, int]) -> None:
        """Clear authentication state for user"""
        session = self.session_manager.get_session(user_id)
        session.clear_tokens()
        session.set('authenticated', False)


class BasicAuthenticationFlow(AuthenticationFlow):
    """HTTP Basic Authentication flow"""
    
    def __init__(self, username: str, password: str, name: str = "BasicAuth"):
        super().__init__(name)
        self.username = username
        self.password = password
    
    def authenticate(self, engine, user_id: Union[str, int], **kwargs) -> Dict[str, Any]:
        """Perform basic authentication by setting Authorization header"""
        # Encode credentials
        credentials = f"{self.username}:{self.password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        # Store in session
        session = self.session_manager.get_session(user_id)
        session.set_token('basic_auth', f"Basic {encoded_credentials}")
        session.set('authenticated', True)
        session.set('auth_type', 'basic')
        session.set('username', self.username)
        
        return {
            'success': True,
            'auth_type': 'basic',
            'username': self.username,
            'message': 'Basic authentication configured'
        }
    
    def get_auth_headers(self, user_id: Union[str, int]) -> Dict[str, str]:
        """Get authentication headers for requests"""
        session = self.session_manager.get_session(user_id)
        basic_token = session.get_token('basic_auth')
        
        if basic_token:
            return {'Authorization': basic_token}
        return {}


class BearerTokenAuthenticationFlow(AuthenticationFlow):
    """Bearer Token Authentication flow (JWT, OAuth, etc.)"""
    
    def __init__(self, token: str = "", token_endpoint: str = "", 
                 client_id: str = "", client_secret: str = "", name: str = "BearerAuth"):
        super().__init__(name)
        self.token = token
        self.token_endpoint = token_endpoint
        self.client_id = client_id
        self.client_secret = client_secret
    
    def authenticate(self, engine, user_id: Union[str, int], **kwargs) -> Dict[str, Any]:
        """Perform bearer token authentication"""
        if self.token:
            # Use provided token directly
            return self._set_bearer_token(user_id, self.token)
        elif self.token_endpoint:
            # Fetch token from endpoint
            return self._fetch_token_from_endpoint(engine, user_id, **kwargs)
        else:
            raise AuthenticationError("No token or token endpoint provided")
    
    def _set_bearer_token(self, user_id: Union[str, int], token: str, 
                         expires_in: Optional[int] = None) -> Dict[str, Any]:
        """Set bearer token in session"""
        session = self.session_manager.get_session(user_id)
        
        expires_at = None
        if expires_in:
            expires_at = time.time() + expires_in
        
        session.set_token('bearer', token, expires_at)
        session.set('authenticated', True)
        session.set('auth_type', 'bearer')
        
        return {
            'success': True,
            'auth_type': 'bearer',
            'token_length': len(token),
            'expires_in': expires_in,
            'message': 'Bearer token authentication configured'
        }
    
    def _fetch_token_from_endpoint(self, engine, user_id: Union[str, int], 
                                  **kwargs) -> Dict[str, Any]:
        """Fetch token from OAuth endpoint"""
        if not self.token_endpoint:
            raise AuthenticationError("No token endpoint configured")
        
        # Prepare token request
        token_data = {
            'grant_type': kwargs.get('grant_type', 'client_credentials'),
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        # Add additional parameters from kwargs
        for key in ['username', 'password', 'scope', 'audience']:
            if key in kwargs:
                token_data[key] = kwargs[key]
        
        # Encode form data
        form_data = urllib.parse.urlencode(token_data)
        
        # Make token request
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        response = engine.execute_request(
            url=self.token_endpoint,
            method='POST',
            headers=headers,
            body=form_data
        )
        
        if not response.get('success', False):
            raise AuthenticationError(f"Token request failed: {response.get('error_message', 'Unknown error')}")
        
        # Parse token response
        try:
            token_response = json.loads(response.get('body', '{}'))
        except json.JSONDecodeError:
            raise AuthenticationError("Invalid JSON response from token endpoint")
        
        if 'access_token' not in token_response:
            raise AuthenticationError("No access_token in response")
        
        access_token = token_response['access_token']
        expires_in = token_response.get('expires_in')
        
        # Store token
        result = self._set_bearer_token(user_id, access_token, expires_in)
        result['token_response'] = token_response
        
        return result
    
    def refresh_token(self, engine, user_id: Union[str, int], 
                     refresh_token: str = "") -> Dict[str, Any]:
        """Refresh an expired token"""
        session = self.session_manager.get_session(user_id)
        refresh_token = refresh_token or session.get('refresh_token', '')
        
        if not refresh_token:
            raise AuthenticationError("No refresh token available")
        
        token_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }
        
        form_data = urllib.parse.urlencode(token_data)
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        response = engine.execute_request(
            url=self.token_endpoint,
            method='POST',
            headers=headers,
            body=form_data
        )
        
        if not response.get('success', False):
            raise AuthenticationError(f"Token refresh failed: {response.get('error_message')}")
        
        try:
            token_response = json.loads(response.get('body', '{}'))
        except json.JSONDecodeError:
            raise AuthenticationError("Invalid JSON response from refresh endpoint")
        
        if 'access_token' not in token_response:
            raise AuthenticationError("No access_token in refresh response")
        
        # Update token
        new_token = token_response['access_token']
        expires_in = token_response.get('expires_in')
        
        return self._set_bearer_token(user_id, new_token, expires_in)


class APIKeyAuthenticationFlow(AuthenticationFlow):
    """API Key Authentication flow"""
    
    def __init__(self, api_key: str, header_name: str = "X-API-Key", 
                 query_param: str = "", name: str = "APIKeyAuth"):
        super().__init__(name)
        self.api_key = api_key
        self.header_name = header_name
        self.query_param = query_param
    
    def authenticate(self, engine, user_id: Union[str, int], **kwargs) -> Dict[str, Any]:
        """Configure API key authentication"""
        session = self.session_manager.get_session(user_id)
        
        session.set_token('api_key', self.api_key)
        session.set('api_key_header', self.header_name)
        session.set('api_key_query_param', self.query_param)
        session.set('authenticated', True)
        session.set('auth_type', 'api_key')
        
        return {
            'success': True,
            'auth_type': 'api_key',
            'header_name': self.header_name,
            'query_param': self.query_param,
            'message': 'API Key authentication configured'
        }
    
    def get_auth_headers(self, user_id: Union[str, int]) -> Dict[str, str]:
        """Get authentication headers for requests"""
        session = self.session_manager.get_session(user_id)
        api_key = session.get_token('api_key')
        header_name = session.get('api_key_header', self.header_name)
        
        if api_key and header_name:
            return {header_name: api_key}
        return {}
    
    def get_auth_query_params(self, user_id: Union[str, int]) -> Dict[str, str]:
        """Get authentication query parameters"""
        session = self.session_manager.get_session(user_id)
        api_key = session.get_token('api_key')
        query_param = session.get('api_key_query_param', self.query_param)
        
        if api_key and query_param:
            return {query_param: api_key}
        return {}


class FormBasedAuthenticationFlow(AuthenticationFlow):
    """Form-based Authentication flow (login forms with sessions)"""
    
    def __init__(self, login_url: str, username_field: str = "username", 
                 password_field: str = "password", success_indicator: str = "",
                 name: str = "FormAuth"):
        super().__init__(name)
        self.login_url = login_url
        self.username_field = username_field
        self.password_field = password_field
        self.success_indicator = success_indicator
    
    def authenticate(self, engine, user_id: Union[str, int], 
                    username: str = "", password: str = "", **kwargs) -> Dict[str, Any]:
        """Perform form-based authentication"""
        if not username or not password:
            raise AuthenticationError("Username and password are required for form authentication")
        
        # Prepare form data
        form_data = {
            self.username_field: username,
            self.password_field: password
        }
        
        # Add additional form fields from kwargs
        for key, value in kwargs.items():
            if key not in ['username', 'password'] and isinstance(value, (str, int, float)):
                form_data[key] = str(value)
        
        # Encode form data
        encoded_data = urllib.parse.urlencode(form_data)
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'LoadSpiker/1.0'
        }
        
        # Include existing session cookies
        session = self.session_manager.get_session(user_id)
        existing_headers = self.session_manager.prepare_request_headers(user_id, headers)
        
        # Make login request
        response = engine.execute_request(
            url=self.login_url,
            method='POST',
            headers=existing_headers,
            body=encoded_data
        )
        
        # Auto-handle cookies from response
        self.session_manager.auto_handle_cookies(user_id, response)
        
        # Check if authentication was successful
        success = self._check_authentication_success(response)
        
        if success:
            session.set('authenticated', True)
            session.set('auth_type', 'form')
            session.set('username', username)
            session.set('login_url', self.login_url)
        
        return {
            'success': success,
            'auth_type': 'form',
            'status_code': response.get('status_code'),
            'response_time_ms': response.get('response_time_ms'),
            'username': username if success else None,
            'message': 'Form authentication successful' if success else 'Form authentication failed'
        }
    
    def _check_authentication_success(self, response: Dict[str, Any]) -> bool:
        """Check if authentication was successful"""
        # Check status code first
        status_code = response.get('status_code', 0)
        if status_code >= 400:
            return False
        
        # If no success indicator specified, assume success based on status code
        if not self.success_indicator:
            return 200 <= status_code < 400
        
        # Check for success indicator in response body
        body = response.get('body', '')
        return self.success_indicator in body
    
    def check_session_validity(self, engine, user_id: Union[str, int], 
                              check_url: str = "") -> bool:
        """Check if current session is still valid"""
        check_url = check_url or self.login_url
        
        # Prepare headers with session cookies
        headers = self.session_manager.prepare_request_headers(user_id, {'User-Agent': 'LoadSpiker/1.0'})
        
        # Make test request
        response = engine.execute_request(
            url=check_url,
            method='GET',
            headers=headers
        )
        
        # Check if we got redirected to login or got unauthorized
        status_code = response.get('status_code', 0)
        return 200 <= status_code < 400


class OAuth2AuthorizationCodeFlow(AuthenticationFlow):
    """OAuth 2.0 Authorization Code flow (simplified for testing)"""
    
    def __init__(self, auth_url: str, token_url: str, client_id: str, 
                 client_secret: str, redirect_uri: str = "", scope: str = "",
                 name: str = "OAuth2AuthCode"):
        super().__init__(name)
        self.auth_url = auth_url
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scope = scope
    
    def authenticate(self, engine, user_id: Union[str, int], 
                    authorization_code: str = "", **kwargs) -> Dict[str, Any]:
        """Perform OAuth2 authorization code flow"""
        if not authorization_code:
            # Generate authorization URL for manual code retrieval
            auth_params = {
                'response_type': 'code',
                'client_id': self.client_id,
                'redirect_uri': self.redirect_uri,
                'scope': self.scope,
                'state': self._generate_state()
            }
            
            auth_query = urllib.parse.urlencode({k: v for k, v in auth_params.items() if v})
            authorization_url = f"{self.auth_url}?{auth_query}"
            
            session = self.session_manager.get_session(user_id)
            session.set('oauth2_state', auth_params['state'])
            session.set('authorization_url', authorization_url)
            
            return {
                'success': False,
                'auth_type': 'oauth2_auth_code',
                'authorization_url': authorization_url,
                'message': 'Authorization URL generated. Please obtain authorization code manually.'
            }
        
        # Exchange authorization code for token
        return self._exchange_code_for_token(engine, user_id, authorization_code, **kwargs)
    
    def _generate_state(self) -> str:
        """Generate random state parameter for OAuth2"""
        return secrets.token_urlsafe(32)
    
    def _exchange_code_for_token(self, engine, user_id: Union[str, int], 
                                authorization_code: str, **kwargs) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        token_data = {
            'grant_type': 'authorization_code',
            'code': authorization_code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri
        }
        
        form_data = urllib.parse.urlencode({k: v for k, v in token_data.items() if v})
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        
        response = engine.execute_request(
            url=self.token_url,
            method='POST',
            headers=headers,
            body=form_data
        )
        
        if not response.get('success', False):
            raise AuthenticationError(f"Token exchange failed: {response.get('error_message')}")
        
        try:
            token_response = json.loads(response.get('body', '{}'))
        except json.JSONDecodeError:
            raise AuthenticationError("Invalid JSON response from token endpoint")
        
        if 'access_token' not in token_response:
            raise AuthenticationError("No access_token in response")
        
        # Store tokens
        session = self.session_manager.get_session(user_id)
        access_token = token_response['access_token']
        expires_in = token_response.get('expires_in')
        refresh_token = token_response.get('refresh_token')
        
        expires_at = None
        if expires_in:
            expires_at = time.time() + expires_in
        
        session.set_token('bearer', access_token, expires_at)
        if refresh_token:
            session.set_token('refresh', refresh_token)
        
        session.set('authenticated', True)
        session.set('auth_type', 'oauth2')
        
        return {
            'success': True,
            'auth_type': 'oauth2',
            'access_token': access_token[:20] + '...' if len(access_token) > 20 else access_token,
            'expires_in': expires_in,
            'has_refresh_token': bool(refresh_token),
            'message': 'OAuth2 authentication successful'
        }


class CustomAuthenticationFlow(AuthenticationFlow):
    """Custom Authentication flow using user-defined function"""
    
    def __init__(self, auth_function: Callable, name: str = "CustomAuth"):
        super().__init__(name)
        self.auth_function = auth_function
    
    def authenticate(self, engine, user_id: Union[str, int], **kwargs) -> Dict[str, Any]:
        """Perform custom authentication using user-defined function"""
        try:
            result = self.auth_function(engine, user_id, self.session_manager, **kwargs)
            
            # Ensure result is a dictionary
            if not isinstance(result, dict):
                result = {'success': bool(result), 'message': str(result)}
            
            # Set authenticated status if successful
            if result.get('success', False):
                session = self.session_manager.get_session(user_id)
                session.set('authenticated', True)
                session.set('auth_type', 'custom')
            
            return result
            
        except Exception as e:
            raise AuthenticationError(f"Custom authentication failed: {str(e)}")


class AuthenticationManager:
    """Manages multiple authentication flows and provides unified interface"""
    
    def __init__(self):
        self.flows: Dict[str, AuthenticationFlow] = {}
        self.session_manager = get_session_manager()
    
    def register_flow(self, name: str, flow: AuthenticationFlow) -> None:
        """Register an authentication flow"""
        self.flows[name] = flow
    
    def authenticate(self, flow_name: str, engine, user_id: Union[str, int], 
                    **kwargs) -> Dict[str, Any]:
        """Authenticate using specified flow"""
        if flow_name not in self.flows:
            raise AuthenticationError(f"Authentication flow '{flow_name}' not found")
        
        flow = self.flows[flow_name]
        return flow.authenticate(engine, user_id, **kwargs)
    
    def is_authenticated(self, user_id: Union[str, int], flow_name: str = "") -> bool:
        """Check if user is authenticated"""
        if flow_name and flow_name in self.flows:
            return self.flows[flow_name].is_authenticated(user_id)
        
        # Check if user has any authentication
        session = self.session_manager.get_session(user_id)
        return session.get('authenticated', False)
    
    def logout(self, user_id: Union[str, int], flow_name: str = "") -> None:
        """Logout user from specified flow or all flows"""
        if flow_name and flow_name in self.flows:
            self.flows[flow_name].logout(user_id)
        else:
            # Logout from all flows
            for flow in self.flows.values():
                flow.logout(user_id)
    
    def get_auth_headers(self, user_id: Union[str, int]) -> Dict[str, str]:
        """Get authentication headers for requests"""
        return self.session_manager.prepare_request_headers(user_id)
    
    def list_flows(self) -> List[str]:
        """List available authentication flows"""
        return list(self.flows.keys())


# Global authentication manager instance
_global_auth_manager = AuthenticationManager()


def get_authentication_manager() -> AuthenticationManager:
    """Get the global authentication manager instance"""
    return _global_auth_manager


def create_basic_auth(username: str, password: str) -> BasicAuthenticationFlow:
    """Create a basic authentication flow"""
    return BasicAuthenticationFlow(username, password)


def create_bearer_auth(token: str = "", token_endpoint: str = "", 
                      client_id: str = "", client_secret: str = "") -> BearerTokenAuthenticationFlow:
    """Create a bearer token authentication flow"""
    return BearerTokenAuthenticationFlow(token, token_endpoint, client_id, client_secret)


def create_api_key_auth(api_key: str, header_name: str = "X-API-Key") -> APIKeyAuthenticationFlow:
    """Create an API key authentication flow"""
    return APIKeyAuthenticationFlow(api_key, header_name)


def create_form_auth(login_url: str, username_field: str = "username", 
                    password_field: str = "password", success_indicator: str = "") -> FormBasedAuthenticationFlow:
    """Create a form-based authentication flow"""
    return FormBasedAuthenticationFlow(login_url, username_field, password_field, success_indicator)


def create_oauth2_auth(auth_url: str, token_url: str, client_id: str, 
                      client_secret: str, redirect_uri: str = "") -> OAuth2AuthorizationCodeFlow:
    """Create an OAuth2 authorization code flow"""
    return OAuth2AuthorizationCodeFlow(auth_url, token_url, client_id, client_secret, redirect_uri)


def create_custom_auth(auth_function: Callable) -> CustomAuthenticationFlow:
    """Create a custom authentication flow"""
    return CustomAuthenticationFlow(auth_function)
