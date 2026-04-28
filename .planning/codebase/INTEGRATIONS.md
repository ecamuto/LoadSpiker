# External Integrations

**Analysis Date:** 2026-04-29

## APIs & External Services

**Target Under Test (user-defined):**
- Any HTTP/HTTPS endpoint - The engine fires requests at URLs supplied by the user via CLI or Python API
  - SDK/Client: libcurl (C layer) or `requests` (Python fallback)
  - Auth: user-supplied headers / auth flow classes in `loadspiker/authentication.py`

**Example/Quick-test endpoint:**
- httpbin.org (`https://httpbin.org/get`) - Referenced in `Makefile` `quick-test` target for smoke testing; not a hard dependency

## Data Storage

**Databases:**
- MySQL, PostgreSQL, MongoDB - LoadSpiker can load-test these databases by connecting and executing queries
  - Connection strings parsed in `src/protocols/database.c`: `mysql://user:pass@host:port/db`, `postgresql://...`, `mongodb://...`
  - C-layer implementation: `src/protocols/database.c` / `src/protocols/database.h`
  - Python API: `Engine.database_connect()`, `Engine.database_query()`, `Engine.database_disconnect()` in `loadspiker/engine.py`
  - Default ports: MySQL 3306, PostgreSQL 5432, MongoDB 27017 (defined in `src/common.h`)
  - Note: The database protocol in the C layer currently parses connection strings and simulates operations; full driver integration is marked as stubs in `src/protocols/database.c`

**File Storage:**
- CSV files - `loadspiker/data_sources.py` provides `CSVDataSource` / `DataManager` for parameterized test data; files are read from local filesystem

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- Custom (no third-party auth SDK)
  - Implementation: `loadspiker/authentication.py` provides pluggable auth flows managed by `AuthenticationManager`
  - Supported flows:
    - `BasicAuthenticationFlow` - HTTP Basic Auth (base64 credentials)
    - `BearerTokenAuthenticationFlow` - Static JWT/OAuth token or token fetched from an OAuth endpoint via `client_credentials` or `authorization_code` grant
    - `APIKeyAuthenticationFlow` - Key injected as a request header (default `X-API-Key`) or query parameter
    - `FormBasedAuthenticationFlow` - POST to a login URL with username/password fields; cookie-based session tracking
    - `OAuth2AuthorizationCodeFlow` - Full authorization code exchange with token refresh
    - `CustomAuthenticationFlow` - User-supplied callable
  - Session state stored in-memory via `loadspiker/session_manager.py` (`SessionStore`, `get_session_manager()`)

## Monitoring & Observability

**Error Tracking:**
- None (no Sentry, Datadog, etc.)

**Logs:**
- `print()` statements throughout Python layer and build scripts
- Metrics collected in-process via `metrics_t` struct in `src/engine.h` (atomic counters: total/success/failed requests, response times, RPS)
- Results surfaced via `ConsoleReporter`, `JSONReporter`, `HTMLReporter` in `loadspiker/reporters.py`

## CI/CD & Deployment

**Hosting:**
- Not applicable - LoadSpiker is a local CLI tool and Python library, not a hosted service

**CI Pipeline:**
- None detected (no `.github/`, `.circleci/`, `.travis.yml`, etc.)

## Environment Configuration

**Required env vars (build time):**
- `LOADSPIKER_DEBUG` - Set to `1` for debug build with AddressSanitizer
- `LOADSPIKER_VERBOSE` - Set to `1` for verbose build output
- `HOMEBREW_PREFIX` - macOS only; defaults to `/opt/homebrew` if not set

**Required env vars (runtime):**
- `PYTHONPATH` - Must include project root when running without `pip install` (set by `activate_env.sh`)

**Secrets location:**
- No secrets managed by the tool itself; users pass credentials (API keys, passwords, OAuth client secrets) directly in their test scripts or as arguments to auth flow constructors

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None (LoadSpiker initiates all connections to targets under test; no webhook dispatch)

## Protocol Support Matrix

LoadSpiker is designed to load-test external systems over the following protocols (all implemented in `src/protocols/`):

| Protocol | C Implementation | Python Fallback | Notes |
|----------|-----------------|-----------------|-------|
| HTTP/HTTPS | `src/engine.c` (libcurl) | `requests` library | Full |
| WebSocket (ws/wss) | `src/protocols/websocket.c` | Stub (501) | State tracking only |
| TCP | `src/protocols/tcp.c` | stdlib `socket` | Full |
| UDP | `src/protocols/udp.c` | stdlib `socket` | Full |
| MQTT | `src/protocols/mqtt.c` | Simulated | Default port 1883 |
| Database (MySQL/PG/Mongo) | `src/protocols/database.c` | Stub (501) | URL parsing; driver stubs |

---

*Integration audit: 2026-04-29*
