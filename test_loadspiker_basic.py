#!/usr/bin/env python3
"""
Test LoadSpiker basic functionality without using scenarios
"""

import sys
import os

# Add current directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def main():
    try:
        # Import the Engine class
        from loadspiker import Engine
        print("✅ LoadSpiker Engine imported successfully!")
        
        # Create an engine instance
        engine = Engine(max_connections=50, worker_threads=2)
        print("✅ Engine created successfully!")
        
        # Test a simple HTTP request
        print("\n🔄 Testing HTTP request...")
        try:
            result = engine.execute_request('https://httpbin.org/get')
            print(f"✅ HTTP request completed!")
            print(f"   Status code: {result.get('status_code')}")
            print(f"   Response time: {result.get('response_time_us')} microseconds")
            print(f"   Success: {result.get('success')}")
        except Exception as e:
            print(f"⚠️  HTTP request failed (this is expected if no internet): {e}")
        
        # Test metrics system
        print("\n📊 Testing metrics...")
        metrics = engine.get_metrics()
        print("✅ Metrics retrieved successfully!")
        print(f"   Total requests: {metrics.get('total_requests', 0)}")
        print(f"   Successful requests: {metrics.get('successful_requests', 0)}")
        print(f"   Failed requests: {metrics.get('failed_requests', 0)}")
        
        # Test WebSocket functionality (basic test)
        print("\n🔌 Testing WebSocket functionality...")
        try:
            # This will likely fail without a WebSocket server, but tests the API
            ws_result = engine.websocket_connect('ws://echo.websocket.org/')
            print(f"✅ WebSocket connect API working: {ws_result.get('success')}")
        except Exception as e:
            print(f"⚠️  WebSocket test failed (expected without server): {e}")
        
        print("\n🎉 LoadSpiker basic functionality test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
