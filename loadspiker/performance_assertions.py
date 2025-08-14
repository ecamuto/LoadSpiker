"""
Performance assertion system for LoadSpiker load testing

This module provides assertions that evaluate aggregate performance metrics
rather than individual request responses.
"""

import statistics
from typing import Any, Dict, List, Callable, Optional, Union

# Base class for performance assertions (standalone, doesn't depend on regular assertions)
class PerformanceAssertion:
    """Base class for performance assertions that work with aggregated metrics"""
    
    def __init__(self, message: str = ""):
        self.message = message
    
    def check(self, response: Dict[str, Any]) -> bool:
        """
        Performance assertions don't use individual responses.
        This method should not be called directly.
        """
        raise NotImplementedError("Use check_metrics() for performance assertions")
    
    def check_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Check assertion against performance metrics. Override in subclasses."""
        raise NotImplementedError
    
    def get_metrics_error_message(self, metrics: Dict[str, Any]) -> str:
        """Get detailed error message for failed metric assertion"""
        return self.message or "Performance assertion failed"


class ThroughputAssertion(PerformanceAssertion):
    """Assert minimum requests per second"""
    
    def __init__(self, min_rps: float, message: str = ""):
        super().__init__(message)
        self.min_rps = min_rps
    
    def check_metrics(self, metrics: Dict[str, Any]) -> bool:
        actual_rps = metrics.get('requests_per_second', 0.0)
        return actual_rps >= self.min_rps
    
    def get_metrics_error_message(self, metrics: Dict[str, Any]) -> str:
        actual_rps = metrics.get('requests_per_second', 0.0)
        return (self.message or 
                f"Throughput {actual_rps:.2f} RPS is below minimum {self.min_rps} RPS")


class AverageResponseTimeAssertion(PerformanceAssertion):
    """Assert maximum average response time"""
    
    def __init__(self, max_avg_ms: float, message: str = ""):
        super().__init__(message)
        self.max_avg_ms = max_avg_ms
    
    def check_metrics(self, metrics: Dict[str, Any]) -> bool:
        actual_avg_ms = metrics.get('avg_response_time_ms', 0.0)
        return actual_avg_ms <= self.max_avg_ms
    
    def get_metrics_error_message(self, metrics: Dict[str, Any]) -> str:
        actual_avg_ms = metrics.get('avg_response_time_ms', 0.0)
        return (self.message or 
                f"Average response time {actual_avg_ms:.2f}ms exceeds limit {self.max_avg_ms}ms")


class ErrorRateAssertion(PerformanceAssertion):
    """Assert maximum error rate percentage"""
    
    def __init__(self, max_error_rate: float, message: str = ""):
        super().__init__(message)
        self.max_error_rate = max_error_rate
    
    def check_metrics(self, metrics: Dict[str, Any]) -> bool:
        total_requests = metrics.get('total_requests', 0)
        failed_requests = metrics.get('failed_requests', 0)
        
        if total_requests == 0:
            return True  # No requests means no errors
        
        error_rate = (failed_requests / total_requests) * 100
        return error_rate <= self.max_error_rate
    
    def get_metrics_error_message(self, metrics: Dict[str, Any]) -> str:
        total_requests = metrics.get('total_requests', 0)
        failed_requests = metrics.get('failed_requests', 0)
        
        if total_requests == 0:
            error_rate = 0.0
        else:
            error_rate = (failed_requests / total_requests) * 100
        
        return (self.message or 
                f"Error rate {error_rate:.2f}% exceeds limit {self.max_error_rate}%")


class MaxResponseTimeAssertion(PerformanceAssertion):
    """Assert maximum response time is below threshold"""
    
    def __init__(self, max_time_ms: float, message: str = ""):
        super().__init__(message)
        self.max_time_ms = max_time_ms
    
    def check_metrics(self, metrics: Dict[str, Any]) -> bool:
        max_time_us = metrics.get('max_response_time_us', 0)
        max_time_ms = max_time_us / 1000
        return max_time_ms <= self.max_time_ms
    
    def get_metrics_error_message(self, metrics: Dict[str, Any]) -> str:
        max_time_us = metrics.get('max_response_time_us', 0)
        max_time_ms = max_time_us / 1000
        return (self.message or 
                f"Maximum response time {max_time_ms:.2f}ms exceeds limit {self.max_time_ms}ms")


class SuccessRateAssertion(PerformanceAssertion):
    """Assert minimum success rate percentage"""
    
    def __init__(self, min_success_rate: float, message: str = ""):
        super().__init__(message)
        self.min_success_rate = min_success_rate
    
    def check_metrics(self, metrics: Dict[str, Any]) -> bool:
        total_requests = metrics.get('total_requests', 0)
        successful_requests = metrics.get('successful_requests', 0)
        
        if total_requests == 0:
            return True  # No requests means 100% success rate
        
        success_rate = (successful_requests / total_requests) * 100
        return success_rate >= self.min_success_rate
    
    def get_metrics_error_message(self, metrics: Dict[str, Any]) -> str:
        total_requests = metrics.get('total_requests', 0)
        successful_requests = metrics.get('successful_requests', 0)
        
        if total_requests == 0:
            success_rate = 100.0
        else:
            success_rate = (successful_requests / total_requests) * 100
        
        return (self.message or 
                f"Success rate {success_rate:.2f}% is below minimum {self.min_success_rate}%")


class TotalRequestsAssertion(PerformanceAssertion):
    """Assert minimum total number of requests processed"""
    
    def __init__(self, min_requests: int, message: str = ""):
        super().__init__(message)
        self.min_requests = min_requests
    
    def check_metrics(self, metrics: Dict[str, Any]) -> bool:
        total_requests = metrics.get('total_requests', 0)
        return total_requests >= self.min_requests
    
    def get_metrics_error_message(self, metrics: Dict[str, Any]) -> str:
        total_requests = metrics.get('total_requests', 0)
        return (self.message or 
                f"Total requests {total_requests} is below minimum {self.min_requests}")


class CustomPerformanceAssertion(PerformanceAssertion):
    """Custom performance assertion using user-defined function"""
    
    def __init__(self, assertion_func: Callable[[Dict[str, Any]], bool], message: str = ""):
        super().__init__(message)
        self.assertion_func = assertion_func
    
    def check_metrics(self, metrics: Dict[str, Any]) -> bool:
        try:
            return self.assertion_func(metrics)
        except Exception:
            return False
    
    def get_metrics_error_message(self, metrics: Dict[str, Any]) -> str:
        return self.message or "Custom performance assertion failed"


class PerformanceAssertionGroup:
    """Group of performance assertions with AND/OR logic"""
    
    def __init__(self, logic: str = "AND"):
        self.logic = logic.upper()
        self.assertions: List[PerformanceAssertion] = []
        self.failed_assertions: List[tuple] = []  # (assertion, error_message)
    
    def add(self, assertion: PerformanceAssertion):
        """Add assertion to group"""
        self.assertions.append(assertion)
        return self
    
    def check_all_metrics(self, metrics: Dict[str, Any]) -> bool:
        """Check all assertions in group against metrics"""
        self.failed_assertions = []
        results = []
        
        for assertion in self.assertions:
            passed = assertion.check_metrics(metrics)
            if not passed:
                error_msg = assertion.get_metrics_error_message(metrics)
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
        
        lines = [f"Performance assertion group ({self.logic}) failed:"]
        for i, (assertion, error_msg) in enumerate(self.failed_assertions, 1):
            lines.append(f"  {i}. {error_msg}")
        
        return "\n".join(lines)


# Convenience functions for creating common performance assertions
def throughput_at_least(min_rps: float, message: str = "") -> ThroughputAssertion:
    """Assert minimum throughput in requests per second"""
    return ThroughputAssertion(min_rps, message)


def avg_response_time_under(max_ms: float, message: str = "") -> AverageResponseTimeAssertion:
    """Assert average response time is under maximum"""
    return AverageResponseTimeAssertion(max_ms, message)


def error_rate_below(max_rate: float, message: str = "") -> ErrorRateAssertion:
    """Assert error rate is below maximum percentage"""
    return ErrorRateAssertion(max_rate, message)


def success_rate_at_least(min_rate: float, message: str = "") -> SuccessRateAssertion:
    """Assert success rate is at least minimum percentage"""
    return SuccessRateAssertion(min_rate, message)


def max_response_time_under(max_ms: float, message: str = "") -> MaxResponseTimeAssertion:
    """Assert maximum response time is under limit"""
    return MaxResponseTimeAssertion(max_ms, message)


def total_requests_at_least(min_requests: int, message: str = "") -> TotalRequestsAssertion:
    """Assert minimum total number of requests processed"""
    return TotalRequestsAssertion(min_requests, message)


def custom_performance_assertion(func: Callable[[Dict[str, Any]], bool], message: str = "") -> CustomPerformanceAssertion:
    """Create custom performance assertion with user-defined function"""
    return CustomPerformanceAssertion(func, message)


# Performance assertion runner for integration with scenarios
def run_performance_assertions(metrics: Dict[str, Any], assertions: List[PerformanceAssertion], 
                              fail_fast: bool = True) -> tuple:
    """
    Run performance assertions against metrics
    
    Args:
        metrics: Performance metrics dictionary
        assertions: List of performance assertions to check
        fail_fast: Stop on first failure if True
        
    Returns:
        Tuple of (success: bool, failure_messages: List[str])
    """
    failed_messages = []
    
    for assertion in assertions:
        if not assertion.check_metrics(metrics):
            error_msg = assertion.get_metrics_error_message(metrics)
            failed_messages.append(error_msg)
            
            if fail_fast:
                break
    
    return len(failed_messages) == 0, failed_messages
