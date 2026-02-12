#!/usr/bin/env python3
"""
LoadSpiker Test Configuration and Shared Fixtures
==================================================

Provides shared pytest fixtures for all test modules.
"""

import sys
import os
import pytest
import threading
import time
import socket

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine


# ---------------------------------------------------------------------------
# Engine fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """Provide a fresh LoadSpiker engine with default settings."""
    eng = Engine(max_connections=10, worker_threads=2)
    yield eng
    del eng


@pytest.fixture
def engine_large():
    """Provide a LoadSpiker engine with larger capacity for stress tests."""
    eng = Engine(max_connections=50, worker_threads=4)
    yield eng
    del eng


# ---------------------------------------------------------------------------
# Mock TCP Server
# ---------------------------------------------------------------------------

class MockTCPServer:
    """Reusable mock TCP echo server for testing."""

    def __init__(self, host='localhost', port=0):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.thread = None

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.port = self.server_socket.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        time.sleep(0.1)
        return self.port

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.thread:
            self.thread.join(timeout=1)

    def _run(self):
        while self.running:
            try:
                client, _ = self.server_socket.accept()
                threading.Thread(target=self._handle, args=(client,), daemon=True).start()
            except OSError:
                break

    def _handle(self, client):
        try:
            while self.running:
                data = client.recv(4096)
                if not data:
                    break
                client.sendall(data)
        except OSError:
            pass
        finally:
            client.close()


@pytest.fixture
def mock_tcp_server():
    """Fixture providing a mock TCP echo server."""
    server = MockTCPServer()
    server.start()
    yield server, server.port
    server.stop()


# ---------------------------------------------------------------------------
# Mock UDP Server
# ---------------------------------------------------------------------------

class MockUDPServer:
    """Reusable mock UDP echo server for testing."""

    def __init__(self, host='localhost', port=0):
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.thread = None
        self.received_messages = []

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.bind((self.host, self.port))
        self.port = self.server_socket.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        time.sleep(0.1)
        return self.port

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        if self.thread:
            self.thread.join(timeout=1)

    def _run(self):
        self.server_socket.settimeout(0.1)
        while self.running:
            try:
                data, addr = self.server_socket.recvfrom(4096)
                self.received_messages.append((data.decode('utf-8', errors='replace'), addr))
                self.server_socket.sendto(data, addr)
            except socket.timeout:
                continue
            except OSError:
                break


@pytest.fixture
def mock_udp_server():
    """Fixture providing a mock UDP echo server."""
    server = MockUDPServer()
    server.start()
    yield server, server.port
    server.stop()