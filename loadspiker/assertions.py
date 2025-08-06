"""
Assertion system for LoadSpiker load testing
"""

import json
import re
from typing import Any, Dict, List, Callable, Optional, Union
from xml.etree import ElementTree as ET


class AssertionError(Exception):
    """Custom assertion error for LoadSpiker"""
    pass


class Assertion:
    """Base class for all assertions"""
    
    def __init__(self, message: str = ""):
        self.message = message
    
    def check(self, response: Dict[str, Any]) -> bool:
        """Check if assertion passes. Override in subclasses."""
        raise NotImplementedError
    
    def get_error_message(self, response: Dict[str, Any]) -> str:
        """Get detailed error message for failed assertion"""
        return self.message or "Assertion failed"


class StatusCodeAssertion(Assertion):
    """Assert HTTP status code"""
    
    def __init__(self, expected_status: int, message: str = ""):
        super().__init__(message)
        self.expected_status = expected_status
    
    def check(self, response: Dict[str, Any]) -> bool:
        return response.get('status_code') == self.expected_status
    
    def get_error_message(self, response: Dict[str, Any]) -> str:
        actual = response.get('status_code')
        return (self.message or 
                f"Expected status {self.expected_status}, got {actual}")


class ResponseTimeAssertion(Assertion):
    """Assert response time is within limit"""
    
    def __init__(self, max_time_ms: int, message: str = ""):
        super().__init__(message)
        self.max_time_ms = max_time_ms
    
    def check(self, response: Dict[str, Any]) -> bool:
        time_ms = response.get('response_time_us', 0) / 1000
        return time_ms <= self.max_time_ms
    
    def get_error_message(self, response: Dict[str, Any]) -> str:
        actual_ms = response.get('response_time_us', 0) / 1000
        return (self.message or 
                f"Response time {actual_ms:.2f}ms exceeded limit {self.max_time_ms}ms")


class BodyContainsAssertion(Assertion):
    """Assert response body contains text"""
    
    def __init__(self, expected_text: str, case_sensitive: bool = True, message: str = ""):
        super().__init__(message)
        self.expected_text = expected_text
        self.case_sensitive = case_sensitive
    
    def check(self, response: Dict[str, Any]) -> bool:
        body = response.get('body', '')
        if not self.case_sensitive:
            body = body.lower()
            expected = self.expected_text.lower()
        else:
            expected = self.expected_text
        return expected in body
    
    def get_error_message(self, response: Dict[str, Any]) -> str:
        return (self.message or 
                f"Response body does not contain '{self.expected_text}'")


class RegexAssertion(Assertion):
    """Assert response body matches regex pattern"""
    
    def __init__(self, pattern: str, message: str = ""):
        super().__init__(message)
        self.pattern = re.compile(pattern)
    
    def check(self, response: Dict[str, Any]) -> bool:
        body = response.get('body', '')
        return bool(self.pattern.search(body))
    
    def get_error_message(self, response: Dict[str, Any]) -> str:
        return (self.message or 
                f"Response body does not match pattern '{self.pattern.pattern}'")


class JSONPathAssertion(Assertion):
    """Assert JSON response using JSONPath-like syntax"""
    
    def __init__(self, path: str, expected_value: Any = None, exists: bool = True, message: str = ""):
        super().__init__(message)
        self.path = path
        self.expected_value = expected_value
        self.exists = exists
    
    def check(self, response: Dict[str, Any]) -> bool:
        try:
            data = json.loads(response.get('body', ''))
            value = self._get_nested_value(data, self.path)
            
            if not self.exists:
                return value is None
            
            if self.expected_value is not None:
                return value == self.expected_value
            
            return value is not None
            
        except (json.JSONDecodeError, KeyError, TypeError):
            return not self.exists
    
    def _get_nested_value(self, data: Any, path: str) -> Any:
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
    
    def get_error_message(self, response: Dict[str, Any]) -> str:
        if self.message:
            return self.message
        
        if not self.exists:
            return f"JSON path '{self.path}' should not exist"
        elif self.expected_value is not None:
            return f"JSON path '{self.path}' expected '{self.expected_value}'"
        else:
            return f"JSON path '{self.path}' does not exist"


