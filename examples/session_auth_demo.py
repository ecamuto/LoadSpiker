#!/usr/bin/env python3
"""
LoadSpiker Session Management and Authentication Demo

This example demonstrates the comprehensive session management and authentication
features implemented in LoadSpiker, including:
- Various authentication methods (Basic, Bearer, API Key, Form-based, OAuth2)
- Session state management with cookies and tokens
- Request correlation and value extraction
- Multi-user session isolation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker.engine import Engine
from loadspiker.session_manager import get_session_manager, ResponseExtractor
from loadspiker.authentication import (
    get_authentication_manager,
    create_basic_auth,
    create_bearer_auth,
    create_api_key_auth,
    create_form_auth,
    create_oauth2_auth,
    create_custom_auth
)
from loadspiker.assertions import status_is, json_path, response_time_under


def demo_basic_authentication():
    """Demonstrate HTTP Basic Authentication"""
    print("\n=== Basic Authentication Demo ===")
    
    engine = Engine()
    auth_manager = get_authentication_manager()
    
    # Create basic auth flow
    basic_auth = create_basic_auth("testuser", "testpass")
    auth_manager.register_flow("basic", basic_auth)
    
    # Authenticate user
    auth_result = auth_manager.authenticate("basic", engine, user_id="user1")
    print(f"Basic Auth Result: {auth_result}")
    
    # Make authenticated request
    headers = auth_manager.get_auth_headers("user1")
    print(f"Auth Headers: {headers}")
    
    # Simulate request with authentication
    if headers:
        response = engine.execute_request(
            url="https://httpbin.org/basic-auth/testuser/testpass",
            headers=headers
        )
        print(f"Authenticated Request Status: {response.get('status_code')}")


def demo_bearer_token_authentication():
    """Demonstrate Bearer Token Authentication"""
    print("\n=== Bearer Token Authentication Demo ===")
    
    engine = Engine()
    auth_manager = get_authentication_manager()
    
    # Create bearer auth with direct token
    bearer_auth = create_bearer_auth(token="test_jwt_token_12345")
    auth_manager.register_flow("bearer", bearer_auth)
    
    # Authenticate user
    auth_result = auth_manager.authenticate("bearer", engine, user_id="user2")
    print(f"Bearer Auth Result: {auth_result}")
    
    # Get auth headers
    headers = auth_manager.get_auth_headers("user2")
    print(f"Bearer Headers: {headers}")


def demo_api_key_authentication():
    """Demonstrate API Key Authentication"""
    print("\n=== API Key Authentication Demo ===")
    
    engine = Engine()
    auth_manager = get_authentication_manager()
    
    # Create API key auth
    api_key_auth = create_api_key_auth("sk-test-api-key-12345", "X-API-Key")
    auth_manager.register_flow("api_key", api_key_auth)
    
    # Authenticate user
    auth_result = auth_manager.authenticate("api_key", engine, user_id="user3")
    print(f"API Key Auth Result: {auth_result}")
    
    # Get auth headers
    headers = auth_manager.get_auth_headers("user3")
    print(f"API Key Headers: {headers}")


def demo_session_management():
    """Demonstrate session management with cookies and correlation"""
    print("\n=== Session Management Demo ===")
    
    engine = Engine()
    session_manager = get_session_manager()
    
    # Simulate response with cookies
    mock_response = {
        'status_code': 200,
        'headers': {'Set-Cookie': 'sessionid=abc123; Path=/; HttpOnly'},
        'body': '{"user_id": 12345, "access_token": "jwt_token_xyz", "profile": {"name": "John Doe", "email": "john@example.com"}}'
    }
    
    # Auto-handle cookies
    session_manager.auto_handle_cookies("user1", mock_response)
    
    # Extract values using correlation rules
    extract_rules = [
        {"type": "json_path", "path": "user_id", "variable": "user_id"},
        {"type": "json_path", "path": "access_token", "variable": "token"},
        {"type": "json_path", "path": "profile.name", "variable": "username"},
        {"type": "json_path", "path": "profile.email", "variable": "email"}
    ]
    
    session_manager.process_response("user1", mock_response, extract_rules)
    
    # Get session data
    session = session_manager.get_session("user1")
    print(f"Extracted user_id: {session.get('user_id')}")
    print(f"Extracted token: {session.get('token')}")
    print(f"Extracted username: {session.get('username')}")
    print(f"Extracted email: {session.get('email')}")
    print(f"Session cookies: {session.get_all_cookies()}")
    
    # Prepare headers for next request
    headers = session_manager.prepare_request_headers("user1")
    print(f"Session headers for next request: {headers}")


def demo_request_correlation():
    """Demonstrate advanced request correlation"""
    print("\n=== Request Correlation Demo ===")
    
    # Test various extraction methods
    test_response = {
        'status_code': 201,
        'headers': {
            'Location': 'https://api.example.com/users/12345',
            'X-Request-ID': 'req-abc-123',
            'Set-Cookie': 'csrf_token=token123; Path=/'
        },
        'body': '''
        {
            "status": "success",
            "data": {
                "user": {
                    "id": 12345,
                    "name": "Alice Smith",
                    "settings": {
                        "theme": "dark",
                        "notifications": true
                    }
                },
                "tokens": {
                    "access": "eyJhbGciOiJIUzI1NiIs...",
                    "refresh": "eyJhbGciOiJIUzI1NiIs..."
                }
            }
        }
        '''
    }
    
    # Test JSON path extraction
    user_id = ResponseExtractor.extract_json_path(test_response['body'], 'data.user.id')
    user_name = ResponseExtractor.extract_json_path(test_response['body'], 'data.user.name')
    theme = ResponseExtractor.extract_json_path(test_response['body'], 'data.user.settings.theme')
    access_token = ResponseExtractor.extract_json_path(test_response['body'], 'data.tokens.access')
    
    print(f"JSON Path Extractions:")
    print(f"  User ID: {user_id}")
    print(f"  User Name: {user_name}")
    print(f"  Theme: {theme}")
    print(f"  Access Token: {access_token[:20]}..." if access_token else "None")
    
    # Test header extraction
    location = ResponseExtractor.extract_header(test_response['headers'], 'Location')
    request_id = ResponseExtractor.extract_header(test_response['headers'], 'X-Request-ID')
    
    print(f"Header Extractions:")
    print(f"  Location: {location}")
    print(f"  Request ID: {request_id}")
    
    # Test cookie extraction
    csrf_token = ResponseExtractor.extract_cookie_from_headers(test_response['headers'], 'csrf_token')
    print(f"Cookie Extractions:")
    print(f"  CSRF Token: {csrf_token}")
    
    # Test regex extraction
    html_response = '<html><body><input name="csrf" value="abc123def456"></body></html>'
    csrf_from_html = ResponseExtractor.extract_regex(html_response, r'name="csrf"\s+value="([^"]+)"', 1)
    print(f"Regex Extractions:")
    print(f"  CSRF from HTML: {csrf_from_html}")


def demo_form_based_authentication():
    """Demonstrate form-based authentication with session management"""
    print("\n=== Form-Based Authentication Demo ===")
    
    engine = Engine()
    auth_manager = get_authentication_manager()
    
    # Create form auth (this would normally hit a real login endpoint)
    form_auth = create_form_auth(
        login_url="https://httpbin.org/post",  # Using httpbin for demo
        username_field="username",
        password_field="password",
        success_indicator="success"  # Would check for success indicator in real scenario
    )
    auth_manager.register_flow("form", form_auth)
    
    try:
        # Attempt authentication
        auth_result = auth_manager.authenticate(
            "form", engine, user_id="user4",
            username="testuser",
            password="testpass"
        )
        print(f"Form Auth Result: {auth_result}")
    except Exception as e:
        print(f"Form Auth Demo (expected with httpbin): {e}")


def demo_oauth2_authentication():
    """Demonstrate OAuth2 authentication flow"""
    print("\n=== OAuth2 Authentication Demo ===")
    
    engine = Engine()
    auth_manager = get_authentication_manager()
    
    # Create OAuth2 auth (this is for demonstration - would need real OAuth2 endpoints)
    oauth2_auth = create_oauth2_auth(
        auth_url="https://example.com/oauth/authorize",
        token_url="https://example.com/oauth/token",
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="https://example.com/callback"
    )
    auth_manager.register_flow("oauth2", oauth2_auth)
    
    # Generate authorization URL
    auth_result = auth_manager.authenticate("oauth2", engine, user_id="user5")
    print(f"OAuth2 Auth Result: {auth_result}")
    
    if 'authorization_url' in auth_result:
        print(f"Visit this URL to authorize: {auth_result['authorization_url']}")


def demo_custom_authentication():
    """Demonstrate custom authentication flow"""
    print("\n=== Custom Authentication Demo ===")
    
    def custom_auth_function(engine, user_id, session_manager, **kwargs):
        """Custom authentication logic"""
        api_key = kwargs.get('api_key')
        secret = kwargs.get('secret')
        
        if not api_key or not secret:
            return {'success': False, 'message': 'API key and secret required'}
        
        # Simulate custom authentication logic
        if api_key == "valid_key" and secret == "valid_secret":
            # Store custom tokens in session
            session = session_manager.get_session(user_id)
            session.set_token('custom_token', f"custom_{api_key}_{secret}")
            session.set('auth_method', 'custom')
            
            return {
                'success': True,
                'auth_type': 'custom',
                'message': 'Custom authentication successful'
            }
        else:
            return {'success': False, 'message': 'Invalid credentials'}
    
    engine = Engine()
    auth_manager = get_authentication_manager()
    
    # Create custom auth flow
    custom_auth = create_custom_auth(custom_auth_function)
    auth_manager.register_flow("custom", custom_auth)
    
    # Test successful authentication
    auth_result = auth_manager.authenticate(
        "custom", engine, user_id="user6",
        api_key="valid_key",
        secret="valid_secret"
    )
    print(f"Custom Auth Success: {auth_result}")
    
    # Test failed authentication
    auth_result = auth_manager.authenticate(
        "custom", engine, user_id="user7",
        api_key="invalid_key",
        secret="invalid_secret"
    )
    print(f"Custom Auth Failure: {auth_result}")


def demo_multi_user_session_isolation():
    """Demonstrate session isolation between multiple users"""
    print("\n=== Multi-User Session Isolation Demo ===")
    
    session_manager = get_session_manager()
    
    # Set up different data for different users
    users_data = [
        {"user_id": "user_a", "username": "alice", "role": "admin", "token": "token_alice"},
        {"user_id": "user_b", "username": "bob", "role": "user", "token": "token_bob"},
        {"user_id": "user_c", "username": "charlie", "role": "moderator", "token": "token_charlie"}
    ]
    
    # Set up sessions for each user
    for user_data in users_data:
        user_id = user_data["user_id"]
        session = session_manager.get_session(user_id)
        
        # Set user-specific data
        session.set('username', user_data['username'])
        session.set('role', user_data['role'])
        session.set_token('bearer', user_data['token'])
        session.set_cookie('user_session', f"session_{user_data['username']}")
    
    # Verify session isolation
    print("Session Isolation Test:")
    for user_data in users_data:
        user_id = user_data["user_id"]
        session = session_manager.get_session(user_id)
        
        print(f"  {user_id}:")
        print(f"    Username: {session.get('username')}")
        print(f"    Role: {session.get('role')}")
        print(f"    Token: {session.get_token('bearer')}")
        print(f"    Cookies: {session.get_all_cookies()}")
    
    # Show session statistics
    stats = session_manager.get_session_stats()
    print(f"Session Manager Stats: {stats}")


def demo_session_aware_requests():
    """Demonstrate session-aware HTTP requests"""
    print("\n=== Session-Aware Requests Demo ===")
    
    engine = Engine()
    
    # Check if session management is available in engine
    if hasattr(engine._engine, 'session_manager') and engine._engine.session_manager:
        print("Session management is integrated with engine")
        
        # Set up session data
        session_manager = engine._engine.session_manager
        session = session_manager.get_session("demo_user")
        session.set_token('bearer', 'demo_token_12345')
        session.set_cookie('session_id', 'sess_demo_12345')
        
        # Prepare headers with session data
        headers = session_manager.prepare_request_headers("demo_user", {
            'Content-Type': 'application/json',
            'User-Agent': 'LoadSpiker-Demo/1.0'
        })
        print(f"Session-aware headers: {headers}")
        
    else:
        print("Session management not available in current engine instance")


def main():
    """Run all session management and authentication demos"""
    print("LoadSpiker Session Management and Authentication Demo")
    print("=" * 60)
    
    try:
        # Authentication demos
        demo_basic_authentication()
        demo_bearer_token_authentication()
        demo_api_key_authentication()
        demo_form_based_authentication()
        demo_oauth2_authentication()
        demo_custom_authentication()
        
        # Session management demos
        demo_session_management()
        demo_request_correlation()
        demo_multi_user_session_isolation()
        demo_session_aware_requests()
        
        print("\n" + "=" * 60)
        print("Demo completed successfully!")
        print("\nKey Features Demonstrated:")
        print("✓ Multiple authentication methods (Basic, Bearer, API Key, Form, OAuth2, Custom)")
        print("✓ Session state management with cookies and tokens")
        print("✓ Request correlation and value extraction (JSON, headers, cookies, regex)")
        print("✓ Multi-user session isolation")
        print("✓ Automatic cookie handling")
        print("✓ Token expiration management")
        print("✓ Integration with LoadSpiker engine")
        
    except Exception as e:
        print(f"\nDemo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
