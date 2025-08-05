"""
Utility functions for load testing
"""

import time
import random
from typing import Callable, Any, Dict, List
from .engine import Engine


def ramp_up(start_users: int, end_users: int, duration: int, step_duration: int = 5):
    """
    Create a ramp-up load pattern
    
    Args:
        start_users: Initial number of users
        end_users: Final number of users
        duration: Total ramp-up duration in seconds
        step_duration: Duration of each step in seconds
        
    Returns:
        Generator yielding (users, duration) tuples
    """
    steps = duration // step_duration
    user_increment = (end_users - start_users) / steps
    
    current_users = start_users
    for _ in range(steps):
        yield int(current_users), step_duration
        current_users += user_increment
    
    # Final step to reach exact end_users
    remaining_time = duration % step_duration
    if remaining_time > 0:
        yield end_users, remaining_time


def constant_load(users: int, duration: int):
    """
    Create a constant load pattern
    
    Args:
        users: Number of concurrent users
        duration: Duration in seconds
        
    Returns:
        Generator yielding (users, duration) tuple
    """
    yield users, duration


def spike_test(normal_users: int, spike_users: int, 
               normal_duration: int, spike_duration: int):
    """
    Create a spike test pattern
    
    Args:
        normal_users: Normal load user count
        spike_users: Spike load user count
        normal_duration: Duration of normal load in seconds
        spike_duration: Duration of spike in seconds
        
    Returns:
        Generator yielding (users, duration) tuples
    """
    yield normal_users, normal_duration // 2
    yield spike_users, spike_duration
    yield normal_users, normal_duration // 2


def stress_test(max_users: int, step_size: int = 10, step_duration: int = 30):
    """
    Create a stress test pattern that gradually increases load
    
    Args:
        max_users: Maximum number of users to reach
        step_size: User increment per step
        step_duration: Duration of each step
        
    Returns:
        Generator yielding (users, duration) tuples
    """
    current_users = step_size
    while current_users <= max_users:
        yield current_users, step_duration
        current_users += step_size


def wait_for_condition(condition_func: Callable[[], bool], 
                      timeout: int = 30, check_interval: float = 1.0) -> bool:
    """
    Wait for a condition to become true with timeout
    
    Args:
        condition_func: Function that returns boolean
        timeout: Maximum wait time in seconds
        check_interval: Time between checks in seconds
        
    Returns:
        True if condition met, False if timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(check_interval)
    return False


def random_delay(min_ms: int, max_ms: int):
    """
    Add random delay to simulate realistic user behavior
    
    Args:
        min_ms: Minimum delay in milliseconds
        max_ms: Maximum delay in milliseconds
    """
    delay_ms = random.randint(min_ms, max_ms)
    time.sleep(delay_ms / 1000.0)


def measure_time(func: Callable) -> tuple:
    """
    Measure execution time of a function
    
    Args:
        func: Function to measure
        
    Returns:
        Tuple of (result, execution_time_ms)
    """
    start_time = time.time()
    result = func()
    end_time = time.time()
    execution_time_ms = (end_time - start_time) * 1000
    return result, execution_time_ms


def validate_response(response: Dict[str, Any], 
                     expected_status: int = 200,
                     expected_content: str = None,
                     max_response_time_ms: int = None) -> bool:
    """
    Validate HTTP response meets expectations
    
    Args:
        response: Response dictionary from engine
        expected_status: Expected HTTP status code
        expected_content: Expected content in response body
        max_response_time_ms: Maximum acceptable response time
        
    Returns:
        True if response is valid, False otherwise
    """
    # Check status code
    if response.get('status_code') != expected_status:
        return False
    
    # Check content if specified
    if expected_content and expected_content not in response.get('body', ''):
        return False
    
    # Check response time if specified
    if max_response_time_ms:
        response_time_ms = response.get('response_time_us', 0) / 1000
        if response_time_ms > max_response_time_ms:
            return False
    
    return True


def create_user_session(engine: Engine, session_requests: List[Dict[str, Any]]):
    """
    Create a user session that executes multiple requests in sequence
    
    Args:
        engine: Load test engine instance
        session_requests: List of request dictionaries
        
    Returns:
        List of responses
    """
    responses = []
    
    for req in session_requests:
        response = engine.execute_request(
            url=req['url'],
            method=req.get('method', 'GET'),
            headers=req.get('headers'),
            body=req.get('body', ''),
            timeout_ms=req.get('timeout_ms', 30000)
        )
        responses.append(response)
        
        # Add realistic delay between requests
        if 'delay_ms' in req:
            time.sleep(req['delay_ms'] / 1000.0)
    
    return responses


def generate_test_data(count: int, data_template: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate test data based on a template
    
    Args:
        count: Number of data items to generate
        data_template: Template with placeholders
        
    Returns:
        List of generated data items
    """
    import uuid
    import datetime
    
    generated_data = []
    
    for i in range(count):
        data_item = {}
        for key, value in data_template.items():
            if isinstance(value, str):
                # Replace placeholders
                processed_value = value.replace('${INDEX}', str(i))
                processed_value = processed_value.replace('${UUID}', str(uuid.uuid4()))
                processed_value = processed_value.replace('${TIMESTAMP}', str(int(time.time())))
                processed_value = processed_value.replace('${DATETIME}', datetime.datetime.now().isoformat())
                processed_value = processed_value.replace('${RANDOM_INT}', str(random.randint(1, 1000)))
                data_item[key] = processed_value
            else:
                data_item[key] = value
        
        generated_data.append(data_item)
    
    return generated_data


def parse_load_pattern(pattern_string: str):
    """
    Parse load pattern from string format
    
    Supported formats:
    - "constant:100:60" - 100 users for 60 seconds
    - "ramp:10:100:60" - ramp from 10 to 100 users over 60 seconds
    - "spike:50:200:30" - 50 users, spike to 200 for 30 seconds
    
    Args:
        pattern_string: Pattern specification string
        
    Returns:
        Generator yielding (users, duration) tuples
    """
    parts = pattern_string.split(':')
    pattern_type = parts[0].lower()
    
    if pattern_type == 'constant':
        users, duration = int(parts[1]), int(parts[2])
        return constant_load(users, duration)
    
    elif pattern_type == 'ramp':
        start_users, end_users, duration = int(parts[1]), int(parts[2]), int(parts[3])
        return ramp_up(start_users, end_users, duration)
    
    elif pattern_type == 'spike':
        normal_users, spike_users, spike_duration = int(parts[1]), int(parts[2]), int(parts[3])
        normal_duration = 60  # Default normal duration
        if len(parts) > 4:
            normal_duration = int(parts[4])
        return spike_test(normal_users, spike_users, normal_duration, spike_duration)
    
    else:
        raise ValueError(f"Unknown load pattern type: {pattern_type}")


def calculate_percentiles(values: List[float], percentiles: List[int] = [50, 90, 95, 99]) -> Dict[int, float]:
    """
    Calculate percentiles from a list of values
    
    Args:
        values: List of numeric values
        percentiles: List of percentile values to calculate
        
    Returns:
        Dictionary mapping percentile to value
    """
    if not values:
        return {p: 0.0 for p in percentiles}
    
    sorted_values = sorted(values)
    n = len(sorted_values)
    
    result = {}
    for p in percentiles:
        index = int((p / 100.0) * (n - 1))
        result[p] = sorted_values[index]
    
    return result