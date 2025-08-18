#!/usr/bin/env python3

"""
LoadSpiker UDP Socket Protocol Demo
==================================

This example demonstrates the new UDP socket protocol support in LoadSpiker.
It shows how to test UDP servers and services using LoadSpiker's high-performance engine.
"""

import sys
import os
import time
import threading
import socket

# Add parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine
from loadspiker.scenarios import UDPScenario, MixedProtocolScenario


class SimpleUDPEchoServer:
    """Simple UDP echo server for demonstration purposes"""
    
    def __init__(self, host='localhost', port=0):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.thread = None
        self.received_messages = []
        
    def start(self):
        """Start the echo server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((self.host, self.port))
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
        self.server_socket.settimeout(0.1)  # Short timeout for responsiveness
        
        while self.running:
            try:
                data, addr = self.server_socket.recvfrom(1024)
                message = data.decode('utf-8')
                self.received_messages.append((message, addr))
                print(f"   📥 Received from {addr}: {message}")
                
                # Echo the data back
                self.server_socket.sendto(data, addr)
                print(f"   📤 Echoed to {addr}: {message}")
                
            except socket.timeout:
                continue
            except OSError:
                break


def main():
    print("🚀 LoadSpiker UDP Socket Protocol Demo")
    print("=" * 50)
    
    # Create engine
    print("📦 Creating LoadSpiker engine...")
    engine = Engine(max_connections=100, worker_threads=4)
    print("✅ Engine created successfully")
    
    # Start demo UDP server
    print("\n🖥️  Starting Demo UDP Echo Server...")
    server = SimpleUDPEchoServer()
    port = server.start()
    print(f"✅ UDP Echo Server started on port {port}")
    
    try:
        # Test 1: Basic UDP Operations
        print("\n📡 Testing Basic UDP Operations")
        print("-" * 35)
        
        # Create endpoint
        print("🔗 Creating UDP endpoint...")
        create_response = engine.udp_create_endpoint('localhost', 0)  # Auto-assign port
        print(f"   Result: {'✅ Success' if create_response['success'] else '❌ Failed'}")
        print(f"   Response Time: {create_response['response_time_ms']:.2f}ms")
        print(f"   Message: {create_response['body']}")
        
        if create_response['success']:
            # Send data
            test_messages = [
                "Hello UDP World!",
                "LoadSpiker UDP Test",
                "Datagram testing in progress...",
                "Final UDP message!"
            ]
            
            for message in test_messages:
                print(f"\n📤 Sending: '{message}'")
                send_response = engine.udp_send('localhost', port, message, timeout_ms=5000)
                print(f"   Send Result: {'✅ Success' if send_response['success'] else '❌ Failed'}")
                print(f"   Response Time: {send_response['response_time_ms']:.2f}ms")
                print(f"   Response: {send_response['body']}")
                
                time.sleep(0.3)  # Give server time to process
            
            # Close endpoint
            print("\n🔌 Closing UDP endpoint...")
            close_response = engine.udp_close_endpoint('localhost', 0)
            print(f"   Result: {'✅ Success' if close_response['success'] else '❌ Failed'}")
            if close_response['success']:
                print(f"   Response Time: {close_response['response_time_ms']:.2f}ms")
                print(f"   Message: {close_response['body']}")
        
        # Test 2: UDP Scenario Usage
        print("\n🎬 Testing UDP Scenario")
        print("-" * 25)
        
        # Create a UDP scenario
        udp_scenario = UDPScenario('localhost', port, "Echo Test Scenario")
        
        # Add a complete echo test
        udp_scenario.add_echo_test("Hello from UDP Scenario!", timeout_ms=3000)
        
        # Add a broadcast test
        udp_scenario.add_broadcast_test("Broadcast message", timeout_ms=2000)
        
        # Build operations
        operations = udp_scenario.build_udp_operations()
        print(f"✅ UDP scenario created with {len(operations)} operations")
        print("   Operations:")
        for i, op in enumerate(operations, 1):
            print(f"      {i}. {op['type']} - {op.get('data', 'N/A')}")
        
        # Test 3: Multiple UDP Clients
        print("\n🔀 Testing Multiple UDP Clients")
        print("-" * 32)
        
        def udp_worker(worker_id):
            """Worker function for concurrent UDP testing"""
            print(f"   Worker {worker_id}: Creating endpoint...")
            create_resp = engine.udp_create_endpoint('localhost', 0)
            if create_resp['success']:
                message = f"Message from UDP worker {worker_id}"
                print(f"   Worker {worker_id}: Sending '{message}'")
                send_resp = engine.udp_send('localhost', port, message, timeout_ms=3000)
                if send_resp['success']:
                    print(f"   Worker {worker_id}: Message sent successfully")
                engine.udp_close_endpoint('localhost', 0)
                print(f"   Worker {worker_id}: Endpoint closed")
        
        # Run multiple workers concurrently
        print("   Starting 3 concurrent UDP workers...")
        threads = []
        for i in range(3):
            thread = threading.Thread(target=udp_worker, args=(i+1,))
            thread.start()
            threads.append(thread)
        
        # Wait for all workers to complete
        for thread in threads:
            thread.join()
        
        print("   ✅ All workers completed")
        
        # Wait for server to process all messages
        time.sleep(0.5)
        print(f"   📊 Server received {len(server.received_messages)} total messages")
        
        # Test 4: UDP Special Cases
        print("\n🎯 Testing UDP Special Cases")
        print("-" * 30)
        
        # Test broadcast address (might require special permissions)
        print("   Testing broadcast address...")
        broadcast_response = engine.udp_send('255.255.255.255', 8080, 'broadcast test', timeout_ms=1000)
        print(f"   Broadcast Result: {'✅ Success' if broadcast_response['success'] else '⚠️ Limited (expected)'}") 
        
        # Test multicast address
        print("   Testing multicast address...")
        multicast_response = engine.udp_send('224.1.1.1', 8080, 'multicast test', timeout_ms=1000)
        print(f"   Multicast Result: {'✅ Success' if multicast_response['success'] else '⚠️ Limited (expected)'}")
        
        # Test zero-length message
        print("   Testing zero-length message...")
        zero_response = engine.udp_send('localhost', port, '', timeout_ms=1000)
        print(f"   Zero-length Result: {'✅ Success' if zero_response['success'] else '❌ Failed'}")
        
        # Test large message (within UDP limits)
        print("   Testing large message (1KB)...")
        large_message = "A" * 1000
        large_response = engine.udp_send('localhost', port, large_message, timeout_ms=1000)
        print(f"   Large Message Result: {'✅ Success' if large_response['success'] else '❌ Failed'}")
        
        # Test 5: Error Handling
        print("\n❌ Testing UDP Error Handling")
        print("-" * 30)
        
        # Test receive without endpoint
        print("   Testing receive without endpoint...")
        receive_error = engine.udp_receive('localhost', 65432, timeout_ms=1000)
        print(f"   Result: {'❌ Failed as expected' if not receive_error['success'] else '⚠️ Unexpected success'}")
        print(f"   Error: {receive_error['error_message']}")
        
        # Test close without endpoint
        print("   Testing close without endpoint...")
        close_error = engine.udp_close_endpoint('localhost', 65433)
        print(f"   Result: {'❌ Failed as expected' if not close_error['success'] else '⚠️ Unexpected success'}")
        print(f"   Error: {close_error['error_message']}")
        
        # Test 6: Performance Metrics
        print("\n📈 UDP Performance Metrics")
        print("-" * 27)
        
        # Reset metrics for clean measurement
        engine.reset_metrics()
        
        # Run some UDP operations
        print("   Running UDP performance test...")
        for i in range(10):
            engine.udp_send('localhost', port, f'Performance test packet {i+1}', timeout_ms=1000)
        
        # Show metrics
        metrics = engine.get_metrics()
        print(f"   ✅ UDP performance test completed!")
        print(f"   Total UDP Operations: {metrics['total_requests']}")
        print(f"   Successful Operations: {metrics['successful_requests']}")
        print(f"   Failed Operations: {metrics['failed_requests']}")
        
        if metrics['total_requests'] > 0:
            success_rate = (metrics['successful_requests'] / metrics['total_requests']) * 100
            print(f"   Success Rate: {success_rate:.1f}%")
            
            # Note: Specific response time metrics depend on the Python fallback implementation
            if 'min_response_time_ms' in metrics:
                print(f"   Min Response Time: {metrics['min_response_time_ms']:.2f}ms")
                print(f"   Max Response Time: {metrics['max_response_time_ms']:.2f}ms")
        
        # Test 7: Mixed Protocol Scenario
        print("\n🔀 Testing Mixed Protocol Scenario")
        print("-" * 35)
        
        mixed_scenario = MixedProtocolScenario("UDP and HTTP Mixed Test")
        
        # Add HTTP request
        mixed_scenario.add_http_request("https://httpbin.org/get", "GET")
        
        # Note: UDP operations would need to be added to MixedProtocolScenario
        # This demonstrates the intended integration pattern
        
        mixed_operations = mixed_scenario.build_mixed_operations()
        print(f"   ✅ Mixed scenario created with {len(mixed_operations)} operations")
        print("   Protocol Distribution:")
        protocol_counts = {}
        for op in mixed_operations:
            protocol_counts[op['type']] = protocol_counts.get(op['type'], 0) + 1
        for protocol, count in protocol_counts.items():
            print(f"      {protocol.title()}: {count} operations")
        
        # Test 8: UDP vs TCP Comparison
        print("\n⚖️  UDP vs TCP Characteristics Demo")
        print("-" * 38)
        
        print("   📊 UDP Characteristics Demonstrated:")
        print("      • Connectionless communication")
        print("      • No connection setup/teardown overhead") 
        print("      • Best-effort delivery (no guarantees)")
        print("      • Lower latency than TCP")
        print("      • Suitable for real-time applications")
        print("      • Broadcast and multicast support")
        
        print("   🔄 Message Flow Summary:")
        print(f"      • Total messages sent to server: {len([m for m in server.received_messages])}")
        print("      • No connection state maintained")
        print("      • Each datagram is independent")
        
    finally:
        server.stop()
        print("\n🛑 Demo UDP server stopped")
    
    # Summary
    print("\n🎉 UDP Protocol Demo Complete!")
    print("\n✅ Successfully Demonstrated:")
    print("   📡 UDP endpoint creation and management")
    print("   📤 UDP datagram transmission")
    print("   🎬 UDP scenario building and execution")
    print("   🔀 Multiple concurrent UDP clients")
    print("   🎯 UDP special cases (broadcast, multicast, zero-length)")
    print("   ❌ Comprehensive error handling")
    print("   📈 Performance metrics collection")
    print("   🔄 Echo server communication patterns")
    
    print("\n🔮 UDP Protocol Benefits:")
    print("   ⚡ High-performance C backend for UDP operations")
    print("   🐍 Clean Python API for easy integration")
    print("   📊 Protocol-specific response data and metrics")
    print("   🌐 Connectionless communication efficiency")
    print("   🎯 Realistic UDP load testing capabilities")
    print("   📡 Broadcast and multicast support")
    print("   ⚡ Low-latency datagram delivery")
    
    print("\n🎯 UDP Use Cases:")
    print("   🎮 Gaming servers (real-time multiplayer)")
    print("   📺 Video/audio streaming services")
    print("   🌐 DNS and DHCP services")
    print("   📊 IoT sensor data collection")
    print("   📈 High-frequency trading systems")
    print("   🔔 Notification and alerting systems")
    
    print("\n📋 Future UDP Enhancements:")
    print("   🌐 IPv6 UDP support")
    print("   📡 Advanced multicast group management")
    print("   📊 UDP-specific metrics (packet loss, jitter)")
    print("   🔒 DTLS (Datagram TLS) support")
    print("   📈 Bandwidth and throughput optimization")
    print("   🎯 QoS (Quality of Service) testing")


if __name__ == "__main__":
    main()
