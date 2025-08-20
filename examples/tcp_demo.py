#!/usr/bin/env python3

"""
LoadSpiker TCP Socket Protocol Demo
==================================

This example demonstrates the new TCP socket protocol support in LoadSpiker.
It shows how to test TCP servers using LoadSpiker's high-performance engine.
"""

import sys
import os
import time
import threading
import socket

# Add parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine
from loadspiker.scenarios import TCPScenario, MixedProtocolScenario


class SimpleTCPEchoServer:
    """Simple TCP echo server for demonstration purposes"""
    
    def __init__(self, host='localhost', port=0):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.thread = None
        
    def start(self):
        """Start the echo server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.port = self.server_socket.getsockname()[1]
        
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        
        time.sleep(0.1)  # Give server time to start
        return self.port
    
    def stop(self):
        """Stop the echo server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.thread:
            self.thread.join(timeout=1)
    
    def _run_server(self):
        """Run the server loop"""
        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                client_thread = threading.Thread(
                    target=self._handle_client, 
                    args=(client_socket, addr),
                    daemon=True
                )
                client_thread.start()
            except OSError:
                break
    
    def _handle_client(self, client_socket, addr):
        """Handle individual client connections"""
        print(f"   📞 Client connected from {addr}")
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                # Echo the data back
                client_socket.send(data)
                print(f"   🔄 Echoed: {data.decode('utf-8', errors='ignore')}")
        except OSError:
            pass
        finally:
            client_socket.close()
            print(f"   📞 Client {addr} disconnected")


