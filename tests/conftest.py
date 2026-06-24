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
import base64
import hashlib
import struct

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine


# ---------------------------------------------------------------------------
# Test isolation
# ---------------------------------------------------------------------------
# The C engine's TCP/UDP/MQTT/Database/WebSocket connection pools are
# process-global static state, not per-engine. Without a reset, slots leak
# across tests: when the OS recycles an ephemeral port, a later test can match
# a stale slot still flagged is_connected with a now-closed fd, so connect()
# reports "already established" on a dead socket and the following send/receive
# fails intermittently. Reset the pools before every test so each starts clean.

@pytest.fixture(scope="session")
def _pool_resetter():
    return Engine(max_connections=1, worker_threads=1)


@pytest.fixture(autouse=True)
def _reset_protocol_pools(_pool_resetter):
    _pool_resetter.reset_connection_pools()
    yield


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


# ---------------------------------------------------------------------------
# Mock WebSocket Server (real RFC 6455 handshake + echo)
# ---------------------------------------------------------------------------

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class MockWebSocketServer:
    """Minimal RFC 6455 WebSocket echo server for testing the real WS path."""

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
            # --- HTTP Upgrade handshake ---
            request = b""
            while b"\r\n\r\n" not in request:
                chunk = client.recv(1024)
                if not chunk:
                    return
                request += chunk
            key = None
            for line in request.decode('latin-1').split("\r\n"):
                if line.lower().startswith("sec-websocket-key:"):
                    key = line.split(":", 1)[1].strip()
            if not key:
                client.close()
                return
            accept = base64.b64encode(
                hashlib.sha1((key + _WS_GUID).encode()).digest()
            ).decode()
            client.sendall(
                ("HTTP/1.1 101 Switching Protocols\r\n"
                 "Upgrade: websocket\r\n"
                 "Connection: Upgrade\r\n"
                 f"Sec-WebSocket-Accept: {accept}\r\n\r\n").encode()
            )
            # --- Echo frames back ---
            while self.running:
                frame = self._recv_frame(client)
                if frame is None:
                    break
                opcode, payload = frame
                if opcode == 0x8:  # close
                    client.sendall(self._build_frame(b"", opcode=0x8))
                    break
                # echo as text
                client.sendall(self._build_frame(payload, opcode=0x1))
        except OSError:
            pass
        finally:
            client.close()

    def _recv_exact(self, client, n):
        buf = b""
        while len(buf) < n:
            chunk = client.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def _recv_frame(self, client):
        hdr = self._recv_exact(client, 2)
        if not hdr:
            return None
        opcode = hdr[0] & 0x0F
        masked = hdr[1] & 0x80
        length = hdr[1] & 0x7F
        if length == 126:
            ext = self._recv_exact(client, 2)
            length = struct.unpack(">H", ext)[0]
        elif length == 127:
            ext = self._recv_exact(client, 8)
            length = struct.unpack(">Q", ext)[0]
        mask = self._recv_exact(client, 4) if masked else b"\x00\x00\x00\x00"
        payload = self._recv_exact(client, length) if length else b""
        if payload is None:
            return None
        if masked:
            payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
        return opcode, payload

    def _build_frame(self, payload, opcode=0x1):
        # Server-to-client frames are unmasked
        header = bytes([0x80 | opcode])
        n = len(payload)
        if n < 126:
            header += bytes([n])
        elif n < 65536:
            header += bytes([126]) + struct.pack(">H", n)
        else:
            header += bytes([127]) + struct.pack(">Q", n)
        return header + payload


@pytest.fixture
def mock_websocket_server():
    """Fixture providing a real RFC 6455 WebSocket echo server."""
    server = MockWebSocketServer()
    server.start()
    yield server, server.port
    server.stop()