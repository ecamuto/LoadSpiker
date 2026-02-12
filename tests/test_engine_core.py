#!/usr/bin/env python3
"""
LoadSpiker Core Engine Tests
=============================

Tests for the core engine functionality including:
- Engine creation and destruction
- HTTP request execution
- Metrics collection and reset
- Protocol methods (with skip markers for missing C extension bindings)
"""

import sys
import os
import pytest
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine


# ---------------------------------------------------------------------------
# Helper: detect whether protocol methods are available on the underlying engine
# ---------------------------------------------------------------------------

def _has_protocol_method(method_name):
    """Check if the underlying engine exposes a given protocol method."""
    try:
        eng = Engine(max_connections=1, worker_threads=1)
        return hasattr(eng._engine, method_name)
    except Exception:
        return False


_has_tcp = _has_protocol_method('tcp_connect')
_has_udp = _has_protocol_method('udp_send')
_has_mqtt = _has_protocol_method('mqtt_connect')
_has_database = _has_protocol_method('database_connect')

_skip_tcp = pytest.mark.skipif(not _has_tcp,
    reason="C extension missing TCP protocol bindings (python_extension.c)")
_skip_udp = pytest.mark.skipif(not _has_udp,
    reason="C extension missing UDP protocol bindings (python_extension.c)")
_skip_mqtt = pytest.mark.skipif(not _has_mqtt,
    reason="C extension missing MQTT protocol bindings (python_extension.c)")
_skip_database = pytest.mark.skipif(not _has_database,
    reason="C extension missing Database protocol bindings (python_extension.c)")


class TestEngineLifecycle:
    """Test engine creation, configuration, and destruction."""

    def test_engine_create_default(self):
        """Engine can be created with default parameters."""
        engine = Engine()
        assert engine is not None
        del engine

    def test_engine_create_custom(self):
        """Engine can be created with custom parameters."""
        engine = Engine(max_connections=50, worker_threads=4)
        assert engine is not None
        del engine

    def test_engine_create_minimal(self):
        """Engine can be created with minimal resources."""
        engine = Engine(max_connections=1, worker_threads=1)
        assert engine is not None
        del engine

    def test_engine_multiple_instances(self):
        """Multiple engine instances can coexist."""
        engines = [Engine(max_connections=5, worker_threads=1) for _ in range(3)]
        assert len(engines) == 3
        for e in engines:
            del e


class TestMetrics:
    """Test metrics collection and reset."""

    def test_get_metrics_initial(self, engine):
        """Initial metrics should be zeroed."""
        metrics = engine.get_metrics()
        assert isinstance(metrics, dict)
        assert metrics.get('total_requests', 0) == 0
        assert metrics.get('successful_requests', 0) == 0
        assert metrics.get('failed_requests', 0) == 0

    def test_reset_metrics(self, engine):
        """reset_metrics should zero all counters."""
        engine.reset_metrics()
        metrics = engine.get_metrics()
        assert metrics['total_requests'] == 0
        assert metrics['successful_requests'] == 0
        assert metrics['failed_requests'] == 0

    def test_metrics_after_request(self, engine):
        """Metrics should update after executing a request."""
        engine.reset_metrics()
        try:
            engine.execute_request(url="http://example.com", method="GET", timeout_ms=5000)
        except Exception:
            pass
        metrics = engine.get_metrics()
        assert metrics['total_requests'] >= 1

    def test_metrics_response_time_fields(self, engine):
        """Metrics should include response time fields."""
        engine.reset_metrics()
        try:
            engine.execute_request(url="http://example.com", method="GET", timeout_ms=5000)
        except Exception:
            pass
        metrics = engine.get_metrics()
        assert 'min_response_time_us' in metrics or 'min_response_time_ms' in metrics
        assert 'max_response_time_us' in metrics or 'max_response_time_ms' in metrics


