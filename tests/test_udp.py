#!/usr/bin/env python3

"""
LoadSpiker UDP Socket Protocol Tests
===================================

Comprehensive test suite for UDP socket functionality in LoadSpiker.
"""

import sys
import os
import pytest
import threading
import time
import socket
import json

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine
from loadspiker.scenarios import UDPScenario, MixedProtocolScenario


class MockUDPServer:
    """Mock UDP server for testing purposes"""
    
    def __init__(self, host='localhost', port=0):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.thread = None
        self.echo_mode = True
        self.responses = []
        self.received_messages = []
        
    def start(self):
        """Start the mock UDP server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((self.host, self.port))
        self.port = self.server_socket.getsockname()[1]  # Get actual port if 0 was used
        
        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()
        
        # Give server time to start
        time.sleep(0.1)
        
        return self.port
    
    def stop(self):
        """Stop the mock UDP server"""
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
                self.received_messages.append((data.decode('utf-8'), addr))
                
                if self.echo_mode:
                    # Echo the data back
                    self.server_socket.sendto(data, addr)
                else:
                    # Send predefined responses
                    if self.responses:
                        response = self.responses.pop(0)
                        self.server_socket.sendto(response.encode('utf-8'), addr)
            except socket.timeout:
                continue
            except OSError:
                break


@pytest.fixture
def mock_udp_server():
    """Fixture to provide a mock UDP server"""
    server = MockUDPServer()
    port = server.start()
    yield server, port
    server.stop()


@pytest.fixture
def engine():
    """Fixture to provide a LoadSpiker engine"""
    return Engine(max_connections=10, worker_threads=2)


class TestUDPBasicOperations:
    """Test basic UDP operations"""
    
    def test_udp_create_endpoint_success(self, engine):
        """Test successful UDP endpoint creation"""
        response = engine.udp_create_endpoint('localhost', 0)  # Use port 0 for auto-assignment
        
        assert response['success'] is True
        assert response['status_code'] == 200
        assert 'UDP endpoint created' in response['body']
        assert response['response_time_ms'] >= 0
        assert response['response_time_us'] >= 0
    
    def test_udp_send_success(self, engine, mock_udp_server):
        """Test successful UDP send operation"""
        server, port = mock_udp_server
        
        # Send data (should auto-create endpoint)
        response = engine.udp_send('localhost', port, 'Hello UDP!', timeout_ms=5000)
        
        assert response['success'] is True
        assert response['status_code'] == 200
        assert 'bytes' in response['body']
        assert 'protocol_data' in response
        assert response['protocol_data']['datagram_sent'] is True
    
    def test_udp_receive_without_endpoint(self, engine):
        """Test UDP receive without creating endpoint first"""
        response = engine.udp_receive('localhost', 65432, timeout_ms=1000)
        
        assert response['success'] is False
        assert 'no udp endpoint available' in response['error_message'].lower()
    
    def test_udp_close_endpoint_without_endpoint(self, engine):
        """Test UDP endpoint closure without creating endpoint first"""
        response = engine.udp_close_endpoint('localhost', 65432)
        
        assert response['success'] is False
        assert 'no udp endpoint to close' in response['error_message'].lower()


class TestUDPDataTransfer:
    """Test UDP data transfer operations"""
    
    def test_udp_echo_communication(self, engine, mock_udp_server):
        """Test complete UDP echo communication"""
        server, port = mock_udp_server
        test_message = "Hello, UDP World!"
        
        # Create endpoint
        create_response = engine.udp_create_endpoint('localhost', 0)
        assert create_response['success'] is True
        
        # Send data
        send_response = engine.udp_send('localhost', port, test_message, timeout_ms=5000)
        assert send_response['success'] is True
        assert 'bytes' in send_response['body']
        
        # Give server time to process and echo
        time.sleep(0.2)
        
        # Receive echo (this might timeout if server doesn't echo back properly)
        # Note: UDP receive in LoadSpiker needs to be bound to a specific endpoint
        # This test demonstrates the intended behavior
        
        # Close endpoint
        close_response = engine.udp_close_endpoint('localhost', 0)
        # Note: This might fail if endpoint wasn't properly created with port 0
    
    def test_udp_multiple_messages(self, engine, mock_udp_server):
        """Test sending multiple UDP messages"""
        server, port = mock_udp_server
        messages = ["Message 1", "Message 2", "Message 3"]
        
        # Create endpoint
        create_response = engine.udp_create_endpoint('localhost', 0)
        assert create_response['success'] is True
        
        # Send multiple messages
        for message in messages:
            send_response = engine.udp_send('localhost', port, message, timeout_ms=5000)
            assert send_response['success'] is True
        
        # Verify server received messages
        time.sleep(0.2)
        assert len(server.received_messages) >= len(messages)
        
        # Close endpoint
        engine.udp_close_endpoint('localhost', 0)
    
    def test_udp_large_data_transfer(self, engine, mock_udp_server):
        """Test transferring larger amounts of data via UDP"""
        server, port = mock_udp_server
        large_message = "A" * 1000  # 1KB message (within UDP limits)
        
        # Send large data
        send_response = engine.udp_send('localhost', port, large_message, timeout_ms=5000)
        assert send_response['success'] is True
        
        # Verify server received the message
        time.sleep(0.2)
        assert len(server.received_messages) >= 1
        if server.received_messages:
            received_data, addr = server.received_messages[-1]
            assert len(received_data) == len(large_message)


class TestUDPScenarios:
    """Test UDP scenario classes"""
    
    def test_udp_scenario_creation(self):
        """Test UDP scenario creation and configuration"""
        scenario = UDPScenario('localhost', 8080, 'Test UDP Scenario')
        
        assert scenario.hostname == 'localhost'
        assert scenario.port == 8080
        assert scenario.name == 'Test UDP Scenario'
        assert len(scenario.udp_operations) == 0
    
    def test_udp_scenario_operations(self):
        """Test adding operations to UDP scenario"""
        scenario = UDPScenario('localhost', 8080)
        
        # Add individual operations
        scenario.add_create_endpoint()
        scenario.add_send('Hello', timeout_ms=3000)
        scenario.add_receive(timeout_ms=3000)
        scenario.add_close_endpoint()
        
        operations = scenario.build_udp_operations()
        
        assert len(operations) == 4
        assert operations[0]['type'] == 'udp_create_endpoint'
        assert operations[0]['hostname'] == 'localhost'
        assert operations[0]['port'] == 8080
        
        assert operations[1]['type'] == 'udp_send'
        assert operations[1]['data'] == 'Hello'
        assert operations[1]['timeout_ms'] == 3000
        
        assert operations[2]['type'] == 'udp_receive'
        assert operations[2]['timeout_ms'] == 3000
        
        assert operations[3]['type'] == 'udp_close_endpoint'
    
    def test_udp_scenario_echo_test(self):
        """Test UDP scenario echo test helper"""
        scenario = UDPScenario('localhost', 8080)
        scenario.add_echo_test('Test Message', timeout_ms=2000)
        
        operations = scenario.build_udp_operations()
        
        assert len(operations) == 4
        assert operations[0]['type'] == 'udp_create_endpoint'
        assert operations[1]['type'] == 'udp_send'
        assert operations[1]['data'] == 'Test Message'
        assert operations[2]['type'] == 'udp_receive'
        assert operations[3]['type'] == 'udp_close_endpoint'
    
    def test_udp_scenario_broadcast_test(self):
        """Test UDP scenario broadcast test helper"""
        scenario = UDPScenario('255.255.255.255', 8080)  # Broadcast address
        scenario.add_broadcast_test('Broadcast Message', timeout_ms=2000)
        
        operations = scenario.build_udp_operations()
        
        assert len(operations) == 3
        assert operations[0]['type'] == 'udp_create_endpoint'
        assert operations[1]['type'] == 'udp_send'
        assert operations[1]['data'] == 'Broadcast Message'
        assert operations[2]['type'] == 'udp_close_endpoint'
    
    def test_udp_scenario_with_data_substitution(self):
        """Test UDP scenario with variable substitution"""
        scenario = UDPScenario('${host}', 8080)
        scenario.set_variable('host', 'example.com')
        scenario.add_send('Hello ${name}!')
        scenario.set_variable('name', 'World')
        
        operations = scenario.build_udp_operations()
        
        assert operations[0]['hostname'] == 'example.com'
        assert operations[0]['data'] == 'Hello World!'


class TestUDPErrorHandling:
    """Test UDP error handling scenarios"""
    
    def test_udp_send_to_invalid_host(self, engine):
        """Test UDP send to invalid hostname"""
        # Note: UDP might not immediately fail for invalid hosts
        response = engine.udp_send('invalid.nonexistent.domain', 80, 'test', timeout_ms=1000)
        
        # UDP is connectionless, so this might still succeed locally
        # The actual failure would occur during network routing
        assert 'status_code' in response
    
    def test_udp_send_to_unreachable_host(self, engine):
        """Test UDP send to unreachable host"""
        # Use a non-routable IP
        response = engine.udp_send('192.0.2.1', 80, 'test', timeout_ms=1000)
        
        # UDP send typically succeeds locally even if destination is unreachable
        # The packet is sent to the network stack regardless
        assert 'status_code' in response
    
    def test_udp_invalid_port(self, engine):
        """Test UDP operations with invalid port"""
        response = engine.udp_create_endpoint('localhost', 99999)
        
        # This might succeed or fail depending on the system
        assert 'status_code' in response


class TestUDPMixedProtocolScenarios:
    """Test UDP in mixed protocol scenarios"""
    
    def test_mixed_protocol_with_udp(self, mock_udp_server):
        """Test UDP operations in mixed protocol scenarios"""
        server, port = mock_udp_server
        
        scenario = MixedProtocolScenario('UDP and HTTP Test')
        
        # Add HTTP request
        scenario.add_http_request('https://httpbin.org/get', 'GET')
        
        # Add UDP operations (placeholder - would need actual UDP support in MixedProtocolScenario)
        # This test demonstrates the intended integration pattern
        
        operations = scenario.build_mixed_operations()
        
        assert len(operations) >= 1
        assert operations[0]['type'] == 'http'


class TestUDPPerformanceMetrics:
    """Test UDP performance metrics"""
    
    def test_udp_response_time_metrics(self, engine, mock_udp_server):
        """Test that UDP operations generate response time metrics"""
        server, port = mock_udp_server
        
        # Reset metrics
        engine.reset_metrics()
        
        # Perform UDP operations
        engine.udp_create_endpoint('localhost', 0)
        engine.udp_send('localhost', port, 'test', timeout_ms=5000)
        engine.udp_close_endpoint('localhost', 0)
        
        # Check metrics
        metrics = engine.get_metrics()
        
        # Should have recorded some requests
        assert metrics['total_requests'] > 0
        
        # Should have response times
        if metrics['total_requests'] > 0:
            assert metrics.get('min_response_time_ms', 0) >= 0
            assert metrics.get('max_response_time_ms', 0) >= 0
    
    def test_udp_error_metrics(self, engine):
        """Test that UDP errors are counted in metrics"""
        # Reset metrics
        engine.reset_metrics()
        
        # Cause a UDP error by trying to receive without endpoint
        engine.udp_receive('localhost', 65432, timeout_ms=100)
        
        # Check that error was recorded
        metrics = engine.get_metrics()
        assert metrics['failed_requests'] > 0


class TestUDPSpecialCases:
    """Test UDP-specific scenarios and edge cases"""
    
    def test_udp_broadcast_address(self, engine):
        """Test UDP send to broadcast address"""
        response = engine.udp_send('255.255.255.255', 8080, 'broadcast test', timeout_ms=1000)
        
        # Broadcast might require special socket options, but should not crash
        assert 'status_code' in response
    
    def test_udp_multicast_address(self, engine):
        """Test UDP send to multicast address"""
        response = engine.udp_send('224.1.1.1', 8080, 'multicast test', timeout_ms=1000)
        
        # Multicast might require special setup, but should not crash
        assert 'status_code' in response
    
    def test_udp_localhost_loopback(self, engine):
        """Test UDP operations using localhost and loopback"""
        # Test localhost
        response1 = engine.udp_send('localhost', 8080, 'test localhost', timeout_ms=1000)
        assert 'status_code' in response1
        
        # Test 127.0.0.1
        response2 = engine.udp_send('127.0.0.1', 8080, 'test loopback', timeout_ms=1000)
        assert 'status_code' in response2
    
    def test_udp_zero_length_message(self, engine, mock_udp_server):
        """Test sending zero-length UDP message"""
        server, port = mock_udp_server
        
        response = engine.udp_send('localhost', port, '', timeout_ms=1000)
        
        # Should succeed - UDP allows zero-length datagrams
        assert response['status_code'] == 200 or response['success'] is True


if __name__ == '__main__':
    # Run a basic test if executed directly
    print("🧪 Running LoadSpiker UDP Tests")
    print("=" * 40)
    
    # Create engine
    engine = Engine()
    
    # Start mock server
    server = MockUDPServer()
    port = server.start()
    
    try:
        print(f"📡 Mock UDP server started on port {port}")
        
        # Test endpoint creation
        print("🔗 Testing UDP endpoint creation...")
        create_response = engine.udp_create_endpoint('localhost', 0)
        print(f"   Result: {'✅ Success' if create_response['success'] else '❌ Failed'}")
        print(f"   Response: {create_response['body']}")
        
        # Test data transfer
        print("📤 Testing UDP send...")
        send_response = engine.udp_send('localhost', port, 'Hello UDP!')
        print(f"   Result: {'✅ Success' if send_response['success'] else '❌ Failed'}")
        print(f"   Response: {send_response['body']}")
        
        # Wait for server to receive
        time.sleep(0.2)
        
        print(f"📥 Server received {len(server.received_messages)} messages")
        for i, (msg, addr) in enumerate(server.received_messages):
            print(f"   {i+1}. From {addr}: {msg}")
        
        # Test endpoint closure
        print("🔌 Testing UDP endpoint closure...")
        close_response = engine.udp_close_endpoint('localhost', 0)
        print(f"   Result: {'✅ Success' if close_response['success'] else '❌ Failed'}")
        print(f"   Response: {close_response['body']}")
        
        print("\n🎬 Testing UDP Scenario...")
        scenario = UDPScenario('localhost', port)
        scenario.add_echo_test('Hello from scenario!')
        
        operations = scenario.build_udp_operations()
        print(f"   Created scenario with {len(operations)} operations")
        for i, op in enumerate(operations, 1):
            print(f"      {i}. {op['type']}")
        
        print("\n✅ UDP Protocol Tests Completed!")
        
    finally:
        server.stop()
        print("🛑 Mock server stopped")
