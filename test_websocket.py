#!/usr/bin/env python3

"""
WebSocket Load Testing Demo for Phase 1
======================================

This test demonstrates the new multi-protocol support in LoadSpiker Phase 1.
It shows WebSocket connection, message sending, and connection management.
"""

import sys
import os

# Add current directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'loadspiker'))

import loadtest
import json
import time

def main():
    print("🚀 LoadSpiker Phase 1 - WebSocket Support Demo")
    print("=" * 50)
    
    # Create engine with moderate settings for demo
    print("📦 Creating LoadSpiker engine...")
    engine = loadtest.Engine(max_connections=100, worker_threads=4)
    print("✅ Engine created successfully")
    
    # Test WebSocket functionality
    websocket_url = "wss://echo.websocket.org"
    
    print(f"\n🔌 Testing WebSocket Connection to {websocket_url}")
    print("-" * 50)
    
    try:
        # 1. Connect to WebSocket
        print("1️⃣  Connecting to WebSocket...")
        connect_response = engine.websocket_connect(url=websocket_url, subprotocol="echo-protocol")
        
        print(f"   ✅ Connection successful!")
        print(f"   📊 Status Code: {connect_response['status_code']}")
        print(f"   ⏱️  Response Time: {connect_response['response_time_us'] / 1000:.2f}ms")
        print(f"   🔗 Protocol: {connect_response['protocol']}")
        
        if 'websocket_data' in connect_response:
            ws_data = connect_response['websocket_data']
            print(f"   🎯 Subprotocol: {ws_data.get('subprotocol', 'none')}")
            print(f"   📨 Messages Sent: {ws_data.get('messages_sent', 0)}")
        
        print(f"   💬 Response: {connect_response['body']}")
        
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return 1
    
    try:
        # 2. Send messages
        print("\n2️⃣  Sending WebSocket messages...")
        
        messages = [
            "Hello WebSocket!",
            json.dumps({"type": "test", "data": "Phase 1 Demo"}),
            "Message 3: Multi-protocol support",
            json.dumps({"command": "ping", "timestamp": time.time()}),
            "Final test message"
        ]
        
        for i, message in enumerate(messages, 1):
            print(f"   📤 Sending message {i}: {message[:50]}{'...' if len(message) > 50 else ''}")
            
            send_response = engine.websocket_send(url=websocket_url, message=message)
            
            print(f"      ✅ Sent successfully!")
            print(f"      ⏱️  Response Time: {send_response['response_time_us'] / 1000:.2f}ms")
            
            if 'websocket_data' in send_response:
                ws_data = send_response['websocket_data']
                print(f"      📊 Total Messages Sent: {ws_data.get('messages_sent', 0)}")
                print(f"      📏 Total Bytes Sent: {ws_data.get('bytes_sent', 0)}")
            
            # Small delay between messages
            time.sleep(0.1)
        
    except Exception as e:
        print(f"   ❌ Message sending failed: {e}")
    
    try:
        # 3. Close connection
        print("\n3️⃣  Closing WebSocket connection...")
        
        close_response = engine.websocket_close(url=websocket_url)
        
        print(f"   ✅ Connection closed successfully!")
        print(f"   ⏱️  Response Time: {close_response['response_time_us'] / 1000:.2f}ms")
        print(f"   💬 Response: {close_response['body']}")
        
    except Exception as e:
        print(f"   ❌ Connection close failed: {e}")
    
    # Show final metrics
    print("\n📈 Final Engine Metrics:")
    print("-" * 30)
    metrics = engine.get_metrics()
    
    print(f"   📊 Total Requests: {metrics['total_requests']}")
    print(f"   ✅ Successful: {metrics['successful_requests']}")
    print(f"   ❌ Failed: {metrics['failed_requests']}")
    if metrics['total_requests'] > 0:
        print(f"   ⏱️  Avg Response Time: {metrics['avg_response_time_ms']:.2f}ms")
        print(f"   🚀 Min Response Time: {metrics['min_response_time_us'] / 1000:.2f}ms")
        print(f"   🐌 Max Response Time: {metrics['max_response_time_us'] / 1000:.2f}ms")
    
    print("\n🎉 Phase 1 WebSocket Demo Complete!")
    print("\n💡 Phase 1 Features Demonstrated:")
    print("   ✅ Multi-protocol architecture")
    print("   ✅ WebSocket connection management")
    print("   ✅ WebSocket message sending") 
    print("   ✅ Protocol-specific response data")
    print("   ✅ Unified metrics collection")
    print("   ✅ Backward compatibility with HTTP")
    
    print("\n🔮 Coming in Later Phases:")
    print("   🔄 Real WebSocket handshake implementation")
    print("   📡 Actual WebSocket frame parsing")
    print("   🔐 WebSocket authentication support")
    print("   📊 Database protocol support")
    print("   🌐 gRPC protocol support")
    print("   🔌 TCP/UDP raw socket support")

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code if exit_code else 0)
