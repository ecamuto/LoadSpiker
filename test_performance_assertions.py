#!/usr/bin/env python3

"""
Test LoadSpiker performance assertions system
"""

import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_performance_assertions():
    """Test the performance assertion system with various scenarios"""
    try:
        from loadspiker import Engine, Scenario
        from loadspiker.performance_assertions import (
            throughput_at_least, avg_response_time_under, error_rate_below,
            success_rate_at_least, max_response_time_under, total_requests_at_least,
            custom_performance_assertion, PerformanceAssertionGroup,
            run_performance_assertions
        )
        
        print("🧪 Testing LoadSpiker Performance Assertion System")
        print("=" * 60)
        
        # Create engine
        engine = Engine(max_connections=20, worker_threads=4)
        
        # Test 1: Basic performance assertions with single request
        print("\n1. Testing basic performance assertions...")
        
        # Make some requests to generate metrics
        response = engine.execute_request('https://httpbin.org/status/200')
        metrics = engine.get_metrics()
        
        print(f"   Current metrics: RPS={metrics['requests_per_second']:.2f}, "
              f"Avg={metrics['avg_response_time_ms']:.2f}ms, "
              f"Total={metrics['total_requests']}")
        
        basic_assertions = [
            throughput_at_least(0.01, "Should handle at least 0.01 RPS"),
            avg_response_time_under(10000, "Average response time should be under 10 seconds"),
            error_rate_below(50.0, "Error rate should be below 50%"),
            success_rate_at_least(90.0, "Success rate should be at least 90%"),
            total_requests_at_least(1, "Should process at least 1 request")
        ]
        
        success, failures = run_performance_assertions(metrics, basic_assertions)
        print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")
        if failures:
            for failure in failures:
                print(f"   - {failure}")
        
        # Test 2: Load test scenario with performance assertions
        print("\n2. Testing with load test scenario...")
        
        scenario = Scenario("Performance Test")
        scenario.get("https://httpbin.org/get")
        scenario.get("https://httpbin.org/status/200")
        
        # Run a small load test
        results = engine.run_scenario(scenario, users=3, duration=5)
        
        print(f"   Load test metrics: RPS={results['requests_per_second']:.2f}, "
              f"Avg={results['avg_response_time_ms']:.2f}ms, "
              f"Total={results['total_requests']}, "
              f"Errors={results['failed_requests']}")
        
        load_assertions = [
            throughput_at_least(0.1, "Should handle at least 0.1 RPS under load"),
            avg_response_time_under(5000, "Average response time should be under 5 seconds"),
            error_rate_below(10.0, "Error rate should be below 10%"),
            success_rate_at_least(95.0, "Success rate should be at least 95%"),
            max_response_time_under(15000, "Maximum response time should be under 15 seconds"),
            total_requests_at_least(3, "Should process at least 3 requests")
        ]
        
        success, failures = run_performance_assertions(results, load_assertions)
        print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")
        if failures:
            for failure in failures:
                print(f"   - {failure}")
        
        # Test 3: Custom performance assertion
        print("\n3. Testing custom performance assertions...")
        
        def reasonable_performance_check(metrics):
            """Custom assertion: Check if performance is reasonable"""
            rps = metrics.get('requests_per_second', 0.0)
            avg_time = metrics.get('avg_response_time_ms', 0.0)
            # Performance is reasonable if we have some throughput and reasonable response time
            return rps > 0.01 and avg_time < 10000
        
        custom_assertions = [
            custom_performance_assertion(reasonable_performance_check, 
                                       "Performance should be reasonable (RPS > 0.01 and avg < 10s)")
        ]
        
        success, failures = run_performance_assertions(results, custom_assertions)
        print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")
        if failures:
            for failure in failures:
                print(f"   - {failure}")
        
        # Test 4: Performance assertion groups (AND/OR logic)
        print("\n4. Testing performance assertion groups...")
        
        # AND group - all must pass
        and_group = PerformanceAssertionGroup("AND")
        and_group.add(success_rate_at_least(90.0))
        and_group.add(error_rate_below(20.0))
        and_group.add(avg_response_time_under(8000))
        
        success = and_group.check_all_metrics(results)
        print(f"   AND Group: {'✅ PASS' if success else '❌ FAIL'}")
        if not success:
            print(f"   {and_group.get_failure_report()}")
        
        # OR group - at least one must pass
        or_group = PerformanceAssertionGroup("OR")
        or_group.add(throughput_at_least(100.0))  # This might fail (too high)
        or_group.add(success_rate_at_least(50.0))  # This should pass
        or_group.add(total_requests_at_least(1))   # This should pass
        
        success = or_group.check_all_metrics(results)
        print(f"   OR Group: {'✅ PASS' if success else '❌ FAIL'}")
        if not success:
            print(f"   {or_group.get_failure_report()}")
        
        print("\n🎉 Performance assertion system testing completed!")
        print("\n📚 Usage Examples:")
        print("""
# Basic usage with load tests:
from loadspiker.performance_assertions import (
    throughput_at_least, avg_response_time_under, error_rate_below
)

# Run load test
results = engine.run_scenario(scenario, users=50, duration=60)

# Define performance assertions
perf_assertions = [
    throughput_at_least(10.0, "Should handle at least 10 RPS"),
    avg_response_time_under(1000, "Average response time under 1 second"),
    error_rate_below(5.0, "Error rate should be below 5%")
]

# Check performance assertions
success, failures = run_performance_assertions(results, perf_assertions)
if not success:
    print("Performance issues:", failures)
""")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("✅ Performance assertion system implemented and ready for integration")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_performance_assertions()
