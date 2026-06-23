#!/usr/bin/env python3
"""
Load-execution tests for non-HTTP scenarios.

Verifies that scenarios built from TCP/UDP/MQTT/Database/Mixed operations are
actually executed under concurrent load by Engine.run_scenario (previously the
load path only ran HTTP requests, so these operations were never executed) and
that metrics accumulate.
"""

import os
import socket
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loadspiker import Engine
from loadspiker.scenarios import (
    Scenario,
    TCPScenario,
    UDPScenario,
    MixedProtocolScenario,
)


# ---------------------------------------------------------------------------
# Normalization / routing
# ---------------------------------------------------------------------------
class TestLoadOperationInterface:
    def test_http_scenario_is_http_only(self):
        sc = Scenario("http")
        sc.get("https://example.com/")
        assert sc.is_http_only() is True
        ops = sc.get_load_operations()
        assert len(ops) == 1
        assert ops[0]["type"] == "http"
        assert ops[0]["url"] == "https://example.com/"

    def test_tcp_scenario_not_http_only(self):
        sc = TCPScenario("localhost", 9999)
        sc.add_echo_test("ping")
        assert sc.is_http_only() is False
        ops = sc.get_load_operations()
        assert [o["type"] for o in ops] == [
            "tcp_connect", "tcp_send", "tcp_receive", "tcp_disconnect",
        ]

    def test_mixed_scenario_not_http_only(self):
        sc = MixedProtocolScenario("mixed")
        sc.add_http_request("https://example.com/", "GET")
        sc.add_database_operation("mysql://u:p@localhost/db", "connect")
        assert sc.is_http_only() is False


# ---------------------------------------------------------------------------
# Actual concurrent execution
# ---------------------------------------------------------------------------
class _Echo:
    """Minimal localhost TCP echo server for the duration of a test."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("localhost", 0))
        self.sock.listen(16)
        self.port = self.sock.getsockname()[1]
        self.running = True
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while self.running:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn):
        try:
            while True:
                data = conn.recv(1024)
                if not data:
                    break
                conn.send(data)
        except OSError:
            pass
        finally:
            conn.close()

    def stop(self):
        self.running = False
        self.sock.close()


@pytest.fixture
def echo_server():
    srv = _Echo()
    time.sleep(0.1)
    yield srv
    srv.stop()


def test_tcp_scenario_runs_under_load(echo_server):
    """A TCP scenario must accumulate metrics when run via run_scenario."""
    engine = Engine(max_connections=20, worker_threads=4)
    engine.reset_metrics()

    sc = TCPScenario("localhost", echo_server.port, "tcp load")
    sc.add_echo_test("ping")

    metrics = engine.run_scenario(sc, users=2, duration=1)

    assert metrics["total_requests"] > 0
    assert metrics["successful_requests"] > 0


def test_mixed_scenario_runs_under_load():
    """Mixed websocket/database (simulated) operations execute under load."""
    engine = Engine(max_connections=10, worker_threads=2)
    engine.reset_metrics()

    sc = MixedProtocolScenario("mixed")
    sc.add_database_operation("mysql://u:p@localhost/db", "connect")
    sc.add_database_operation("mysql://u:p@localhost/db", "query", "SELECT 1")
    sc.add_database_operation("mysql://u:p@localhost/db", "disconnect")

    metrics = engine.run_scenario(sc, users=2, duration=1)

    assert metrics["total_requests"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
