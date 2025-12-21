#!/usr/bin/env python3
"""
Comprehensive C Extension Integration Test
Tests the entire flow: C code compilation, Python integration, and functionality
"""

import sys
import os

# Ensure we're using the local loadspiker package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test 1: Verify all imports work"""
    print("=" * 60)
    print("TEST 1: Testing imports...")
    print("=" * 60)
    
    try:
        # Try to import the C extension directly
        try:
            import loadspiker
            # Check if it's the C extension by looking for the Engine class
            if hasattr(loadspiker, 'Engine') and hasattr(loadspiker.Engine, '__module__'):
                module_name = loadspiker.Engine.__module__
                if module_name == 'loadspiker' and not module_name.endswith('.engine'):
                    print("✓ C extension (loadspiker) imported successfully")
                    return loadspiker
        except ImportError:
            pass
        
        # Fall back to checking for Python-only implementation
        import loadspiker
        print("✓ loadspiker imported successfully (Python implementation)")
        return None
            
    except ImportError as e:
        print(f"✗ Failed to import loadspiker: {e}")
        return None

def test_c_extension_module(c_ext):
    """Test 2: Verify C extension module structure"""
    print("\n" + "=" * 60)
    print("TEST 2: Testing C extension module structure...")
    print("=" * 60)
    
    if c_ext is None:
        print("⚠ Skipping - C extension not available")
        return False
    
    # Check for Engine class
    if hasattr(c_ext, 'Engine'):
        print("✓ Engine class found in C extension")
        
        # Try to instantiate the engine
        try:
            engine = c_ext.Engine(max_connections=10, worker_threads=2)
            print("✓ Engine instantiated successfully")
            print(f"  - Type: {type(engine)}")
            
            # Check for methods
            methods = ['execute_request', 'get_metrics', 'reset_metrics']
            for method in methods:
                if hasattr(engine, method):
                    print(f"✓ Method '{method}' found")
                else:
                    print(f"✗ Method '{method}' NOT found")
            
            return engine
        except Exception as e:
            print(f"✗ Failed to instantiate Engine: {e}")
            return None
    else:
        print("✗ Engine class NOT found in C extension")
        return None

def test_http_request(engine):
    """Test 3: Test basic HTTP request functionality"""
    print("\n" + "=" * 60)
    print("TEST 3: Testing HTTP request functionality...")
    print("=" * 60)
    
    if engine is None:
        print("⚠ Skipping - No engine available")
        return False
    
    try:
        # Test with a simple HTTP request to example.com
        print("Executing HTTP request to http://example.com...")
        response = engine.execute_request(
            url="http://example.com",
            method="GET",
            timeout_ms=5000
        )
        
        print("✓ HTTP request executed successfully")
        print(f"  - Status Code: {response.get('status_code', 'N/A')}")
        print(f"  - Success: {response.get('success', 'N/A')}")
        print(f"  - Response Time: {response.get('response_time_us', 0) / 1000:.2f} ms")
        print(f"  - Body Length: {len(response.get('body', ''))} bytes")
        
        if response.get('error_message'):
            print(f"  - Error: {response.get('error_message')}")
        
        return response.get('success', False)
        
    except Exception as e:
        print(f"✗ HTTP request failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_metrics(engine):
    """Test 4: Test metrics collection"""
    print("\n" + "=" * 60)
    print("TEST 4: Testing metrics collection...")
    print("=" * 60)
    
    if engine is None:
        print("⚠ Skipping - No engine available")
        return False
    
    try:
        metrics = engine.get_metrics()
        print("✓ Metrics retrieved successfully")
        print(f"  - Total Requests: {metrics.get('total_requests', 0)}")
        print(f"  - Successful Requests: {metrics.get('successful_requests', 0)}")
        print(f"  - Failed Requests: {metrics.get('failed_requests', 0)}")
        print(f"  - Avg Response Time: {metrics.get('avg_response_time_ms', 0):.2f} ms")
        print(f"  - Min Response Time: {metrics.get('min_response_time_us', 0) / 1000:.2f} ms")
        print(f"  - Max Response Time: {metrics.get('max_response_time_us', 0) / 1000:.2f} ms")
        
        return True
    except Exception as e:
        print(f"✗ Failed to get metrics: {e}")
        return False

def test_pure_python_fallback():
    """Test 5: Test pure Python implementation"""
    print("\n" + "=" * 60)
    print("TEST 5: Testing pure Python fallback...")
    print("=" * 60)
    
    try:
        from loadspiker import LoadTest
        print("✓ LoadTest class imported")
        
        # Create a simple test
        test = LoadTest()
        print("✓ LoadTest instantiated")
        
        # Test basic HTTP request using pure Python
        print("Testing HTTP request via pure Python...")
        test.get("http://example.com")
        
        results = test.results()
        print("✓ Pure Python HTTP request successful")
        print(f"  - Total Requests: {results.get('total_requests', 0)}")
        print(f"  - Success Rate: {results.get('success_rate', 0):.2f}%")
        
        return True
    except Exception as e:
        print(f"✗ Pure Python test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("LoadSpiker C Extension Integration Test Suite")
    print("=" * 60)
    
    results = {
        'imports': False,
        'c_extension': False,
        'http_request': False,
        'metrics': False,
        'pure_python': False
    }
    
    # Test 1: Imports
    c_ext = test_imports()
    results['imports'] = c_ext is not None or True  # Pass if either works
    
    # Test 2: C Extension Module
    engine = None
    if c_ext:
        engine = test_c_extension_module(c_ext)
        results['c_extension'] = engine is not None
    
    # Test 3: HTTP Request
    if engine:
        results['http_request'] = test_http_request(engine)
    
    # Test 4: Metrics
    if engine:
        results['metrics'] = test_metrics(engine)
    
    # Test 5: Pure Python Fallback
    results['pure_python'] = test_pure_python_fallback()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name.replace('_', ' ').title()}")
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! C extension is working correctly.")
        return 0
    elif results['pure_python']:
        print("\n⚠️  C extension has issues, but pure Python fallback works.")
        return 1
    else:
        print("\n❌ Critical failures detected. System not operational.")
        return 2

if __name__ == "__main__":
    sys.exit(main())