class HeaderAssertion(Assertion):
    """Assert HTTP response header"""
    
    def __init__(self, header_name: str, expected_value: str = None, exists: bool = True, message: str = ""):
        super().__init__(message)
        self.header_name = header_name.lower()
        self.expected_value = expected_value
        self.exists = exists
    
    def check(self, response: Dict[str, Any]) -> bool:
        headers = self._parse_headers(response.get('headers', ''))
        header_value = headers.get(self.header_name)
        
        if not self.exists:
            return header_value is None
        
        if self.expected_value is not None:
            return header_value == self.expected_value
        
        return header_value is not None
    
    def _parse_headers(self, headers_str: str) -> Dict[str, str]:
        """Parse header string into dictionary"""
        headers = {}
        for line in headers_str.split('\n'):
            if ':' in line:
                key, value = line.split(':', 1)
                headers[key.strip().lower()] = value.strip()
        return headers
    
    def get_error_message(self, response: Dict[str, Any]) -> str:
        if self.message:
            return self.message
        
        if not self.exists:
            return f"Header '{self.header_name}' should not exist"
        elif self.expected_value is not None:
            return f"Header '{self.header_name}' expected '{self.expected_value}'"
        else:
            return f"Header '{self.header_name}' does not exist"


class CustomAssertion(Assertion):
    """Custom assertion using user-defined function"""
    
    def __init__(self, assertion_func: Callable[[Dict[str, Any]], bool], message: str = ""):
        super().__init__(message)
        self.assertion_func = assertion_func
    
    def check(self, response: Dict[str, Any]) -> bool:
        try:
            return self.assertion_func(response)
        except Exception:
            return False
    
    def get_error_message(self, response: Dict[str, Any]) -> str:
        return self.message or "Custom assertion failed"


class AssertionGroup:
    """Group of assertions with AND/OR logic"""
    
    def __init__(self, logic: str = "AND"):
        self.logic = logic.upper()
        self.assertions: List[Assertion] = []
        self.failed_assertions: List[tuple] = []  # (assertion, error_message)
    
    def add(self, assertion: Assertion):
        """Add assertion to group"""
        self.assertions.append(assertion)
        return self
    
    def check_all(self, response: Dict[str, Any]) -> bool:
        """Check all assertions in group"""
        self.failed_assertions = []
        results = []
        
        for assertion in self.assertions:
            passed = assertion.check(response)
            if not passed:
                error_msg = assertion.get_error_message(response)
                self.failed_assertions.append((assertion, error_msg))
            results.append(passed)
        
        if self.logic == "AND":
            return all(results)
        elif self.logic == "OR":
            return any(results)
        else:
            raise ValueError(f"Unknown logic operator: {self.logic}")
    
    def get_failure_report(self) -> str:
        """Get detailed failure report"""
        if not self.failed_assertions:
            return ""
        
        lines = [f"Assertion group ({self.logic}) failed:"]
        for i, (assertion, error_msg) in enumerate(self.failed_assertions, 1):
            lines.append(f"  {i}. {error_msg}")
        
        return "\n".join(lines)


# Convenience functions for creating common assertions
def status_is(code: int, message: str = "") -> StatusCodeAssertion:
    """Assert status code equals expected value"""
    return StatusCodeAssertion(code, message)


def response_time_under(max_ms: int, message: str = "") -> ResponseTimeAssertion:
    """Assert response time is under maximum"""
    return ResponseTimeAssertion(max_ms, message)


def body_contains(text: str, case_sensitive: bool = True, message: str = "") -> BodyContainsAssertion:
    """Assert body contains text"""
    return BodyContainsAssertion(text, case_sensitive, message)


def body_matches(pattern: str, message: str = "") -> RegexAssertion:
    """Assert body matches regex pattern"""
    return RegexAssertion(pattern, message)


def json_path(path: str, expected_value: Any = None, exists: bool = True, message: str = "") -> JSONPathAssertion:
    """Assert JSON path exists and optionally equals value"""
    return JSONPathAssertion(path, expected_value, exists, message)


def header_exists(name: str, value: str = None, message: str = "") -> HeaderAssertion:
    """Assert header exists and optionally equals value"""
    return HeaderAssertion(name, value, True, message)


def custom_assertion(func: Callable[[Dict[str, Any]], bool], message: str = "") -> CustomAssertion:
    """Create custom assertion with user-defined function"""
    return CustomAssertion(func, message)


# Assertion runner for integration with scenarios
def run_assertions(response: Dict[str, Any], assertions: List[Assertion], 
                  fail_fast: bool = True) -> tuple:
    """
    Run assertions against response
    
    Args:
        response: HTTP response dictionary
        assertions: List of assertions to check
        fail_fast: Stop on first failure if True
        
    Returns:
        Tuple of (success: bool, failure_messages: List[str])
    """
    failed_messages = []
    
    for assertion in assertions:
        if not assertion.check(response):
            error_msg = assertion.get_error_message(response)
            failed_messages.append(error_msg)
            
            if fail_fast:
                break
    
    return len(failed_messages) == 0, failed_messages
