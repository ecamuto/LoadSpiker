#!/usr/bin/env python3
"""
Simple test to verify basic functionality
"""
import sys
import os
sys.path.insert(0, '.')

from loadspiker import Engine

def main():
    print("🧪 Testing LoadSpiker basic functionality...")
    
    # Create engine
    engine = Engine(max_connections=10, worker_threads=2)
    print("✅ Engine created")
    
    # Test single request
    try:
        print("   Making request to https://www.google.com...")
        response = engine.execute_request("https://www.google.com")
        print(f"✅ Single request: Status {response['status_code']}")
        print(f"   Response time: {response['response_time_us']/1000:.1f}ms")
        print(f"   Success: {response['success']}")
        if not response['success']:
            print(f"   Error: {response['error_message']}")
        print(f"   Body length: {len(response.get('body', ''))}")
    except Exception as e:
        print(f"❌ Single request failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test metrics
    try:
        metrics = engine.get_metrics()
        print(f"✅ Metrics: {metrics['total_requests']} total requests")
    except Exception as e:
        print(f"❌ Metrics failed: {e}")
        return False
    
    print("\n🎉 Basic functionality test passed!")
    return True

if __name__ == '__main__':
    if not main():
        sys.exit(1)
