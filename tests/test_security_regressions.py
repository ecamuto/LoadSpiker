"""
Regression tests for the C-layer security fixes (see docs/SECURITY_AUDIT.md).

These guard against re-introducing:
  * V1-V3 — MQTT CONNECT/PUBLISH/SUBSCRIBE stack-buffer overflows. The fix
    rejects over-length inputs before the fixed-size packet buffers are filled.
  * V11   — UDP re-bind on every operation. The endpoint must keep one socket
    with a single stable ephemeral source port.
  * V9    — reference-count leak while building result dictionaries in the
    C extension (coarse object-count guard).

All of these live in the C extension, so the suite skips when only the pure
Python fallback is available (the fallback simulates and does not enforce caps).
"""

import gc
import socket

import pytest

from loadspiker import Engine
from loadspiker.engine import _c_extension_available

pytestmark = pytest.mark.skipif(
    not _c_extension_available,
    reason="C extension not built; over-length guards live in C, not the fallback",
)

# Mirrors the caps in src/protocols/mqtt.h
MAX_MQTT_CLIENT_ID_LENGTH = 128
MAX_MQTT_TOPIC_LENGTH = 256
MAX_MQTT_MESSAGE_LENGTH = 8192


@pytest.fixture
def engine():
    eng = Engine(max_connections=10, worker_threads=2)
    yield eng
    del eng


# --------------------------------------------------------------------------
# V1-V3: over-length MQTT inputs are rejected before packet encoding
# --------------------------------------------------------------------------

def test_mqtt_connect_overlong_client_id_rejected(engine):
    """V1: client_id longer than the cap must be refused, not memcpy'd."""
    resp = engine.mqtt_connect(
        broker_host="127.0.0.1", broker_port=1883,
        client_id="x" * (MAX_MQTT_CLIENT_ID_LENGTH + 64),
    )
    assert resp["success"] is False
    assert resp["status_code"] == 400
    assert "too long" in resp["error_message"].lower()


def test_mqtt_publish_overlong_topic_rejected(engine):
    """V2: an over-length PUBLISH topic is refused before the buffer is built."""
    resp = engine.mqtt_publish(
        broker_host="127.0.0.1", broker_port=1883, client_id="reg",
        topic="t" * (MAX_MQTT_TOPIC_LENGTH + 64), payload="hi",
    )
    assert resp["success"] is False
    assert resp["status_code"] == 400
    assert "too long" in resp["error_message"].lower()


def test_mqtt_publish_overlong_payload_rejected(engine):
    """V2: an over-length PUBLISH payload is refused."""
    resp = engine.mqtt_publish(
        broker_host="127.0.0.1", broker_port=1883, client_id="reg",
        topic="ok", payload="p" * (MAX_MQTT_MESSAGE_LENGTH + 64),
    )
    assert resp["success"] is False
    assert resp["status_code"] == 400
    assert "too long" in resp["error_message"].lower()


def test_mqtt_subscribe_overlong_topic_rejected(engine):
    """V3: an over-length SUBSCRIBE topic is refused."""
    resp = engine.mqtt_subscribe(
        broker_host="127.0.0.1", broker_port=1883, client_id="reg",
        topic="s" * (MAX_MQTT_TOPIC_LENGTH + 64),
    )
    assert resp["success"] is False
    assert resp["status_code"] == 400
    assert "too long" in resp["error_message"].lower()


# --------------------------------------------------------------------------
# V11: a UDP endpoint keeps one socket with a stable ephemeral source port
# --------------------------------------------------------------------------

def test_udp_endpoint_uses_stable_ephemeral_port(engine):
    """Two sends from the same endpoint must share one ephemeral source port
    (the endpoint is not recreated / re-bound per operation)."""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(5.0)
    host, port = server.getsockname()

    try:
        engine.udp_create_endpoint(host, port, conn_id="reg_udp")

        engine.udp_send(host, port, "first", conn_id="reg_udp")
        _, addr1 = server.recvfrom(1024)

        engine.udp_send(host, port, "second", conn_id="reg_udp")
        _, addr2 = server.recvfrom(1024)

        src_port_1 = addr1[1]
        src_port_2 = addr2[1]

        assert src_port_1 != 0, "endpoint should bind a real ephemeral port"
        assert src_port_1 == src_port_2, (
            f"source port changed between sends ({src_port_1} -> {src_port_2}); "
            "endpoint was re-bound (V11 regression)"
        )
    finally:
        engine.udp_close_endpoint(host, port, conn_id="reg_udp")
        server.close()


# --------------------------------------------------------------------------
# V9: building result dictionaries must not leak references
# --------------------------------------------------------------------------

def test_dict_building_does_not_leak_objects(engine):
    """Repeatedly drive a dict-returning rejection path; the live object count
    must not grow ~1 per call (the V9 signature)."""
    iterations = 4000
    over_topic = "t" * (MAX_MQTT_TOPIC_LENGTH + 64)

    # Warm up so first-call caches/interning don't count as growth.
    for _ in range(200):
        engine.mqtt_publish(broker_host="127.0.0.1", client_id="reg",
                            topic=over_topic, payload="x")
    gc.collect()
    before = len(gc.get_objects())

    for _ in range(iterations):
        engine.mqtt_publish(broker_host="127.0.0.1", client_id="reg",
                            topic=over_topic, payload="x")

    gc.collect()
    after = len(gc.get_objects())

    # A genuine per-call leak would add ~`iterations` objects. Allow generous
    # slack for unrelated allocator noise.
    assert after - before < iterations // 8, (
        f"object count grew by {after - before} over {iterations} calls "
        "(possible reference leak — V9 regression)"
    )
