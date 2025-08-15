#!/usr/bin/env python3
"""
Comprehensive pytest test suite for LoadSpiker Performance Assertions
Provides exhaustive regression testing coverage
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Import performance assertions directly (avoiding main package import conflict)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'loadspiker'))
import performance_assertions

# Extract the classes and functions we need
from performance_assertions import (
    PerformanceAssertion,
    ThroughputAssertion, 
    AverageResponseTimeAssertion,
    ErrorRateAssertion,
    SuccessRateAssertion,
    MaxResponseTimeAssertion,
    TotalRequestsAssertion,
    CustomPerformanceAssertion,
    PerformanceAssertionGroup,
    throughput_at_least,
    avg_response_time_under,
    error_rate_below,
    success_rate_at_least,
    max_response_time_under,
    total_requests_at_least,
    custom_performance_assertion,
    run_performance_assertions
)


class TestPerformanceAssertionBase:
    """Tests for the base PerformanceAssertion class"""
    
    def test_base_class_initialization(self):
        """Test base class can be initialized with message"""
        assertion = PerformanceAssertion("Test message")
        assert assertion.message == "Test message"
        
    def test_base_class_empty_message(self):
        """Test base class with empty message"""
        assertion = PerformanceAssertion()
        assert assertion.message == ""
    
    def test_check_not_implemented(self):
        """Test that check() raises NotImplementedError"""
        assertion = PerformanceAssertion()
        with pytest.raises(NotImplementedError):
            assertion.check({})
    
    def test_check_metrics_not_implemented(self):
        """Test that check_metrics() raises NotImplementedError"""
        assertion = PerformanceAssertion()
        with pytest.raises(NotImplementedError):
            assertion.check_metrics({})
    
    def test_get_metrics_error_message_default(self):
        """Test default error message"""
        assertion = PerformanceAssertion()
        assert assertion.get_metrics_error_message({}) == "Performance assertion failed"
    
    def test_get_metrics_error_message_custom(self):
        """Test custom error message"""
        assertion = PerformanceAssertion("Custom error")
        assert assertion.get_metrics_error_message({}) == "Custom error"


class TestThroughputAssertion:
    """Tests for ThroughputAssertion"""
    
    def test_initialization(self):
        """Test ThroughputAssertion initialization"""
        assertion = ThroughputAssertion(10.0, "Test message")
        assert assertion.min_rps == 10.0
        assert assertion.message == "Test message"
    
    def test_check_metrics_pass(self):
        """Test throughput assertion that passes"""
        assertion = ThroughputAssertion(5.0)
        metrics = {'requests_per_second': 10.0}
        assert assertion.check_metrics(metrics) is True
    
    def test_check_metrics_fail(self):
        """Test throughput assertion that fails"""
        assertion = ThroughputAssertion(15.0)
        metrics = {'requests_per_second': 10.0}
        assert assertion.check_metrics(metrics) is False
    
    def test_check_metrics_exact(self):
        """Test throughput assertion with exact match"""
        assertion = ThroughputAssertion(10.0)
        metrics = {'requests_per_second': 10.0}
        assert assertion.check_metrics(metrics) is True
    
    def test_check_metrics_missing_key(self):
        """Test throughput assertion with missing metrics key"""
        assertion = ThroughputAssertion(5.0)
        metrics = {}
        assert assertion.check_metrics(metrics) is False
    
    def test_error_message(self):
        """Test throughput assertion error message"""
        assertion = ThroughputAssertion(15.0, "Custom message")
        metrics = {'requests_per_second': 10.0}
        assert assertion.get_metrics_error_message(metrics) == "Custom message"
    
    def test_default_error_message(self):
        """Test throughput assertion default error message"""
        assertion = ThroughputAssertion(15.0)
        metrics = {'requests_per_second': 10.0}
        expected = "Throughput 10.00 RPS is below minimum 15.0 RPS"
        assert assertion.get_metrics_error_message(metrics) == expected


class TestAverageResponseTimeAssertion:
    """Tests for AverageResponseTimeAssertion"""
    
    def test_initialization(self):
        """Test AverageResponseTimeAssertion initialization"""
        assertion = AverageResponseTimeAssertion(500.0, "Test message")
        assert assertion.max_avg_ms == 500.0
        assert assertion.message == "Test message"
    
    def test_check_metrics_pass(self):
        """Test average response time assertion that passes"""
        assertion = AverageResponseTimeAssertion(500.0)
        metrics = {'avg_response_time_ms': 300.0}
        assert assertion.check_metrics(metrics) is True
    
    def test_check_metrics_fail(self):
        """Test average response time assertion that fails"""
        assertion = AverageResponseTimeAssertion(200.0)
        metrics = {'avg_response_time_ms': 300.0}
        assert assertion.check_metrics(metrics) is False
    
    def test_check_metrics_exact(self):
        """Test average response time assertion with exact match"""
        assertion = AverageResponseTimeAssertion(300.0)
        metrics = {'avg_response_time_ms': 300.0}
        assert assertion.check_metrics(metrics) is True
    
    def test_check_metrics_missing_key(self):
        """Test average response time assertion with missing metrics key"""
        assertion = AverageResponseTimeAssertion(500.0)
        metrics = {}
        assert assertion.check_metrics(metrics) is True  # Default 0.0 passes
    
    def test_error_message(self):
        """Test average response time assertion error message"""
        assertion = AverageResponseTimeAssertion(200.0, "Custom message")
        metrics = {'avg_response_time_ms': 300.0}
        assert assertion.get_metrics_error_message(metrics) == "Custom message"
    
    def test_default_error_message(self):
        """Test average response time assertion default error message"""
        assertion = AverageResponseTimeAssertion(200.0)
        metrics = {'avg_response_time_ms': 300.0}
        expected = "Average response time 300.00ms exceeds limit 200.0ms"
        assert assertion.get_metrics_error_message(metrics) == expected


class TestErrorRateAssertion:
    """Tests for ErrorRateAssertion"""
    
    def test_initialization(self):
        """Test ErrorRateAssertion initialization"""
        assertion = ErrorRateAssertion(5.0, "Test message")
        assert assertion.max_error_rate == 5.0
        assert assertion.message == "Test message"
    
    def test_check_metrics_pass(self):
        """Test error rate assertion that passes"""
        assertion = ErrorRateAssertion(10.0)
        metrics = {'total_requests': 100, 'failed_requests': 5}
        assert assertion.check_metrics(metrics) is True  # 5% < 10%
    
    def test_check_metrics_fail(self):
        """Test error rate assertion that fails"""
        assertion = ErrorRateAssertion(3.0)
        metrics = {'total_requests': 100, 'failed_requests': 5}
        assert assertion.check_metrics(metrics) is False  # 5% > 3%
    
    def test_check_metrics_exact(self):
        """Test error rate assertion with exact match"""
        assertion = ErrorRateAssertion(5.0)
        metrics = {'total_requests': 100, 'failed_requests': 5}
        assert assertion.check_metrics(metrics) is True  # 5% <= 5%
    
    def test_check_metrics_zero_requests(self):
        """Test error rate assertion with zero requests"""
        assertion = ErrorRateAssertion(5.0)
        metrics = {'total_requests': 0, 'failed_requests': 0}
        assert assertion.check_metrics(metrics) is True  # No requests = no errors
    
    def test_check_metrics_missing_keys(self):
        """Test error rate assertion with missing metrics keys"""
        assertion = ErrorRateAssertion(5.0)
        metrics = {}
        assert assertion.check_metrics(metrics) is True  # Default values
    
    def test_error_message(self):
        """Test error rate assertion error message"""
        assertion = ErrorRateAssertion(3.0, "Custom message")
        metrics = {'total_requests': 100, 'failed_requests': 5}
        assert assertion.get_metrics_error_message(metrics) == "Custom message"
    
    def test_default_error_message(self):
        """Test error rate assertion default error message"""
        assertion = ErrorRateAssertion(3.0)
        metrics = {'total_requests': 100, 'failed_requests': 5}
        expected = "Error rate 5.00% exceeds limit 3.0%"
        assert assertion.get_metrics_error_message(metrics) == expected
    
    def test_default_error_message_zero_requests(self):
        """Test error rate assertion error message with zero requests"""
        assertion = ErrorRateAssertion(3.0)
        metrics = {'total_requests': 0, 'failed_requests': 0}
        expected = "Error rate 0.00% exceeds limit 3.0%"
        assert assertion.get_metrics_error_message(metrics) == expected


class TestSuccessRateAssertion:
    """Tests for SuccessRateAssertion"""
    
    def test_initialization(self):
        """Test SuccessRateAssertion initialization"""
        assertion = SuccessRateAssertion(95.0, "Test message")
        assert assertion.min_success_rate == 95.0
        assert assertion.message == "Test message"
    
    def test_check_metrics_pass(self):
        """Test success rate assertion that passes"""
        assertion = SuccessRateAssertion(90.0)
        metrics = {'total_requests': 100, 'successful_requests': 95}
        assert assertion.check_metrics(metrics) is True  # 95% >= 90%
    
    def test_check_metrics_fail(self):
        """Test success rate assertion that fails"""
        assertion = SuccessRateAssertion(98.0)
        metrics = {'total_requests': 100, 'successful_requests': 95}
        assert assertion.check_metrics(metrics) is False  # 95% < 98%
    
    def test_check_metrics_exact(self):
        """Test success rate assertion with exact match"""
        assertion = SuccessRateAssertion(95.0)
        metrics = {'total_requests': 100, 'successful_requests': 95}
        assert assertion.check_metrics(metrics) is True  # 95% >= 95%
    
    def test_check_metrics_zero_requests(self):
        """Test success rate assertion with zero requests"""
        assertion = SuccessRateAssertion(90.0)
        metrics = {'total_requests': 0, 'successful_requests': 0}
        assert assertion.check_metrics(metrics) is True  # No requests = 100% success
    
    def test_check_metrics_missing_keys(self):
        """Test success rate assertion with missing metrics keys"""
        assertion = SuccessRateAssertion(90.0)
        metrics = {}
        assert assertion.check_metrics(metrics) is True  # Default values
    
    def test_error_message(self):
        """Test success rate assertion error message"""
        assertion = SuccessRateAssertion(98.0, "Custom message")
        metrics = {'total_requests': 100, 'successful_requests': 95}
        assert assertion.get_metrics_error_message(metrics) == "Custom message"
    
    def test_default_error_message(self):
        """Test success rate assertion default error message"""
        assertion = SuccessRateAssertion(98.0)
        metrics = {'total_requests': 100, 'successful_requests': 95}
        expected = "Success rate 95.00% is below minimum 98.0%"
        assert assertion.get_metrics_error_message(metrics) == expected
    
    def test_default_error_message_zero_requests(self):
        """Test success rate assertion error message with zero requests"""
        assertion = SuccessRateAssertion(98.0)
        metrics = {'total_requests': 0, 'successful_requests': 0}
        expected = "Success rate 100.00% is below minimum 98.0%"
        assert assertion.get_metrics_error_message(metrics) == expected


class TestMaxResponseTimeAssertion:
    """Tests for MaxResponseTimeAssertion"""
    
    def test_initialization(self):
        """Test MaxResponseTimeAssertion initialization"""
        assertion = MaxResponseTimeAssertion(1000.0, "Test message")
        assert assertion.max_time_ms == 1000.0
        assert assertion.message == "Test message"
    
    def test_check_metrics_pass(self):
        """Test max response time assertion that passes"""
        assertion = MaxResponseTimeAssertion(1000.0)
        metrics = {'max_response_time_us': 500000}  # 500ms in microseconds
        assert assertion.check_metrics(metrics) is True
    
    def test_check_metrics_fail(self):
        """Test max response time assertion that fails"""
        assertion = MaxResponseTimeAssertion(500.0)
        metrics = {'max_response_time_us': 1000000}  # 1000ms in microseconds
        assert assertion.check_metrics(metrics) is False
    
    def test_check_metrics_exact(self):
        """Test max response time assertion with exact match"""
        assertion = MaxResponseTimeAssertion(1000.0)
        metrics = {'max_response_time_us': 1000000}  # 1000ms in microseconds
        assert assertion.check_metrics(metrics) is True
    
    def test_check_metrics_missing_key(self):
        """Test max response time assertion with missing metrics key"""
        assertion = MaxResponseTimeAssertion(1000.0)
        metrics = {}
        assert assertion.check_metrics(metrics) is True  # Default 0 passes
    
    def test_error_message(self):
        """Test max response time assertion error message"""
        assertion = MaxResponseTimeAssertion(500.0, "Custom message")
        metrics = {'max_response_time_us': 1000000}
        assert assertion.get_metrics_error_message(metrics) == "Custom message"
    
    def test_default_error_message(self):
        """Test max response time assertion default error message"""
        assertion = MaxResponseTimeAssertion(500.0)
        metrics = {'max_response_time_us': 1000000}  # 1000ms
        expected = "Maximum response time 1000.00ms exceeds limit 500.0ms"
        assert assertion.get_metrics_error_message(metrics) == expected


class TestTotalRequestsAssertion:
    """Tests for TotalRequestsAssertion"""
    
    def test_initialization(self):
        """Test TotalRequestsAssertion initialization"""
        assertion = TotalRequestsAssertion(100, "Test message")
        assert assertion.min_requests == 100
        assert assertion.message == "Test message"
    
    def test_check_metrics_pass(self):
        """Test total requests assertion that passes"""
        assertion = TotalRequestsAssertion(50)
        metrics = {'total_requests': 100}
        assert assertion.check_metrics(metrics) is True
    
    def test_check_metrics_fail(self):
        """Test total requests assertion that fails"""
        assertion = TotalRequestsAssertion(150)
        metrics = {'total_requests': 100}
        assert assertion.check_metrics(metrics) is False
    
    def test_check_metrics_exact(self):
        """Test total requests assertion with exact match"""
        assertion = TotalRequestsAssertion(100)
        metrics = {'total_requests': 100}
        assert assertion.check_metrics(metrics) is True
    
    def test_check_metrics_missing_key(self):
        """Test total requests assertion with missing metrics key"""
        assertion = TotalRequestsAssertion(50)
        metrics = {}
        assert assertion.check_metrics(metrics) is False  # Default 0 fails
    
    def test_error_message(self):
        """Test total requests assertion error message"""
        assertion = TotalRequestsAssertion(150, "Custom message")
        metrics = {'total_requests': 100}
        assert assertion.get_metrics_error_message(metrics) == "Custom message"
    
    def test_default_error_message(self):
        """Test total requests assertion default error message"""
        assertion = TotalRequestsAssertion(150)
        metrics = {'total_requests': 100}
        expected = "Total requests 100 is below minimum 150"
        assert assertion.get_metrics_error_message(metrics) == expected


class TestCustomPerformanceAssertion:
    """Tests for CustomPerformanceAssertion"""
    
    def test_initialization(self):
        """Test CustomPerformanceAssertion initialization"""
        func = lambda m: True
        assertion = CustomPerformanceAssertion(func, "Test message")
        assert assertion.assertion_func == func
        assert assertion.message == "Test message"
    
    def test_check_metrics_pass(self):
        """Test custom assertion that passes"""
        func = lambda m: m.get('value', 0) > 5
        assertion = CustomPerformanceAssertion(func)
        metrics = {'value': 10}
        assert assertion.check_metrics(metrics) is True
    
    def test_check_metrics_fail(self):
        """Test custom assertion that fails"""
        func = lambda m: m.get('value', 0) > 15
        assertion = CustomPerformanceAssertion(func)
        metrics = {'value': 10}
        assert assertion.check_metrics(metrics) is False
    
    def test_check_metrics_exception(self):
        """Test custom assertion that raises exception"""
        def failing_func(metrics):
            raise ValueError("Test error")
        
        assertion = CustomPerformanceAssertion(failing_func)
        metrics = {}
        assert assertion.check_metrics(metrics) is False
    
    def test_error_message(self):
        """Test custom assertion error message"""
        func = lambda m: False
        assertion = CustomPerformanceAssertion(func, "Custom message")
        assert assertion.get_metrics_error_message({}) == "Custom message"
    
    def test_default_error_message(self):
        """Test custom assertion default error message"""
        func = lambda m: False
        assertion = CustomPerformanceAssertion(func)
        assert assertion.get_metrics_error_message({}) == "Custom performance assertion failed"


class TestPerformanceAssertionGroup:
    """Tests for PerformanceAssertionGroup"""
    
    def test_initialization_and(self):
        """Test PerformanceAssertionGroup initialization with AND logic"""
        group = PerformanceAssertionGroup("AND")
        assert group.logic == "AND"
        assert group.assertions == []
        assert group.failed_assertions == []
    
    def test_initialization_or(self):
        """Test PerformanceAssertionGroup initialization with OR logic"""
        group = PerformanceAssertionGroup("OR")
        assert group.logic == "OR"
    
    def test_initialization_default(self):
        """Test PerformanceAssertionGroup default initialization"""
        group = PerformanceAssertionGroup()
        assert group.logic == "AND"
    
    def test_initialization_case_insensitive(self):
        """Test PerformanceAssertionGroup with lowercase logic"""
        group = PerformanceAssertionGroup("and")
        assert group.logic == "AND"
    
    def test_add_assertion(self):
        """Test adding assertions to group"""
        group = PerformanceAssertionGroup()
        assertion = ThroughputAssertion(10.0)
        result = group.add(assertion)
        
        assert len(group.assertions) == 1
        assert group.assertions[0] == assertion
        assert result == group  # Should return self for chaining
    
    def test_add_multiple_assertions(self):
        """Test adding multiple assertions to group"""
        group = PerformanceAssertionGroup()
        assertion1 = ThroughputAssertion(10.0)
        assertion2 = ErrorRateAssertion(5.0)
        
        group.add(assertion1).add(assertion2)
        
        assert len(group.assertions) == 2
        assert group.assertions[0] == assertion1
        assert group.assertions[1] == assertion2
    
    def test_check_all_metrics_and_all_pass(self):
        """Test AND group where all assertions pass"""
        group = PerformanceAssertionGroup("AND")
        group.add(ThroughputAssertion(5.0))
        group.add(ErrorRateAssertion(10.0))
        
        metrics = {'requests_per_second': 10.0, 'total_requests': 100, 'failed_requests': 2}
        result = group.check_all_metrics(metrics)
        
        assert result is True
        assert len(group.failed_assertions) == 0
    
    def test_check_all_metrics_and_one_fails(self):
        """Test AND group where one assertion fails"""
        group = PerformanceAssertionGroup("AND")
        group.add(ThroughputAssertion(15.0))  # This will fail
        group.add(ErrorRateAssertion(10.0))   # This will pass
        
        metrics = {'requests_per_second': 10.0, 'total_requests': 100, 'failed_requests': 2}
        result = group.check_all_metrics(metrics)
        
        assert result is False
        assert len(group.failed_assertions) == 1
        assert isinstance(group.failed_assertions[0][0], ThroughputAssertion)
    
    def test_check_all_metrics_and_all_fail(self):
        """Test AND group where all assertions fail"""
        group = PerformanceAssertionGroup("AND")
        group.add(ThroughputAssertion(15.0))  # This will fail
        group.add(ErrorRateAssertion(1.0))    # This will fail (2% > 1%)
        
        metrics = {'requests_per_second': 10.0, 'total_requests': 100, 'failed_requests': 2}
        result = group.check_all_metrics(metrics)
        
        assert result is False
        assert len(group.failed_assertions) == 2
    
    def test_check_all_metrics_or_all_pass(self):
        """Test OR group where all assertions pass"""
        group = PerformanceAssertionGroup("OR")
        group.add(ThroughputAssertion(5.0))   # This will pass
        group.add(ErrorRateAssertion(10.0))   # This will pass
        
        metrics = {'requests_per_second': 10.0, 'total_requests': 100, 'failed_requests': 2}
        result = group.check_all_metrics(metrics)
        
        assert result is True
        assert len(group.failed_assertions) == 0
    
    def test_check_all_metrics_or_one_passes(self):
        """Test OR group where one assertion passes"""
        group = PerformanceAssertionGroup("OR")
        group.add(ThroughputAssertion(15.0))  # This will fail
        group.add(ErrorRateAssertion(10.0))   # This will pass
        
        metrics = {'requests_per_second': 10.0, 'total_requests': 100, 'failed_requests': 2}
        result = group.check_all_metrics(metrics)
        
        assert result is True
        assert len(group.failed_assertions) == 1  # Still tracks failures
    
    def test_check_all_metrics_or_all_fail(self):
        """Test OR group where all assertions fail"""
        group = PerformanceAssertionGroup("OR")
        group.add(ThroughputAssertion(15.0))  # This will fail
        group.add(ErrorRateAssertion(1.0))    # This will fail
        
        metrics = {'requests_per_second': 10.0, 'total_requests': 100, 'failed_requests': 2}
        result = group.check_all_metrics(metrics)
        
        assert result is False
        assert len(group.failed_assertions) == 2
    
    def test_invalid_logic(self):
        """Test invalid logic operator"""
        group = PerformanceAssertionGroup("INVALID")
        group.add(ThroughputAssertion(10.0))
        
        metrics = {'requests_per_second': 15.0}
        
        with pytest.raises(ValueError, match="Unknown logic operator: INVALID"):
            group.check_all_metrics(metrics)
    
    def test_get_failure_report_no_failures(self):
        """Test failure report with no failures"""
        group = PerformanceAssertionGroup()
        assert group.get_failure_report() == ""
    
    def test_get_failure_report_with_failures(self):
        """Test failure report with failures"""
        group = PerformanceAssertionGroup("AND")
        group.add(ThroughputAssertion(15.0, "High throughput"))
        group.add(ErrorRateAssertion(1.0, "Low error rate"))
        
        metrics = {'requests_per_second': 10.0, 'total_requests': 100, 'failed_requests': 2}
        group.check_all_metrics(metrics)
        
        report = group.get_failure_report()
        assert "Performance assertion group (AND) failed:" in report
        assert "1. High throughput" in report
        assert "2. Low error rate" in report
    
    def test_reset_failed_assertions(self):
        """Test that failed assertions are reset on new check"""
        group = PerformanceAssertionGroup("AND")
        group.add(ThroughputAssertion(15.0))
        
        # First check - should fail
        metrics_fail = {'requests_per_second': 10.0}
        group.check_all_metrics(metrics_fail)
        assert len(group.failed_assertions) == 1
        
        # Second check - should pass and reset failures
        metrics_pass = {'requests_per_second': 20.0}
        group.check_all_metrics(metrics_pass)
        assert len(group.failed_assertions) == 0


class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    def test_throughput_at_least(self):
        """Test throughput_at_least convenience function"""
        assertion = throughput_at_least(10.0, "Test message")
        assert isinstance(assertion, ThroughputAssertion)
        assert assertion.min_rps == 10.0
        assert assertion.message == "Test message"
    
    def test_avg_response_time_under(self):
        """Test avg_response_time_under convenience function"""
        assertion = avg_response_time_under(500.0, "Test message")
        assert isinstance(assertion, AverageResponseTimeAssertion)
        assert assertion.max_avg_ms == 500.0
        assert assertion.message == "Test message"
    
    def test_error_rate_below(self):
        """Test error_rate_below convenience function"""
        assertion = error_rate_below(5.0, "Test message")
        assert isinstance(assertion, ErrorRateAssertion)
        assert assertion.max_error_rate == 5.0
        assert assertion.message == "Test message"
    
    def test_success_rate_at_least(self):
        """Test success_rate_at_least convenience function"""
        assertion = success_rate_at_least(95.0, "Test message")
        assert isinstance(assertion, SuccessRateAssertion)
        assert assertion.min_success_rate == 95.0
        assert assertion.message == "Test message"
    
    def test_max_response_time_under(self):
        """Test max_response_time_under convenience function"""
        assertion = max_response_time_under(1000.0, "Test message")
        assert isinstance(assertion, MaxResponseTimeAssertion)
        assert assertion.max_time_ms == 1000.0
        assert assertion.message == "Test message"
    
    def test_total_requests_at_least(self):
        """Test total_requests_at_least convenience function"""
        assertion = total_requests_at_least(100, "Test message")
        assert isinstance(assertion, TotalRequestsAssertion)
        assert assertion.min_requests == 100
        assert assertion.message == "Test message"
    
    def test_custom_performance_assertion(self):
        """Test custom_performance_assertion convenience function"""
        func = lambda m: True
        assertion = custom_performance_assertion(func, "Test message")
        assert isinstance(assertion, CustomPerformanceAssertion)
        assert assertion.assertion_func == func
        assert assertion.message == "Test message"


class TestRunPerformanceAssertions:
    """Tests for run_performance_assertions function"""
    
    def test_all_pass(self):
        """Test run_performance_assertions where all assertions pass"""
        metrics = {'requests_per_second': 15.0, 'total_requests': 100, 'failed_requests': 2}
        assertions = [
            ThroughputAssertion(10.0),
            ErrorRateAssertion(5.0)
        ]
        
        success, failures = run_performance_assertions(metrics, assertions)
        
        assert success is True
        assert len(failures) == 0
    
    def test_some_fail(self):
        """Test run_performance_assertions where some assertions fail"""
        metrics = {'requests_per_second': 5.0, 'total_requests': 100, 'failed_requests': 10}
        assertions = [
            ThroughputAssertion(10.0, "High throughput needed"),
            ErrorRateAssertion(5.0, "Low error rate needed")
        ]
        
        success, failures = run_performance_assertions(metrics, assertions, fail_fast=False)
        
        assert success is False
        assert len(failures) == 2
        assert "High throughput needed" in failures[0]
        assert "Low error rate needed" in failures[1]
    
    def test_fail_fast_true(self):
        """Test run_performance_assertions with fail_fast=True"""
        metrics = {'requests_per_second': 5.0, 'total_requests': 100, 'failed_requests': 10}
        assertions = [
            ThroughputAssertion(10.0, "First failure"),
            ErrorRateAssertion(5.0, "Second failure")
        ]
        
        success, failures = run_performance_assertions(metrics, assertions, fail_fast=True)
        
        assert success is False
        assert len(failures) == 1  # Should stop at first failure
        assert "First failure" in failures[0]
    
    def test_fail_fast_false(self):
        """Test run_performance_assertions with fail_fast=False"""
        metrics = {'requests_per_second': 5.0, 'total_requests': 100, 'failed_requests': 10}
        assertions = [
            ThroughputAssertion(10.0, "First failure"),
            ErrorRateAssertion(5.0, "Second failure")
        ]
        
        success, failures = run_performance_assertions(metrics, assertions, fail_fast=False)
        
        assert success is False
        assert len(failures) == 2  # Should collect all failures
        assert "First failure" in failures[0]
        assert "Second failure" in failures[1]
    
    def test_empty_assertions(self):
        """Test run_performance_assertions with empty assertions list"""
        metrics = {'requests_per_second': 10.0}
        assertions = []
        
        success, failures = run_performance_assertions(metrics, assertions)
        
        assert success is True
        assert len(failures) == 0
    
    def test_empty_metrics(self):
        """Test run_performance_assertions with empty metrics"""
        metrics = {}
        assertions = [ThroughputAssertion(10.0)]
        
        success, failures = run_performance_assertions(metrics, assertions)
        
        assert success is False
        assert len(failures) == 1


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""
    
    def test_very_large_numbers(self):
        """Test with very large numbers"""
        assertion = ThroughputAssertion(1000000.0)
        metrics = {'requests_per_second': 2000000.0}
        assert assertion.check_metrics(metrics) is True
    
    def test_very_small_numbers(self):
        """Test with very small numbers"""
        assertion = ThroughputAssertion(0.001)
        metrics = {'requests_per_second': 0.002}
        assert assertion.check_metrics(metrics) is True
    
    def test_zero_values(self):
        """Test with zero values"""
        assertion = ThroughputAssertion(0.0)
        metrics = {'requests_per_second': 0.0}
        assert assertion.check_metrics(metrics) is True
    
    def test_negative_values(self):
        """Test with negative values (should handle gracefully)"""
        assertion = ThroughputAssertion(10.0)
        metrics = {'requests_per_second': -5.0}
        assert assertion.check_metrics(metrics) is False
    
    def test_float_precision(self):
        """Test float precision edge cases"""
        assertion = ThroughputAssertion(10.0)
        metrics = {'requests_per_second': 10.000000001}
        assert assertion.check_metrics(metrics) is True
    
    def test_none_values(self):
        """Test handling of None values in metrics"""
        assertion = ErrorRateAssertion(5.0)
        metrics = {'total_requests': None, 'failed_requests': None}
        # Should handle None gracefully (get() returns None, treated as 0)
        result = assertion.check_metrics(metrics)
        assert result is True  # 0 total requests = no errors


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios"""
    
    @pytest.fixture
    def sample_metrics_good(self):
        """Sample metrics representing good performance"""
        return {
            'requests_per_second': 50.0,
            'avg_response_time_ms': 200.0,
            'max_response_time_us': 1000000,  # 1000ms
            'total_requests': 1000,
            'successful_requests': 980,
            'failed_requests': 20
        }
    
    @pytest.fixture
    def sample_metrics_poor(self):
        """Sample metrics representing poor performance"""
        return {
            'requests_per_second': 5.0,
            'avg_response_time_ms': 2000.0,
            'max_response_time_us': 10000000,  # 10000ms
            'total_requests': 100,
            'successful_requests': 70,
            'failed_requests': 30
        }
    
    def test_high_performance_api_requirements(self, sample_metrics_good):
        """Test high-performance API requirements"""
        api_requirements = [
            throughput_at_least(30.0, "API should handle 30+ RPS"),
            avg_response_time_under(500.0, "API response time under 500ms"),
            error_rate_below(5.0, "API error rate below 5%"),
            success_rate_at_least(95.0, "API success rate at least 95%"),
            max_response_time_under(2000.0, "API max response time under 2s")
        ]
        
        success, failures = run_performance_assertions(sample_metrics_good, api_requirements)
        
        assert success is True
        assert len(failures) == 0
    
    def test_basic_web_application_requirements(self, sample_metrics_good):
        """Test basic web application requirements"""
        web_requirements = [
            throughput_at_least(10.0, "Web app should handle 10+ RPS"),
            avg_response_time_under(3000.0, "Web app response time under 3s"),
            error_rate_below(10.0, "Web app error rate below 10%"),
            success_rate_at_least(90.0, "Web app success rate at least 90%")
        ]
        
        success, failures = run_performance_assertions(sample_metrics_good, web_requirements)
        
        assert success is True
        assert len(failures) == 0
    
    def test_failing_performance_scenario(self, sample_metrics_poor):
        """Test scenario where performance requirements are not met"""
        strict_requirements = [
            throughput_at_least(20.0, "Need 20+ RPS"),
            avg_response_time_under(500.0, "Need response time under 500ms"),
            error_rate_below(10.0, "Need error rate below 10%"),
            success_rate_at_least(95.0, "Need success rate at least 95%")
        ]
        
        success, failures = run_performance_assertions(sample_metrics_poor, strict_requirements, fail_fast=False)
        
        assert success is False
        assert len(failures) == 4  # All should fail
    
    def test_production_readiness_gate(self, sample_metrics_good):
        """Test production readiness gate using assertion groups"""
        # All must pass for production
        production_gate = PerformanceAssertionGroup("AND")
        production_gate.add(throughput_at_least(25.0, "Production needs 25+ RPS"))
        production_gate.add(avg_response_time_under(1000.0, "Production needs <1s avg"))
        production_gate.add(error_rate_below(2.0, "Production needs <2% errors"))
        production_gate.add(success_rate_at_least(98.0, "Production needs 98%+ success"))
        
        result = production_gate.check_all_metrics(sample_metrics_good)
        
        assert result is True
    
    def test_flexible_acceptance_criteria(self, sample_metrics_poor):
        """Test flexible acceptance criteria using OR logic"""
        # At least one must pass for basic acceptance
        flexible_gate = PerformanceAssertionGroup("OR")
        flexible_gate.add(throughput_at_least(10.0, "Basic throughput"))
        flexible_gate.add(success_rate_at_least(70.0, "Basic success rate"))
        flexible_gate.add(error_rate_below(50.0, "Basic error rate"))
        
        result = flexible_gate.check_all_metrics(sample_metrics_poor)
        
        assert result is True  # Should pass because success rate is 70%
    
    def test_stress_test_validation(self, sample_metrics_poor):
        """Test validation for stress testing scenarios"""
        # During stress testing, we accept degraded performance
        stress_requirements = [
            error_rate_below(40.0, "Stress test: error rate below 40%"),
            total_requests_at_least(50, "Stress test: at least 50 requests processed"),
            # Custom assertion for graceful degradation
            custom_performance_assertion(
                lambda m: m.get('successful_requests', 0) > 0,
                "Stress test: some requests should succeed"
            )
        ]
        
        success, failures = run_performance_assertions(sample_metrics_poor, stress_requirements)
        
        assert success is True  # Should pass with relaxed criteria
        assert len(failures) == 0


if __name__ == "__main__":
    # Allow running tests directly
    pytest.main([__file__, "-v"])
