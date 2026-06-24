# LoadSpiker — Outstanding Work & Backlog

Consolidated TODO across the codebase: the Python-layer audit (below), the
remaining items from the C [Security & Correctness Audit](SECURITY_AUDIT.md), and
the engineering/doc backlog. Items are tagged with priority and a reference.

Priority: 🔴 high · 🟠 medium · 🟡 low

---

## 1. Python-layer audit findings

Audit of `authentication.py`, `session_manager.py`, `data_sources.py`,
`reporters.py`, `cli.py`, `utils.py`, `assertions.py`,
`performance_assertions.py`.

**Status: P1–P5 all fixed this pass** (see [Done this pass](#done-this-pass-for-context)).

| ID | Sev | Location | Issue | Suggested fix |
| -- | --- | -------- | ----- | ------------- |
| ✅ P1 | 🟠 | [data_sources.py:98-125](../loadspiker/data_sources.py#L98) | **Silent CSV type coercion corrupts string data.** `value.isdigit()`→int, `'.' in value`→float, `"true"/"false"`→bool. Leading-zero IDs (`"007"`→7), zip codes (`"01234"`→1234), version strings (`"1.10"`→1.1), `"false"`→bool. Data-driven request parameters are mangled with no opt-out. | Make coercion opt-in (`coerce_types=False` default), or never coerce values with leading zeros, or keep raw strings and let scenarios cast explicitly. |
| ✅ P2 | 🟡 | [authentication.py:440-500](../loadspiker/authentication.py#L440) | OAuth2 `state` is generated and stored but **never validated** on code exchange — the CSRF value is unused. | Compare returned `state` against `session.get('oauth2_state')` before exchanging the code. |
| ✅ P3 | 🟡 | [authentication.py:193](../loadspiker/authentication.py#L193) | Bearer `_fetch_token_from_endpoint` returns the **full `token_response`** (access + refresh tokens) in its result dict; logging the result leaks secrets. OAuth2 flow truncates its token (inconsistent). | Drop or redact `token_response` from the returned dict; expose only metadata (`expires_in`, `has_refresh_token`). |
| ✅ P4 | 🟡 | [reporters.py:233](../loadspiker/reporters.py#L233) | HTMLReporter embeds `json.dumps(progress_data)` in a `<script>` block and metrics via f-string. **Currently safe** (only numeric data flows in), but no escaping / `</script>` handling — latent XSS if any string field (URL/error/body) is ever added to the report. | Escape with `</` → `<\/` in the JSON dump and HTML-escape any string fields before interpolation, as defense-in-depth. |
| ✅ P5 | 🟡 | [cli.py:152-167](../cli.py#L152) | Config access `config['base_url']` / `req_config['url']` is unguarded → a missing key surfaces as a generic "Test failed" rather than a clear message. | Validate required keys and emit a specific error. |

**Verified clean:** `session_manager.py` (properly `RLock`-guarded, no lock
inversion); no `eval`/`exec`/`pickle`/`yaml.load`/`shell=True`/`verify=False`
anywhere; `parse_load_pattern` only does `int()` parsing; assertions modules
have no risky patterns.

---

## 2. C audit — still open

From [SECURITY_AUDIT.md](SECURITY_AUDIT.md). None are memory-safety holes.

**Status: V6, V8, V11, V14 all fixed this pass.**

- [x] 🟠 **V6 — binary payload truncation.** Fixed: extension marshals `data`
      with `s*` (accepts `str` and `bytes`, carries length); `tcp_send`/`udp_send`
      now take a `size_t data_len` and no longer call `strlen(data)`. Binary
      payloads with embedded NULs send in full (verified by NUL roundtrip).
- [x] 🟡 **V8 — MQTT control-packet partial reads.** Fixed: added
      `mqtt_recv_full()` read-to-length loop; CONNACK/SUBACK/UNSUBACK use it and
      reject short reads.
- [x] 🟡 **V11 — UDP re-`bind()` on every receive.** Fixed: endpoint tracks a
      `local_bound` flag; `udp_receive` binds at most once per endpoint.
- [x] 🟡 **V14 — DB result aliases the union via `char[]` cast.** Fixed: both
      writer (`database.c`) and reader (`python_extension.c`) use the named
      `protocol_data.database` union member.

---

## 3. Concurrency / performance follow-ups

- [x] 🟠 **MQTT & Database lock narrowing.** Fixed: MQTT
      connect/publish/subscribe/unsubscribe now find/reserve under the pool
      mutex then release it before blocking `connect`/`send`/`recv` (added
      `mqtt_find_or_reserve_locked`; reserved slots are never removed, so the
      slot pointer stays valid after unlock; send/recv failures re-lock only to
      flip `is_connected`). Database `execute_query` releases `db_pool_mutex`
      before the simulated `usleep`.
- [x] 🟡 **Per-user Database isolation.** Fixed: DB connections are now keyed by
      `(connection_string, conn_id)`; `conn_id` is threaded through
      `database_*` / `engine_database_*` / the extension / `engine.py`
      (default `"default"`). One user's disconnect no longer flips
      `is_connected` for others (verified).

---

## 4. Functional gaps

- [x] 🔴 **WebSocket is real.** `websocket.c` now does real RFC 6455 frames via
      libcurl's WebSocket API (`curl_ws_send`/`curl_ws_recv`, `CONNECT_ONLY=2`),
      gated by `HAVE_CURL_WEBSOCKETS` (falls back to the simulated path where
      libcurl lacks WS). The extension's WS methods now release the GIL during
      I/O. Verified end-to-end against a local RFC 6455 echo server (new
      `mock_websocket_server` fixture).
- [x] 🔴 **Database: real PostgreSQL.** `database.c` connects/queries real
      PostgreSQL via libpq (`PQconnectdb`/`PQexec`), gated by `HAVE_LIBPQ`.
      MySQL/MongoDB remain simulated (no client linked). Real connect verified
      against a live server; PG tests skip when none is reachable.
- [x] 🟡 `websocket.c` clock unified to the shared monotonic `get_time_us()`
      (removed the local `gettimeofday` helper).

---

## 5. Refactor / cleanup

- [ ] 🟡 **Dedup protocol pool boilerplate.** find-or-create + pool-full logic is
      copy-pasted across `tcp.c`, `udp.c`, `mqtt.c`. Extract a shared helper.
- [ ] 🟡 **Coarse ramp-up.** `engine.py:_run_with_ramp_up` re-runs
      `start_load_test` in 5 s bursts with `sleep(1)`. Consider driving ramp in
      the C core for smoother granularity.
- [ ] 🟡 **Consolidate root-level `test_*.py` scripts.** ~17 ad-hoc scripts sit
      in the repo root alongside the real `tests/` suite. Fold the useful ones
      into `tests/`, delete the rest.

---

## 6. Verification gaps

- [x] 🟠 **Run AddressSanitizer.** Done. `make test-asan` now builds a standalone
      natively-instrumented harness (`tests/asan_check.c`, mirroring the tsan
      target) — injecting ASan into stock CPython on macOS loads the runtime too
      late ("Interceptors are not working"). The harness drives the MQTT
      CONNECT/PUBLISH/SUBSCRIBE encoders (V1–V3) at their maximum permitted input
      lengths plus the over-length rejection guards; ASan reports no memory
      errors. Caveat: V9 (Python refcount leak) needs a live interpreter and is
      not covered here — macOS also lacks LeakSanitizer. Also fixed a latent
      breakage: `tests/tsan_check.c` still used the pre-isolation 3-arg
      `database_connect`; updated to the `conn_id` signature so `make tsan`
      compiles again.
- [ ] 🟡 **Regression tests for security fixes.** Add tests for MQTT over-length
      rejection (V1–V3), the refcount-leak fix (V9), and ephemeral UDP port.
- [ ] 🟡 **CI.** No CI config; add one that runs `make test` + `make tsan`.

---

## 7. Documentation reconciliation

- [x] 🟠 **`docs/site/*.html` reconciled.** Updated `protocols.html`,
      `architecture.html`, `api-reference.html`, and `roadmap.html` to match the
      real capability state: WebSocket is real RFC 6455 (libcurl WS,
      `HAVE_CURL_WEBSOCKETS`) with a simulated fallback; PostgreSQL is real
      (libpq, `HAVE_LIBPQ`) while MySQL/MongoDB stay simulated; all protocols are
      bound through the Python extension (dropped the stale "Python bindings
      pending" / "Phase 1 simulation" notices). Also corrected the
      [README](../README.md) matrix itself, which still claimed WebSocket/Database
      were simulated and TCP truncated binary/NUL payloads (fixed by V6).
- [ ] 🟡 Reconcile [docs/API.md](API.md), [docs/CODE_ANALYSIS.md](CODE_ANALYSIS.md),
      [docs/ROADMAP.md](ROADMAP.md), [CHANGELOG.md](../CHANGELOG.md), and the
      short [CONTRIBUTING.md](../CONTRIBUTING.md) with the current state and the
      new [Contributor Guide](CONTRIBUTOR_GUIDE.md).

---

## Done this pass (for context)

- C extension bridges all protocols (TCP/UDP/MQTT/Database); previously only
  HTTP + WebSocket were exposed (everything else raised `AttributeError`).
- MQTT packet-encoder stack overflows fixed (V1–V3); MQTT connect error paths
  fixed (V7); atomic shutdown flags (V4); racy fd-lookup wrappers removed (V5);
  refcount leak fixed (V9); dead `response_queue` removed (V12); libcurl path
  de-triplicated.
- Non-HTTP scenarios now execute under concurrent load.
- TCP/UDP per-user connection isolation + lock-narrowed I/O (no shared sockets;
  no process-wide serialization).
- New docs: README rewrite, Contributor Guide, Security Audit, this backlog.
- Python-layer audit P1–P5 fixed: CSV coercion now opt-in & leading-zero-safe
  (P1); OAuth2 `state` validated on code exchange (P2); Bearer result redacts
  raw `token_response` (P3); HTMLReporter escapes `</` in `<script>` (P4); CLI
  config validates required `base_url`/`url` keys (P5).
- C audit V6/V8/V11/V14 fixed: length-carrying TCP/UDP send for binary payloads
  (V6); MQTT read-to-length loop (V8); UDP binds once per endpoint (V11); DB
  response uses the named union member (V14).
- Concurrency follow-ups fixed: MQTT (connect/publish/subscribe/unsubscribe) and
  Database (`execute_query` usleep) now narrow the pool mutex to the lookup, no
  longer serializing those protocols process-wide; DB connections are isolated
  per virtual user via `conn_id`.
- Functional gaps closed (§4): real RFC 6455 WebSocket via libcurl's WS API
  (GIL released during I/O); real PostgreSQL via libpq (MySQL/Mongo still sim);
  websocket.c clock unified to monotonic `get_time_us()`. setup.py now detects
  libcurl via curl-config and libpq via pg_config, defining `HAVE_CURL_WEBSOCKETS`
  / `HAVE_LIBPQ` so the build degrades gracefully where those are absent.