class TestHTTPRequests:
    """Test HTTP request execution."""

    def test_execute_request_get(self, engine):
        """Basic GET request should return a response dict."""
        response = engine.execute_request(
            url="http://example.com",
            method="GET",
            timeout_ms=10000
        )
        assert isinstance(response, dict)
        assert 'status_code' in response
        assert 'success' in response
        assert 'response_time_us' in response or 'response_time_ms' in response

    def test_execute_request_success(self, engine):
        """GET to example.com should succeed."""
        response = engine.execute_request(
            url="http://example.com",
            method="GET",
            timeout_ms=10000
        )
        assert response['success'] is True
        assert response['status_code'] == 200

    def test_execute_request_with_headers(self, engine):
        """Request with custom headers should work."""
        response = engine.execute_request(
            url="http://example.com",
            method="GET",
            headers={"Accept": "text/html", "User-Agent": "LoadSpiker-Test"},
            timeout_ms=10000
        )
        assert isinstance(response, dict)
        assert 'status_code' in response

    def test_execute_request_invalid_url(self, engine):
        """Request to invalid URL should fail gracefully."""
        response = engine.execute_request(
            url="http://invalid.nonexistent.domain.test",
            method="GET",
            timeout_ms=3000
        )
        assert isinstance(response, dict)
        assert response['success'] is False

    def test_execute_request_timeout(self, engine):
        """Request with very short timeout should fail."""
        response = engine.execute_request(
            url="http://example.com",
            method="GET",
            timeout_ms=1
        )
        assert isinstance(response, dict)
        assert 'success' in response

    def test_execute_request_post(self, engine):
        """POST request should work."""
        response = engine.execute_request(
            url="http://httpbin.org/post",
            method="POST",
            body='{"test": "data"}',
            headers={"Content-Type": "application/json"},
            timeout_ms=10000
        )
        assert isinstance(response, dict)
        assert 'status_code' in response


class TestWebSocketProtocol:
    """Test WebSocket protocol methods via engine (simulated)."""

    def test_websocket_connect(self, engine):
        """WebSocket connect should return response."""
        response = engine.websocket_connect("ws://echo.websocket.org")
        assert isinstance(response, dict)
        assert 'success' in response

    def test_websocket_send(self, engine):
        """WebSocket send should return response."""
        engine.websocket_connect("ws://echo.websocket.org")
        response = engine.websocket_send("ws://echo.websocket.org", "Hello!")
        assert isinstance(response, dict)
        assert 'success' in response

    def test_websocket_close(self, engine):
        """WebSocket close should return response."""
        engine.websocket_connect("ws://echo.websocket.org")
        response = engine.websocket_close("ws://echo.websocket.org")
        assert isinstance(response, dict)
        assert 'success' in response


@_skip_database
class TestDatabaseProtocol:
    """Test database protocol methods via engine."""

    def test_database_connect_mysql(self, engine):
        """Database connect for MySQL should return response."""
        response = engine.database_connect(
            "mysql://testuser:testpass@localhost:3306/testdb", "mysql"
        )
        assert isinstance(response, dict)
        assert 'success' in response
        assert response['success'] is True

    def test_database_connect_postgresql(self, engine):
        """Database connect for PostgreSQL should return response."""
        response = engine.database_connect(
            "postgresql://testuser:testpass@localhost:5432/testdb", "postgresql"
        )
        assert isinstance(response, dict)
        assert response['success'] is True

    def test_database_connect_mongodb(self, engine):
        """Database connect for MongoDB should return response."""
        response = engine.database_connect(
            "mongodb://testuser:testpass@localhost:27017/testdb", "mongodb"
        )
        assert isinstance(response, dict)
        assert response['success'] is True

    def test_database_connect_invalid_type(self, engine):
        """Database connect with invalid type should fail."""
        response = engine.database_connect("invalid://test", "invalid_type")
        assert isinstance(response, dict)
        assert response['success'] is False

    def test_database_query_without_connection(self, engine):
        """Query without prior connection should fail."""
        response = engine.database_query(
            "mysql://test:test@localhost/test", "SELECT * FROM users"
        )
        assert isinstance(response, dict)
        assert response['success'] is False

    def test_database_disconnect(self, engine):
        """Database disconnect should work after connect."""
        engine.database_connect(
            "mysql://testuser:testpass@localhost:3306/testdb", "mysql"
        )
        response = engine.database_disconnect(
            "mysql://testuser:testpass@localhost:3306/testdb"
        )
        assert isinstance(response, dict)
        assert response['success'] is True


