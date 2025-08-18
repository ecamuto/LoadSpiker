#!/usr/bin/env python3

"""
LoadSpiker TCP Socket Protocol Tests
===================================

Comprehensive test suite for TCP socket functionality in LoadSpiker.
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
from loadspiker.scenarios import TCPScenario, MixedProtocolScenario


class MockTCPServer:
    """Mock TCP server for testing purposes"""
    
    def __init__(self, host='localhost', port=0):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.thread = None
        self.echo_mode = True
        self.responses = []
        
    def start(self):
        """Start the mock TCP server"""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.port = self.server_socket.getsockname()[1]  # Get actual port if 0 was used
        
        self.running = True
        self.thread = threading.Thread(target=self._run_server)
        self.thread.daemon = True
        self.thread.start()
        
        # Give server time to start
        time.sleep(0.1)
        
        return self.port
    
    def stop(self):
        """Stop the mock TCP server"""
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
                    args=(client_socket,)
                )
                client_thread.daemon = True
                client_thread.start()
            except OSError:
                break
    
    def _handle_client(self, client_socket):
        """Handle individual client connections"""
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    break
                
                if self.echo_mode:
                    # Echo the data back
                    client_socket.send(data)
                else:
                    # Send predefined responses
                    if self.responses:
                        response = self.responses.pop(0)
                        client_socket.send(response.encode('utf-8'))
        except OSError:
            pass
        finally:
            client_socket.close()


@pytest.fixture
def mock_tcp_server():
    """Fixture to provide a mock TCP server"""
    server = MockTCPServer()
    port = server.start()
    yield server, port
    server.stop()


@pytest.fixture
def engine():
    """Fixture to provide a LoadSpiker engine"""
    return Engine(max_connections=10, worker_threads=2)


class TestTCPBasicOperations:
    """Test basic TCP operations"""
    
    def test_tcp_connect_success(self, engine, mock_tcp_server):
        """Test successful TCP connection"""
        server, port = mock_tcp_server
        
        response = engine.tcp_connect('localhost', port, timeout_ms=5000)
        
        assert response['success'] is True
        assert response['status_code'] == 200
        assert 'TCP connection established' in response['body']
        assert response['response_time_ms'] >= 0
        assert response['response_time_us'] >= 0
    
    def test_tcp_connect_failure(self, engine):
        """Test TCP connection failure to non-existent server"""
        # Use a port that's unlikely to be open
        response = engine.tcp_connect('localhost', 65432, timeout_ms=1000)
        
        assert response['success'] is False
        assert response['status_code'] != 200
        assert 'failed' in response['error_message'].lower()
    
    def test_tcp_send_without_connection(self, engine):
        """Test TCP send without establishing connection first"""
        response = engine.tcp_send('localhost', 65432, 'test data', timeout_ms=1000)
        
        assert response['success'] is False
        assert 'no active tcp connection' in response['error_message'].lower()
    
    def test_tcp_receive_without_connection(self, engine):
        """Test TCP receive without establishing connection first"""
        response = engine.tcp_receive('localhost', 65432, timeout_ms=1000)
        
        assert response['success'] is False
        assert 'no active tcp connection' in response['error_message'].lower()
    
    def test_tcp_disconnect_without_connection(self, engine):
        """Test TCP disconnect without establishing connection first"""
        response = engine.tcp_disconnect('localhost', 65432)
        
        assert response['success'] is False
        assert 'no active tcp connection' in response['error_message'].lower()


class TestTCPDataTransfer:
    """Test TCP data transfer operations"""
    
    def test_tcp_echo_communication(self, engine, mock_tcp_server):
        """Test complete TCP echo communication"""
        server, port = mock_tcp_server
        test_message = "Hello, TCP World!"
        
        # Connect
        connect_response = engine.tcp_connect('localhost', port, timeout_ms=5000)
        assert connect_response['success'] is True
        
        # Send data
        send_response = engine.tcp_send('localhost', port, test_message, timeout_ms=5000)
        assert send_response['success'] is True
        assert 'bytes' in send_response['body']
        
        # Receive echo
        receive_response = engine.tcp_receive('localhost', port, timeout_ms=5000)
        assert receive_response['success'] is True
        if 'protocol_data' in receive_response:
            assert test_message in receive_response['protocol_data'].get('received_data', '')
        
        # Disconnect
        disconnect_response = engine.tcp_disconnect('localhost', port)
        assert disconnect_response['success'] is True
    
    def test_tcp_multiple_messages(self, engine, mock_tcp_server):
        """Test sending multiple messages over the same connection"""
        server, port = mock_tcp_server
        messages = ["Message 1", "Message 2", "Message 3"]
        
        # Connect once
        connect_response = engine.tcp_connect('localhost', port, timeout_ms=5000)
        assert connect_response['success'] is True
        
        # Send multiple messages
        for message in messages:
            send_response = engine.tcp_send('localhost', port, message, timeout_ms=5000)
            assert send_response['success'] is True
            
            receive_response = engine.tcp_receive('localhost', port, timeout_ms=5000)
            assert receive_response['success'] is True
        
        # Disconnect
        disconnect_response = engine.tcp_disconnect('localhost', port)
        assert disconnect_response['success'] is True
    
    def test_tcp_large_data_transfer(self, engine, mock_tcp_server):
        """Test transferring larger amounts of data"""
        server, port = mock_tcp_server
        large_message = "A" * 1000  # 1KB message
        
        # Connect
        connect_response = engine.tcp_connect('localhost', port, timeout_ms=5000)
        assert connect_response['success'] is True
        
        # Send large data
        send_response = engine.tcp_send('localhost', port, large_message, timeout_ms=5000)
        assert send_response['success'] is True
        
        # Receive echo
        receive_response = engine.tcp_receive('localhost', port, timeout_ms=5000)
        assert receive_response['success'] is True
        
        # Disconnect
        disconnect_response = engine.tcp_disconnect('localhost', port)
        assert disconnect_response['success'] is True


class TestTCPScenarios:
    """Test TCP scenario classes"""
    
    def test_tcp_scenario_creation(self):
        """Test TCP scenario creation and configuration"""
        scenario = TCPScenario('localhost', 8080, 'Test TCP Scenario')
        
        assert scenario.hostname == 'localhost'
        assert scenario.port == 8080
        assert scenario.name == 'Test TCP Scenario'
        assert len(scenario.tcp_operations) == 0
    
    def test_tcp_scenario_operations(self):
        """Test adding operations to TCP scenario"""
        scenario = TCPScenario('localhost', 8080)
        
        # Add individual operations
        scenario.add_connect(timeout_ms=5000)
        scenario.add_send('Hello', timeout_ms=3000)
        scenario.add_receive(timeout_ms=3000)
        scenario.add_disconnect()
        
        operations = scenario.build_tcp_operations()
        
        assert len(operations) == 4
        assert operations[0]['type'] == 'tcp_connect'
        assert operations[0]['hostname'] == 'localhost'
        assert operations[0]['port'] == 8080
        assert operations[0]['timeout_ms'] == 5000
        
        assert operations[1]['type'] == 'tcp_send'
        assert operations[1]['data'] == 'Hello'
        assert operations[1]['timeout_ms'] == 3000
        
        assert operations[2]['type'] == 'tcp_receive'
        assert operations[2]['timeout_ms'] == 3000
        
        assert operations[3]['type'] == 'tcp_disconnect'
    
    def test_tcp_scenario_echo_test(self):
        """Test TCP scenario echo test helper"""
        scenario = TCPScenario('localhost', 8080)
        scenario.add_echo_test('Test Message', timeout_ms=2000)
        
        operations = scenario.build_tcp_operations()
        
        assert len(operations) == 4
        assert operations[0]['type'] == 'tcp_connect'
        assert operations[1]['type'] == 'tcp_send'
        assert operations[1]['data'] == 'Test Message'
        assert operations[2]['type'] == 'tcp_receive'
        assert operations[3]['type'] == 'tcp_disconnect'
    
    def test_tcp_scenario_with_data_substitution(self):
        """Test TCP scenario with variable substitution"""
        scenario = TCPScenario('${host}', 8080)
        scenario.set_variable('host', 'example.com')
        scenario.add_send('Hello ${name}!')
        scenario.set_variable('name', 'World')
        
        operations = scenario.build_tcp_operations()
        
        assert operations[0]['hostname'] == 'example.com'
        assert operations[0]['data'] == 'Hello World!'


class TestTCPErrorHandling:
    """Test TCP error handling scenarios"""
    
    def test_tcp_connection_timeout(self, engine):
        """Test TCP connection timeout"""
        # Use a non-routable IP to force timeout
        response = engine.tcp_connect('192.0.2.1', 80, timeout_ms=100)
        
        assert response['success'] is False
        assert 'timeout' in response['error_message'].lower() or 'failed' in response['error_message'].lower()
    
    def test_tcp_invalid_hostname(self, engine):
        """Test TCP connection to invalid hostname"""
        response = engine.tcp_connect('invalid.nonexistent.domain', 80, timeout_ms=1000)
        
        assert response['success'] is False
        assert response['error_message'] != ''
    
    def test_tcp_invalid_port(self, engine):
        """Test TCP connection to invalid port"""
        response = engine.tcp_connect('localhost', 99999, timeout_ms=1000)
        
        assert response['success'] is False
        assert response['error_message'] != ''


class TestTCPMixedProtocolScenarios:
    """Test TCP in mixed protocol scenarios"""
    
    def test_mixed_protocol_with_tcp(self, mock_tcp_server):
        """Test TCP operations in mixed protocol scenarios"""
        server, port = mock_tcp_server
        
        scenario = MixedProtocolScenario('TCP and HTTP Test')
        
        # Add HTTP request
        scenario.add_http_request('https://httpbin.org/get', 'GET')
        
        # Add TCP operations (placeholder - would need actual TCP support in MixedProtocolScenario)
        # This test demonstrates the intended integration pattern
        
        operations = scenario.build_mixed_operations()
        
        assert len(operations) >= 1
        assert operations[0]['type'] == 'http'


class TestTCPPerformanceMetrics:
    """Test TCP performance metrics"""
    
    def test_tcp_response_time_metrics(self, engine, mock_tcp_server):
        """Test that TCP operations generate response time metrics"""
        server, port = mock_tcp_server
        
        # Reset metrics
        engine.reset_metrics()
        
        # Perform TCP operations
        engine.tcp_connect('localhost', port, timeout_ms=5000)
        engine.tcp_send('localhost', port, 'test', timeout_ms=5000)
        engine.tcp_receive('localhost', port, timeout_ms=5000)
        engine.tcp_disconnect('localhost', port)
        
        # Check metrics
        metrics = engine.get_metrics()
        
        # Should have recorded some requests
        assert metrics['total_requests'] > 0
        
        # Should have response times
        if metrics['total_requests'] > 0:
            assert metrics.get('min_response_time_ms', 0) >= 0
            assert metrics.get('max_response_time_ms', 0) >= 0
    
    def test_tcp_error_metrics(self, engine):
        """Test that TCP errors are counted in metrics"""
        # Reset metrics
        engine.reset_metrics()
        
        # Cause a TCP error
        engine.tcp_connect('invalid.host', 80, timeout_ms=100)
        
        # Check that error was recorded
        metrics = engine.get_metrics()
        assert metrics['failed_requests'] > 0


if __name__ == '__main__':
    # Run a basic test if executed directly
    print("🧪 Running LoadSpiker TCP Tests")
    print("=" * 40)
    
    # Create engine
    engine = Engine()
    
    # Start mock server
    server = MockTCPServer()
    port = server.start()
    
    try:
        print(f"📡 Mock TCP server started on port {port}")
        
        # Test basic connection
        print("🔗 Testing TCP connection...")
        connect_response = engine.tcp_connect('localhost', port)
        print(f"   Result: {'✅ Success' if connect_response['success'] else '❌ Failed'}")
        print(f"   Response: {connect_response['body']}")
        
        if connect_response['success']:
            # Test data transfer
            print("📤 Testing TCP send...")
            send_response = engine.tcp_send('localhost', port, 'Hello TCP!')
            print(f"   Result: {'✅ Success' if send_response['success'] else '❌ Failed'}")
            print(f"   Response: {send_response['body']}")
            
            print("📥 Testing TCP receive...")
            receive_response = engine.tcp_receive('localhost', port)
            print(f"   Result: {'✅ Success' if receive_response['success'] else '❌ Failed'}")
            print(f"   Response: {receive_response['body']}")
            
            # Test disconnect
            print("🔌 Testing TCP disconnect...")
            disconnect_response = engine.tcp_disconnect('localhost', port)
            print(f"   Result: {'✅ Success' if disconnect_response['success'] else '❌ Failed'}")
            print(f"   Response: {disconnect_response['body']}")
        
        print("\n🎬 Testing TCP Scenario...")
        scenario = TCPScenario('localhost', port)
        scenario.add_echo_test('Hello from scenario!')
        
        operations = scenario.build_tcp_operations()
        print(f"   Created scenario with {len(operations)} operations")
        for i, op in enumerate(operations, 1):
            print(f"      {i}. {op['type']}")
        
        print("\n✅ TCP Protocol Tests Completed!")
        
    finally:
        server.stop()
        print("🛑 Mock server stopped")
