"""
Tests for Engine.capabilities() runtime capability introspection.

capabilities() reports, per protocol, whether the build is "real" (actually
contacts a server), "simulated" (synthetic responses), or "not_implemented",
plus a "tls" bool. The C extension derives this from the compile-time feature
macros; the Python fallback engine reports its own fixed capabilities.
"""

import pytest

from loadspiker.engine import _c_extension_available


PROTOCOL_KEYS = {"http", "tcp", "udp", "mqtt", "websocket", "database", "tls"}
DB_KEYS = {"postgresql", "mysql", "mongodb"}
ALLOWED_STATES = {"real", "simulated", "not_implemented"}


class TestCapabilitiesShape:
    """Structure and allowed values, independent of which backend is compiled."""

    def test_returns_dict(self, engine):
        caps = engine.capabilities()
        assert isinstance(caps, dict)

    def test_has_all_top_level_keys(self, engine):
        caps = engine.capabilities()
        assert set(caps.keys()) == PROTOCOL_KEYS

    def test_database_is_dict_with_all_backends(self, engine):
        caps = engine.capabilities()
        assert isinstance(caps["database"], dict)
        assert set(caps["database"].keys()) == DB_KEYS

    def test_protocol_values_in_allowed_set(self, engine):
        caps = engine.capabilities()
        for key in ("http", "tcp", "udp", "mqtt", "websocket"):
            assert caps[key] in ALLOWED_STATES, f"{key}={caps[key]!r}"
        for backend, state in caps["database"].items():
            assert state in ALLOWED_STATES, f"database.{backend}={state!r}"

    def test_tls_is_bool(self, engine):
        caps = engine.capabilities()
        assert isinstance(caps["tls"], bool)

    def test_always_real_protocols(self, engine):
        """HTTP/TCP/UDP have no simulated fallback in either engine."""
        caps = engine.capabilities()
        assert caps["http"] == "real"
        assert caps["tcp"] == "real"
        assert caps["udp"] == "real"


@pytest.mark.skipif(not _c_extension_available,
                    reason="C extension not available")
class TestCapabilitiesCExtension:
    """This machine's build has all real backends compiled in
    (HAVE_CURL_WEBSOCKETS, HAVE_LIBPQ, HAVE_MYSQL, HAVE_MONGOC, HAVE_OPENSSL)."""

    def test_mqtt_real(self, engine):
        assert engine.capabilities()["mqtt"] == "real"

    def test_websocket_real(self, engine):
        assert engine.capabilities()["websocket"] == "real"

    def test_all_database_backends_real(self, engine):
        db = engine.capabilities()["database"]
        assert db == {"postgresql": "real", "mysql": "real", "mongodb": "real"}

    def test_tls_enabled(self, engine):
        assert engine.capabilities()["tls"] is True


@pytest.mark.skipif(_c_extension_available,
                    reason="Python fallback engine only used without C extension")
class TestCapabilitiesPythonFallback:
    def test_fallback_capabilities(self, engine):
        caps = engine.capabilities()
        assert caps["mqtt"] == "simulated"
        assert caps["websocket"] == "not_implemented"
        assert caps["database"] == {
            "postgresql": "not_implemented",
            "mysql": "not_implemented",
            "mongodb": "not_implemented",
        }
        assert caps["tls"] is True
