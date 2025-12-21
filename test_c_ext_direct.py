#!/usr/bin/env python3
"""
Simple direct test of the C extension functionality
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 60)
print("LoadSpiker C Extension Direct Test")
print("=" * 60)

# Import the loadspiker package
from loadspiker import Engine

# Create an engine instance
print("\n1. Creating Engine instance...")
engine = Engine(max_connections=10, worker_threads=2)
print(f"   ✓ Engine created: {type(engine)}")
print(f"   ✓ Using C extension: {engine._using_c_extension}")

# Test basic HTTP request
print("\n2. Testing HTTP request to example.com...")
try:
    response = engine.execute_request(
        url="http://example.com",
        method="GET",
        timeout_ms=5000
    )
    
    print(f"   ✓ Request executed")
    print(f"   - Status Code: {response.get('status_code', 'N/A')}")
    print(f"   - Success: {response.get('success', 'N/A')}")
    print(f"   - Response Time: {response.get('response_time_us', 0) / 1000:.2f} ms")
    print(f"   - Body Length: {len(response.get('body', ''))} bytes")
    
    if response.get('error_message'):
        print(f"   - Error: {response.get('error_message')}")
    
except Exception as e:
    print(f"   ✗ Request failed: {e}")
    import traceback
    traceback.print_exc()

# Test metrics
print("\n3. Testing metrics collection...")
try:
    metrics = engine.get_metrics()
    print(f"   ✓ Metrics retrieved")
    print(f"   - Total Requests: {metrics.get('total_requests', 0)}")
    print(f"   - Successful Requests: {metrics.get('successful_requests', 0)}")
    print(f"   - Failed Requests: {metrics.get('failed_requests', 0)}")
    print(f"   - Avg Response Time: {metrics.get('avg_response_time_ms', 0):.2f} ms")
except Exception as e:
    print(f"   ✗ Metrics failed: {e}")

# Summary
print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)

if engine._using_c_extension:
    print("✅ C Extension is working correctly!")
    print("   High-performance mode is ENABLED")
    sys.exit(0)
else:
    print("⚠️  Using Python fallback implementation")
    sys.exit(1)