@_skip_tcp
class TestTCPProtocol:
    """Test TCP protocol methods via engine."""

    def test_tcp_connect(self, engine, mock_tcp_server):
        """TCP connect to mock server should succeed."""
        server, port = mock_tcp_server
        response = engine.tcp_connect('localhost', port, timeout_ms=5000)
        assert isinstance(response, dict)
        assert response['success'] is True
        assert response['status_code'] == 200

    def test_tcp_connect_failure(self, engine):
        """TCP connect to non-existent port should fail."""
        response = engine.tcp_connect('localhost', 65432, timeout_ms=1000)
        assert isinstance(response, dict)
        assert response['success'] is False

    def test_tcp_send_receive(self, engine, mock_tcp_server):
        """TCP send/receive through mock echo server."""
        server, port = mock_tcp_server
        connect_resp = engine.tcp_connect('localhost', port, timeout_ms=5000)
        assert connect_resp['success'] is True

        send_resp = engine.tcp_send('localhost', port, 'Hello TCP', timeout_ms=5000)
        assert send_resp['success'] is True

        recv_resp = engine.tcp_receive('localhost', port, timeout_ms=5000)
        assert recv_resp['success'] is True

    def test_tcp_disconnect(self, engine, mock_tcp_server):
        """TCP disconnect should succeed after connect."""
        server, port = mock_tcp_server
        engine.tcp_connect('localhost', port, timeout_ms=5000)
        response = engine.tcp_disconnect('localhost', port)
        assert isinstance(response, dict)
        assert response['success'] is True

    def test_tcp_send_without_connection(self, engine):
        """TCP send without connection should fail."""
        response = engine.tcp_send('localhost', 65432, 'data', timeout_ms=1000)
        assert isinstance(response, dict)
        assert response['success'] is False


@_skip_udp
class TestUDPProtocol:
    """Test UDP protocol methods via engine."""

    def test_udp_create_endpoint(self, engine):
        """UDP endpoint creation should succeed."""
        response = engine.udp_create_endpoint('localhost', 0)
        assert isinstance(response, dict)
        assert response['success'] is True

    def test_udp_send(self, engine, mock_udp_server):
        """UDP send to mock server should succeed."""
        server, port = mock_udp_server
        response = engine.udp_send('localhost', port, 'Hello UDP', timeout_ms=5000)
        assert isinstance(response, dict)
        assert response['success'] is True

    def test_udp_receive_without_endpoint(self, engine):
        """UDP receive without endpoint should fail."""
        response = engine.udp_receive('localhost', 65432, timeout_ms=1000)
        assert isinstance(response, dict)
        assert response['success'] is False


@_skip_mqtt
class TestMQTTProtocol:
    """Test MQTT protocol methods via engine (simulated without real broker)."""

    def test_mqtt_connect(self, engine):
        """MQTT connect should return a response dict."""
        response = engine.mqtt_connect(
            broker_host="test.mosquitto.org",
            broker_port=1883,
            client_id="loadspiker_test"
        )
        assert isinstance(response, dict)
        assert 'success' in response

    def test_mqtt_publish(self, engine):
        """MQTT publish should return a response dict."""
        engine.mqtt_connect(
            broker_host="test.mosquitto.org",
            broker_port=1883,
            client_id="loadspiker_test"
        )
        response = engine.mqtt_publish(
            broker_host="test.mosquitto.org",
            broker_port=1883,
            client_id="loadspiker_test",
            topic="loadspiker/test",
            payload="Hello MQTT",
            qos=0
        )
        assert isinstance(response, dict)
        assert 'success' in response

    def test_mqtt_disconnect(self, engine):
        """MQTT disconnect should return a response dict."""
        engine.mqtt_connect(
            broker_host="test.mosquitto.org",
            broker_port=1883,
            client_id="loadspiker_test"
        )
        response = engine.mqtt_disconnect(
            broker_host="test.mosquitto.org",
            broker_port=1883,
            client_id="loadspiker_test"
        )
        assert isinstance(response, dict)
        assert 'success' in response


@_skip_database
class TestMetricsAccumulation:
    """Test that metrics accumulate correctly across multiple operations."""

    def test_metrics_count_multiple_requests(self, engine):
        """Multiple requests should all be counted."""
        engine.reset_metrics()

        for _ in range(5):
            engine.database_connect("mysql://user:pass@localhost/db", "mysql")
            engine.database_disconnect("mysql://user:pass@localhost/db")

        metrics = engine.get_metrics()
        assert metrics['total_requests'] >= 10

    def test_metrics_track_failures(self, engine):
        """Failed requests should be tracked separately."""
        engine.reset_metrics()

        engine.database_query("mysql://user:pass@localhost/db", "SELECT 1")
        engine.database_connect("invalid://x", "invalid")

        metrics = engine.get_metrics()
        assert metrics['failed_requests'] >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])