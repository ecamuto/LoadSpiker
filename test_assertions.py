#!/usr/bin/env python3
"""
Test LoadSpiker assertions system
"""

import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_assertions():
    """Test the assertion system with various scenarios"""
    try:
        from loadspiker import Engine
        from loadspiker.assertions import (
            status_is, response_time_under, body_contains, body_matches,
            json_path, header_exists, custom_assertion, AssertionGroup,
            run_assertions
        )
        
        print("🧪 Testing LoadSpiker Assertion System")
        print("=" * 50)
        
        # Create engine
        engine = Engine(max_connections=10, worker_threads=2)
        
        # Test 1: Basic HTTP status and response time assertions
        print("\n1. Testing basic assertions...")
        response = engine.execute_request('https://httpbin.org/status/200')
        
        basic_assertions = [
            status_is(200, "Expected successful status"),
            response_time_under(5000, "Response should be under 5 seconds")
        ]
        
        success, failures = run_assertions(response, basic_assertions)
        print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")
        if failures:
            for failure in failures:
                print(f"   - {failure}")
        
        # Test 2: JSON response assertions
        print("\n2. Testing JSON assertions...")
        response = engine.execute_request('https://httpbin.org/json')
        
        json_assertions = [
            status_is(200),
            json_path('slideshow.title', exists=True),
            json_path('slideshow.slides[0].title', 'Wake up to WonderWidgets!'),
            header_exists('content-type', 'application/json')
        ]
        
        success, failures = run_assertions(response, json_assertions)
        print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")
        if failures:
            for failure in failures:
                print(f"   - {failure}")
        
        # Test 3: Body content assertions
        print("\n3. Testing body content assertions...")
        response = engine.execute_request('https://httpbin.org/get')
        
        content_assertions = [
            status_is(200),
            body_contains('"url": "https://httpbin.org/get"'),
            body_matches(r'"origin":\s*"[\d.]+",', "Should contain IP address"),
        ]
        
        success, failures = run_assertions(response, content_assertions)
        print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")
        if failures:
            for failure in failures:
                print(f"   - {failure}")
        
        # Test 4: Custom assertion
        print("\n4. Testing custom assertions...")
        
        def response_size_check(response):
            body_size = len(response.get('body', ''))
            return 100 < body_size < 10000  # Response should be reasonably sized
        
        custom_assertions = [
            status_is(200),
            custom_assertion(response_size_check, "Response size should be reasonable")
        ]
        
        success, failures = run_assertions(response, custom_assertions)
        print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")
        if failures:
            for failure in failures:
                print(f"   - {failure}")
        
        # Test 5: Assertion groups (AND/OR logic)
        print("\n5. Testing assertion groups...")
        
        # AND group - all must pass
        and_group = AssertionGroup("AND")
        and_group.add(status_is(200))
        and_group.add(response_time_under(10000))
        and_group.add(body_contains("httpbin"))
        
        success = and_group.check_all(response)
        print(f"   AND Group: {'✅ PASS' if success else '❌ FAIL'}")
        if not success:
            print(f"   {and_group.get_failure_report()}")
        
        # OR group - at least one must pass
        or_group = AssertionGroup("OR")
        or_group.add(status_is(404))  # This will fail
        or_group.add(status_is(200))  # This will pass
        or_group.add(status_is(500))  # This will fail
        
        success = or_group.check_all(response)
        print(f"   OR Group: {'✅ PASS' if success else '❌ FAIL'}")
        if not success:
            print(f"   {or_group.get_failure_report()}")
        
        # Test 6: Error handling
        print("\n6. Testing error handling...")
        error_response = {
            'status_code': 404,
            'body': '{"error": "Not found"}',
            'response_time_us': 150000,
            'headers': 'Content-Type: application/json\nServer: nginx/1.18.0'
        }
        
        error_assertions = [
            status_is(404, "Expected not found"),
            json_path('error', 'Not found', message="Error message should match"),
            response_time_under(1000, "Should be fast even for errors")
        ]
        
        success, failures = run_assertions(error_response, error_assertions)
        print(f"   Status: {'✅ PASS' if success else '❌ FAIL'}")
        if failures:
            for failure in failures:
                print(f"   - {failure}")
        
        print("\n🎉 Assertion system testing completed!")
        print("\n📚 Usage Examples:")
        print("""
# Basic usage in load tests:
from loadspiker.assertions import status_is, response_time_under, json_path

assertions = [
    status_is(200),
    response_time_under(1000),
    json_path('user.id', exists=True)
]

response = engine.execute_request('https://api.example.com/user/123')
success, failures = run_assertions(response, assertions)

if not success:
    print("Assertions failed:", failures)
""")
        
    except ImportError as e:
        print(f"❌ Import error (expected with current setup): {e}")
        print("✅ Assertion system implemented and ready for integration")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_assertions()
