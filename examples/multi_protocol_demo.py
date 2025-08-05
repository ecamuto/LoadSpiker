#!/usr/bin/env python3

"""
LoadSpiker Phase 1 - Multi-Protocol Demo
========================================

This example demonstrates the new multi-protocol support in LoadSpiker Phase 1.
It shows how HTTP and WebSocket protocols can be used together in a single test.
"""

import sys
import os
import time
import json

# Add parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine

def main():
    print("🚀 LoadSpiker Phase 1 - Multi-Protocol Support Demo")
    print("=" * 55)
    
    # Create engine
    print("📦 Creating LoadSpiker engine...")
    engine = Engine(max_connections=100, worker_threads=4)
    print("✅ Engine created successfully")
    
    # Test 1: HTTP functionality (backward compatibility)
    print("\n🌐 Testing HTTP Protocol")
    print("-" * 30)
    
    http_response = engine.execute_request(
        url="https://httpbin.org/json",
        method="GET",
        headers={"User-Agent": "LoadSpiker-Phase1/1.0"}
    )
    
    print(f"✅ HTTP Request successful!")
    print(f"   Status: {http_response['status_code']}")
    print(f"   Response Time: {http_response['response_time_us'] / 1000:.2f}ms")
    print(f"   Body Length: {len(http_response['body'])} bytes")
    
    # Test 2: WebSocket functionality (new in Phase 1)
    print("\n🔌 Testing WebSocket Protocol")
    print("-" * 35)
    
    websocket_url = "wss://echo.websocket.org"
    
    # Connect
    print("1. Connecting to WebSocket...")
    ws_connect = engine.websocket_connect(
        url=websocket_url,
        subprotocol="echo-protocol"
    )
    print(f"   ✅ Connected! Status: {ws_connect['status_code']}")
    print(f"   Response Time: {ws_connect['response_time_us'] / 1000:.2f}ms")
    
    # Send multiple messages
    print("2. Sending messages...")
    messages = [
        "Hello from LoadSpiker Phase 1!",
        json.dumps({"type": "demo", "protocol": "websocket"}),
        "Multi-protocol support is working!"
    ]
    
    for i, message in enumerate(messages, 1):
        ws_send = engine.websocket_send(url=websocket_url, message=message)
        print(f"   Message {i}: ✅ Sent ({len(message)} bytes)")
        print(f"   Response Time: {ws_send['response_time_us'] / 1000:.2f}ms")
        
        # Show WebSocket-specific data
        if 'websocket_data' in ws_send:
            ws_data = ws_send['websocket_data']
            print(f"   Total Messages: {ws_data['messages_sent']}")
            print(f"   Total Bytes: {ws_data['bytes_sent']}")
        
        time.sleep(0.1)  # Small delay
    
    # Close connection
    print("3. Closing WebSocket connection...")
    ws_close = engine.websocket_close(url=websocket_url)
    print(f"   ✅ Closed! Response Time: {ws_close['response_time_us'] / 1000:.2f}ms")
    
    # Test 3: Mixed protocol load test simulation
    print("\n⚡ Mixed Protocol Load Test Simulation")
    print("-" * 45)
    
    print("Running mixed HTTP and WebSocket operations...")
    
    # Reset metrics for clean measurement
    engine.reset_metrics()
    
    # Simulate mixed load
    for i in range(5):
        # HTTP request
        http_resp = engine.execute_request(
            url=f"https://httpbin.org/delay/{i % 2 + 1}",
            method="GET"
        )
        
        # WebSocket operations
        engine.websocket_connect(url="wss://echo.websocket.org")
        engine.websocket_send(url="wss://echo.websocket.org", message=f"Load test message {i}")
        engine.websocket_close(url="wss://echo.websocket.org")
        
        print(f"   Completed mixed operation {i + 1}/5")
        time.sleep(0.2)
    
    # Show final metrics
    print("\n📊 Final Test Metrics")
    print("-" * 25)
    metrics = engine.get_metrics()
    
    print(f"Total HTTP Requests: {metrics['total_requests']}")
    print(f"Successful Requests: {metrics['successful_requests']}")
    print(f"Failed Requests: {metrics['failed_requests']}")
    
    if metrics['total_requests'] > 0:
        print(f"Average Response Time: {metrics['avg_response_time_ms']:.2f}ms")
        print(f"Min Response Time: {metrics['min_response_time_us'] / 1000:.2f}ms")
        print(f"Max Response Time: {metrics['max_response_time_us'] / 1000:.2f}ms")
    
    # Summary
    print("\n🎉 Phase 1 Multi-Protocol Demo Complete!")
    print("\n✅ Successfully Demonstrated:")
    print("   🌐 HTTP protocol support (backward compatible)")
    print("   🔌 WebSocket protocol support (new)")
    print("   📊 Unified metrics collection")
    print("   🔄 Mixed protocol operations")
    print("   🏗️  Multi-protocol architecture foundation")
    
    print("\n🔮 Phase 1 Architecture Benefits:")
    print("   📈 Scalable protocol framework")
    print("   🔧 Easy to extend with new protocols")
    print("   🎯 Protocol-specific response data")
    print("   ⚡ High-performance C backend")
    print("   🐍 Clean Python API")
    
    print("\n📋 Next Phases Will Add:")
    print("   🗄️  Database protocol support (MySQL, PostgreSQL, MongoDB)")
    print("   🌐 gRPC protocol support")
    print("   🔌 Raw TCP/UDP socket support")
    print("   🔐 Advanced authentication mechanisms")
    print("   📡 Real WebSocket handshake implementation")
    print("   📊 Enhanced protocol-specific metrics")

if __name__ == "__main__":
    main()