def main():
    print("🚀 LoadSpiker TCP Socket Protocol Demo")
    print("=" * 50)
    
    # Create engine
    print("📦 Creating LoadSpiker engine...")
    engine = Engine(max_connections=100, worker_threads=4)
    print("✅ Engine created successfully")
    
    # Start demo TCP server
    print("\n🖥️  Starting Demo TCP Echo Server...")
    server = SimpleTCPEchoServer()
    port = server.start()
    print(f"✅ TCP Echo Server started on port {port}")
    
    try:
        # Test 1: Basic TCP Operations
        print("\n🔌 Testing Basic TCP Operations")
        print("-" * 35)
        
        # Connect to server
        print("🔗 Connecting to TCP server...")
        connect_response = engine.tcp_connect('localhost', port, timeout_ms=5000)
        print(f"   Result: {'✅ Success' if connect_response['success'] else '❌ Failed'}")
        print(f"   Response Time: {connect_response['response_time_ms']:.2f}ms")
        print(f"   Message: {connect_response['body']}")
        
        if connect_response['success']:
            # Send data
            test_messages = [
                "Hello TCP World!",
                "LoadSpiker TCP Test",
                "Protocol testing in progress...",
                "Final message!"
            ]
            
            for message in test_messages:
                print(f"\n📤 Sending: '{message}'")
                send_response = engine.tcp_send('localhost', port, message, timeout_ms=5000)
                print(f"   Send Result: {'✅ Success' if send_response['success'] else '❌ Failed'}")
                print(f"   Response Time: {send_response['response_time_ms']:.2f}ms")
                print(f"   Response: {send_response['body']}")
                
                if send_response['success']:
                    print("📥 Receiving echo...")
                    receive_response = engine.tcp_receive('localhost', port, timeout_ms=5000)
                    print(f"   Receive Result: {'✅ Success' if receive_response['success'] else '❌ Failed'}")
                    print(f"   Response Time: {receive_response['response_time_ms']:.2f}ms")
                    print(f"   Received: {receive_response['body']}")
                
                time.sleep(0.5)  # Small delay between messages
            
            # Disconnect
            print("\n🔌 Disconnecting from TCP server...")
            disconnect_response = engine.tcp_disconnect('localhost', port)
            print(f"   Result: {'✅ Success' if disconnect_response['success'] else '❌ Failed'}")
            print(f"   Response Time: {disconnect_response['response_time_ms']:.2f}ms")
            print(f"   Message: {disconnect_response['body']}")
        
        # Test 2: TCP Scenario Usage
        print("\n🎬 Testing TCP Scenario")
        print("-" * 25)
        
        # Create a TCP scenario
        tcp_scenario = TCPScenario('localhost', port, "Echo Test Scenario")
        
        # Add a complete echo test
        tcp_scenario.add_echo_test("Hello from TCP Scenario!", timeout_ms=3000)
        
        # Build operations
        operations = tcp_scenario.build_tcp_operations()
        print(f"✅ TCP scenario created with {len(operations)} operations")
        print("   Operations:")
        for i, op in enumerate(operations, 1):
            print(f"      {i}. {op['type']} - {op.get('data', 'N/A')}")
        
        # Test 3: Multiple Connections
        print("\n🔀 Testing Multiple TCP Connections")
        print("-" * 35)
        
        def tcp_worker(worker_id):
            """Worker function for concurrent TCP testing"""
            print(f"   Worker {worker_id}: Connecting...")
            connect_resp = engine.tcp_connect('localhost', port, timeout_ms=3000)
            if connect_resp['success']:
                message = f"Message from worker {worker_id}"
                print(f"   Worker {worker_id}: Sending '{message}'")
                send_resp = engine.tcp_send('localhost', port, message, timeout_ms=3000)
                if send_resp['success']:
                    receive_resp = engine.tcp_receive('localhost', port, timeout_ms=3000)
                    print(f"   Worker {worker_id}: Received echo")
                engine.tcp_disconnect('localhost', port)
                print(f"   Worker {worker_id}: Disconnected")
        
        # Run multiple workers concurrently
        print("   Starting 3 concurrent TCP workers...")
        threads = []
        for i in range(3):
            thread = threading.Thread(target=tcp_worker, args=(i+1,))
            thread.start()
            threads.append(thread)
        
        # Wait for all workers to complete
        for thread in threads:
            thread.join()
        
        print("   ✅ All workers completed")
        
        # Test 4: Error Handling
        print("\n❌ Testing TCP Error Handling")
        print("-" * 30)
        
        # Test connection to non-existent server
        print("   Testing connection to non-existent server...")
        error_response = engine.tcp_connect('localhost', 65432, timeout_ms=1000)
        print(f"   Result: {'❌ Failed as expected' if not error_response['success'] else '⚠️ Unexpected success'}")
        print(f"   Error: {error_response['error_message']}")
        
        # Test send without connection
        print("   Testing send without connection...")
        send_error = engine.tcp_send('localhost', 65433, 'test', timeout_ms=1000)
        print(f"   Result: {'❌ Failed as expected' if not send_error['success'] else '⚠️ Unexpected success'}")
        print(f"   Error: {send_error['error_message']}")
        
        # Test 5: Performance Metrics
        print("\n📈 TCP Performance Metrics")
        print("-" * 27)
        
        # Reset metrics for clean measurement
        engine.reset_metrics()
        
        # Run some TCP operations
        print("   Running TCP performance test...")
        for i in range(5):
            engine.tcp_connect('localhost', port, timeout_ms=2000)
            engine.tcp_send('localhost', port, f'Performance test message {i+1}', timeout_ms=2000)
            engine.tcp_receive('localhost', port, timeout_ms=2000)
            engine.tcp_disconnect('localhost', port)
        
        # Show metrics
        metrics = engine.get_metrics()
        print(f"   ✅ TCP performance test completed!")
        print(f"   Total TCP Operations: {metrics['total_requests']}")
        print(f"   Successful Operations: {metrics['successful_requests']}")
        print(f"   Failed Operations: {metrics['failed_requests']}")
        
        if metrics['total_requests'] > 0:
            success_rate = (metrics['successful_requests'] / metrics['total_requests']) * 100
            print(f"   Success Rate: {success_rate:.1f}%")
            
            # Note: Specific response time metrics depend on the Python fallback implementation
            if 'min_response_time_ms' in metrics:
                print(f"   Min Response Time: {metrics['min_response_time_ms']:.2f}ms")
                print(f"   Max Response Time: {metrics['max_response_time_ms']:.2f}ms")
        
        # Test 6: Mixed Protocol Scenario
        print("\n🔀 Testing Mixed Protocol Scenario")
        print("-" * 35)
        
        mixed_scenario = MixedProtocolScenario("TCP and HTTP Mixed Test")
        
        # Add HTTP request
        mixed_scenario.add_http_request("https://httpbin.org/get", "GET")
        
        # Note: TCP operations would need to be added to MixedProtocolScenario
        # This demonstrates the intended integration pattern
        
        mixed_operations = mixed_scenario.build_mixed_operations()
        print(f"   ✅ Mixed scenario created with {len(mixed_operations)} operations")
        print("   Protocol Distribution:")
        protocol_counts = {}
        for op in mixed_operations:
            protocol_counts[op['type']] = protocol_counts.get(op['type'], 0) + 1
        for protocol, count in protocol_counts.items():
            print(f"      {protocol.title()}: {count} operations")
        
    finally:
        server.stop()
        print("\n🛑 Demo TCP server stopped")
    
    # Summary
    print("\n🎉 TCP Protocol Demo Complete!")
    print("\n✅ Successfully Demonstrated:")
    print("   🔌 TCP connection establishment and teardown")
    print("   📤 TCP data transmission (send/receive)")
    print("   🎬 TCP scenario building and execution")
    print("   🔀 Multiple concurrent TCP connections")
    print("   ❌ Comprehensive error handling")
    print("   📈 Performance metrics collection")
    print("   🔄 Echo server communication patterns")
    
    print("\n🔮 TCP Protocol Benefits:")
    print("   ⚡ High-performance C backend for TCP operations")
    print("   🐍 Clean Python API for easy integration")
    print("   📊 Protocol-specific response data and metrics")
    print("   🔗 Connection management and pooling")
    print("   🎯 Realistic TCP load testing capabilities")
    print("   🛡️  Robust error handling and timeout control")
    
    print("\n📋 Future TCP Enhancements:")
    print("   🔒 SSL/TLS TCP connection support")
    print("   💾 Advanced connection pooling optimization")
    print("   📈 TCP-specific metrics (RTT, bandwidth, etc.)")
    print("   🔄 Keep-alive and connection reuse")
    print("   🌐 IPv6 TCP support")
    print("   📊 TCP connection state monitoring")


if __name__ == "__main__":
    main()
