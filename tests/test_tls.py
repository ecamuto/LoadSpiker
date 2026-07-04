#!/usr/bin/env python3
"""
TLS transport tests (TCP + MQTT over TLS)
=========================================

Hermetic: a self-signed certificate is generated per session (via the openssl
CLI) and local ssl-wrapped servers stand in for real endpoints. Skips cleanly
when the C extension lacks OpenSSL support or the openssl CLI is unavailable.
"""

import os
import shutil
import socket
import ssl
import subprocess
import sys
import threading

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine
from loadspiker.engine import _c_extension_available

pytestmark = pytest.mark.skipif(
    not _c_extension_available, reason="C extension required for TLS transport tests"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tls_cert(tmp_path_factory):
    """Self-signed localhost certificate (cert_path, key_path)."""
    if not shutil.which("openssl"):
        pytest.skip("openssl CLI not available to generate a test certificate")
    d = tmp_path_factory.mktemp("tls")
    cert, key = str(d / "cert.pem"), str(d / "key.pem")
    subprocess.run(
        ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
         "-keyout", key, "-out", cert, "-days", "2",
         "-subj", "/CN=localhost",
         "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"],
        check=True, capture_output=True,
    )
    return cert, key


def _server_context(tls_cert):
    cert, key = tls_cert
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert, key)
    return ctx


class _TLSServer:
    """Tiny threaded TLS server; `handler(conn)` runs per connection."""

    def __init__(self, tls_cert, handler):
        self.ctx = _server_context(tls_cert)
        self.handler = handler
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('localhost', 0))
        self.sock.listen(5)
        self.port = self.sock.getsockname()[1]
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.running:
            try:
                client, _ = self.sock.accept()
            except OSError:
                break
            try:
                conn = self.ctx.wrap_socket(client, server_side=True)
            except (ssl.SSLError, OSError):
                client.close()
                continue  # e.g. the plain-TCP or verify-failure probes
            threading.Thread(target=self._serve, args=(conn,), daemon=True).start()

    def _serve(self, conn):
        try:
            self.handler(conn)
        except (ssl.SSLError, OSError):
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self):
        self.running = False
        try:
            self.sock.close()
        except OSError:
            pass


@pytest.fixture
def tls_echo_server(tls_cert):
    """TLS server echoing every received chunk back."""
    def echo(conn):
        conn.settimeout(10)
        while True:
            data = conn.recv(4096)
            if not data:
                return
            conn.sendall(data)

    server = _TLSServer(tls_cert, echo)
    yield 'localhost', server.port
    server.stop()


@pytest.fixture
def tls_mqtt_broker(tls_cert):
    """Minimal MQTT 3.1.1 broker over TLS: answers CONNECT with a success
    CONNACK, SUBSCRIBE with SUBACK, consumes everything else."""
    def broker(conn):
        conn.settimeout(10)
        buf = b''
        connected = False
        while True:
            data = conn.recv(4096)
            if not data:
                return
            buf += data
            # Serve complete packets from the front of the buffer.
            while len(buf) >= 2:
                ptype = buf[0] & 0xF0
                # Single-byte remaining length is enough for our test packets
                rl = buf[1]
                if rl > 127 and len(buf) >= 3:
                    rl = (buf[1] & 0x7F) + 128 * buf[2]
                    header = 3
                else:
                    header = 2
                if len(buf) < header + rl:
                    break
                packet, buf = buf[:header + rl], buf[header + rl:]
                if ptype == 0x10 and not connected:      # CONNECT
                    conn.sendall(b'\x20\x02\x00\x00')    # CONNACK success
                    connected = True
                elif ptype == 0x80:                      # SUBSCRIBE
                    pid = packet[header:header + 2]
                    conn.sendall(b'\x90\x03' + pid + b'\x00')  # SUBACK QoS0
                elif ptype == 0xE0:                      # DISCONNECT
                    return
                # PUBLISH (0x30) QoS0 needs no reply

    server = _TLSServer(tls_cert, broker)
    yield 'localhost', server.port
    server.stop()


# ---------------------------------------------------------------------------
# TCP over TLS
# ---------------------------------------------------------------------------

class TestTCPOverTLS:
    def test_tls_connect(self, engine, tls_echo_server):
        host, port = tls_echo_server
        resp = engine.tcp_connect(host, port, use_tls=True, tls_verify=False)
        assert resp['success'] is True, resp['error_message']
        assert 'TLS connection established' in resp['body']
        engine.tcp_disconnect(host, port)

    def test_tls_send_receive_roundtrip(self, engine, tls_echo_server):
        host, port = tls_echo_server
        resp = engine.tcp_connect(host, port, use_tls=True, tls_verify=False)
        assert resp['success'] is True, resp['error_message']

        sent = engine.tcp_send(host, port, "hello over TLS")
        assert sent['success'] is True, sent['error_message']

        received = engine.tcp_receive(host, port)
        assert received['success'] is True, received['error_message']
        assert received['body'] == "hello over TLS"
        engine.tcp_disconnect(host, port)

    def test_tls_verify_rejects_self_signed(self, engine, tls_echo_server):
        host, port = tls_echo_server
        resp = engine.tcp_connect(host, port, use_tls=True, tls_verify=True,
                                  conn_id="verify-probe")
        assert resp['success'] is False
        assert 'certificate' in resp['error_message'].lower() \
            or 'handshake' in resp['error_message'].lower()

    def test_plain_tcp_still_works_alongside_tls(self, engine, mock_tcp_server):
        server, port = mock_tcp_server
        host = server.host
        resp = engine.tcp_connect(host, port)
        assert resp['success'] is True
        assert 'TCP connection established' in resp['body']
        engine.tcp_disconnect(host, port)


# ---------------------------------------------------------------------------
# MQTT over TLS
# ---------------------------------------------------------------------------

class TestMQTTOverTLS:
    def test_mqtts_connect_publish_disconnect(self, engine, tls_mqtt_broker):
        host, port = tls_mqtt_broker
        resp = engine.mqtt_connect(host, broker_port=port, client_id="tls-client",
                                   use_tls=True, tls_verify=False)
        assert resp['success'] is True, resp['error_message']

        pub = engine.mqtt_publish(host, broker_port=port, client_id="tls-client",
                                  topic="t/tls", payload="secret payload", qos=0)
        assert pub['success'] is True, pub['error_message']

        sub = engine.mqtt_subscribe(host, broker_port=port, client_id="tls-client",
                                    topic="t/tls", qos=0)
        assert sub['success'] is True, sub['error_message']

        disc = engine.mqtt_disconnect(host, broker_port=port, client_id="tls-client")
        assert disc['success'] is True, disc['error_message']

    def test_mqtts_verify_rejects_self_signed(self, engine, tls_mqtt_broker):
        host, port = tls_mqtt_broker
        resp = engine.mqtt_connect(host, broker_port=port, client_id="tls-verify-probe",
                                   use_tls=True, tls_verify=True)
        assert resp['success'] is False
        assert 'certificate' in resp['error_message'].lower() \
            or 'handshake' in resp['error_message'].lower()
