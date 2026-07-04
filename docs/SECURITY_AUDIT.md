# LoadSpiker Security & Correctness Audit

Audit of the C engine, the CPython extension, and the protocol modules, focused
on memory safety, concurrency, resource handling, and correctness. Each finding
lists severity, location, impact, and the fix (with status). Findings marked
**Fixed** were addressed in the refactor that accompanies this document.
The remaining **By design** items (V13, V15) are trust-boundary notes, not bugs;
the full backlog is tracked in [TODO.md](TODO.md) and the
[Contributor Guide](CONTRIBUTOR_GUIDE.md).

Severity: 🔴 high · 🟠 medium · 🟡 low

| ID | Sev | Area | Status |
| -- | --- | ---- | ------ |
| V1 | 🔴 | MQTT CONNECT stack overflow | ✅ Fixed |
| V2 | 🔴 | MQTT PUBLISH stack overflow | ✅ Fixed |
| V3 | 🔴 | MQTT SUBSCRIBE/UNSUBSCRIBE stack overflow | ✅ Fixed |
| V4 | 🟠 | Data race on `shutdown`/`active` | ✅ Fixed |
| V5 | 🟠 | Racy fd→host lookup in TCP/UDP engine wrappers | ✅ Fixed (removed) |
| V6 | 🟠 | Binary payload truncation (`strlen`) | ✅ Fixed |
| V7 | 🟠 | MQTT connect error paths leak/alias sockets | ✅ Fixed |
| V8 | 🟠 | MQTT control-packet partial reads | ✅ Fixed |
| V9 | 🟡 | Python refcount leak in dict building | ✅ Fixed |
| V10 | 🟡 | Empty error messages on WS failure | ✅ Fixed |
| V11 | 🟡 | UDP re-`bind()` on every receive | ✅ Fixed |
| V12 | 🟡 | Dead `response_queue` allocation | ✅ Fixed |
| V13 | 🟡 | Arbitrary code execution via scenario files | ⚠️ By design (documented) |
| V14 | 🟡 | DB result aliases union via `char[]` cast | ✅ Fixed |
| V15 | 🟡 | SQL injection surface in real DB backends | ⚠️ By design (documented) |

---

## 🔴 High

### V1 — MQTT CONNECT packet: unbounded `memcpy` into a 1024-byte stack buffer
**Location:** `src/protocols/mqtt.c`, `mqtt_create_connect_packet()` /
`mqtt_connect()`.
**Impact:** `client_id`, `username`, and `password` were `memcpy`-ed into
`char connect_packet[1024]` with no length validation. A long client id or
credential overflows the stack frame → memory corruption / potential RCE.
**Fix:** `mqtt_connect()` now rejects inputs exceeding
`MAX_MQTT_CLIENT_ID_LENGTH`/`USERNAME`/`PASSWORD` (128/256/256) before building
the packet. With those caps the maximum encoded packet (≈656 B) cannot exceed
the buffer.

### V2 — MQTT PUBLISH packet overflow
**Location:** `mqtt_create_publish_packet()` / `mqtt_publish()`.
**Impact:** `topic` and `message` were copied into
`char publish_packet[MAX_MQTT_MESSAGE_LENGTH + 512]` with the message length
never checked and the topic length unbounded → stack overflow for large topics
or payloads > 8 KiB.
**Fix:** `mqtt_publish()` now rejects `topic > 255` or `message > 8191` bytes up
front; the bounded inputs fit the buffer with margin.

### V3 — MQTT SUBSCRIBE / UNSUBSCRIBE packet overflow
**Location:** `mqtt_subscribe()` / `mqtt_unsubscribe()` (both build a
`char [512]` packet).
**Impact:** `topic` copied unchecked → overflow for topics ≳ 500 bytes.
**Fix:** both functions now reject `topic > 255` bytes before encoding.

> **Reachability note:** V1–V3 are reachable from Python now that the MQTT
> bridge exists (`engine.mqtt_*`). Before the bridge they were only reachable
> from C tests. They are fixed regardless.

---

## 🟠 Medium

### V4 — Data race on `engine->shutdown` and `worker.active`
**Location:** `src/engine.c` worker loops vs `engine_destroy`.
**Impact:** the shutdown flag and per-worker `active` flag were plain `bool`s
read in worker loops without the lock and written during teardown — a classic
torn-flag race (and undefined behavior under the C memory model).
**Fix:** both are now `_Atomic`. `make tsan` reports no races.

### V5 — Racy fd→host lookup in TCP/UDP engine wrappers
**Location:** former `engine_tcp_send/receive/disconnect`,
`engine_udp_send/receive/close_endpoint` + `tcp_lookup_by_fd`/`udp_lookup_by_fd`.
**Impact:** these wrappers translated a socket fd back to a `host:port` and then
re-looked-up the pool entry by `host:port`. Two connections to the same endpoint
collapsed to one slot, and a closed-then-reused fd could alias the wrong entry
under concurrency.
**Fix:** the wrappers were **dead code** (nothing called them — the Python
bridge talks to the protocol functions directly). They were removed entirely,
eliminating the unsafe lookup path. The pools were subsequently re-keyed by
`(host, port, conn_id)` for per-virtual-user socket isolation, and the pool
mutex is no longer held during blocking I/O (it is taken only to find/reserve/
mutate a slot), removing the process-wide serialization of socket operations.

### V6 — Binary payloads truncated at the first NUL  *(Fixed)*
**Location:** former `tcp_send()`, `udp_send()` used `strlen(data)`; the
extension marshalled `data` as a `str`.
**Impact:** payloads containing `0x00` were silently truncated; true binary load
testing was not possible.
**Fix:** the extension now marshals `data` with `s*` (accepts `str` and `bytes`,
carries length); `tcp_send`/`udp_send` take a `size_t data_len` and no longer
call `strlen(data)`, so binary payloads with embedded NULs send in full
(verified by a NUL roundtrip). See `tcp_send` ([tcp.c:234](../src/protocols/tcp.c#L234))
and `udp_send` ([udp.c:156](../src/protocols/udp.c#L156)).

### V7 — MQTT connect error paths leaked/aliased sockets
**Location:** `mqtt_connect()` DNS-fail, connect-fail, and CONNECT-send-fail
branches.
**Impact:** these branches called `close(socket_fd)` but left `socket_fd >= 0`
and left a freshly-allocated pool slot in place. `mqtt_cleanup_all()` would then
`close()` the same fd again (double close / fd aliasing).
**Fix:** every error branch now sets `socket_fd = -1` and rolls back a
newly-allocated slot (`new_entry`).

### V8 — MQTT control packets assume single-read delivery  *(Fixed)*
**Location:** CONNACK (`mqtt_connect`), SUBACK (`mqtt_subscribe`), UNSUBACK
(`mqtt_unsubscribe`) previously used one `recv()`.
**Impact:** a TCP segment boundary splitting the control packet yielded a false
failure. Not a memory-safety issue; a robustness gap.
**Fix:** added a `mqtt_recv_full()` read-to-length loop
([mqtt.c:31](../src/protocols/mqtt.c#L31)); CONNACK/SUBACK/UNSUBACK now read to
the expected length and reject short reads.

---

## 🟡 Low

### V9 — Reference-count leak when building result dictionaries  *(Fixed)*
**Location:** `src/python_extension.c`, every `PyDict_SetItemString(d, k,
PyXxx_From*(…))`.
**Impact:** `PyDict_SetItemString` does not steal a reference, so each temporary
(`PyLong`, `PyUnicode`, …) leaked one object per insert. Over a long run this is
a steady, load-proportional memory leak.
**Fix:** all inserts go through a `dict_set()` helper that `Py_DECREF`s the
value after insertion; string creation goes through `safe_str()`.

### V10 — Empty `RuntimeError` message on WebSocket failure  *(Fixed)*
**Location:** WebSocket extension methods raised
`PyErr_SetString(…, response.error_message)` even when the message was empty.
**Fix:** a default message is used when `error_message` is empty.

### V11 — UDP `bind()` on every receive  *(Fixed)*
**Location:** `udp_receive()` previously called `bind()` each time and ignored
failure.
**Impact:** only the first bind succeeded; subsequent calls silently relied on
the existing binding. Harmless but surprising.
**Fix:** the endpoint tracks a `local_bound` flag
([udp.c:243](../src/protocols/udp.c#L243)); `udp_receive` binds at most once per
endpoint.

### V12 — Dead `response_queue` allocation  *(Fixed)*
**Location:** `struct engine` allocated a `response_queue` parallel to the
request queue that was never read or written.
**Fix:** field and its `malloc`/`free` removed.

### V13 — Scenario / config files execute arbitrary code  *(By design)*
**Location:** `cli.py -s scenario.py` loads a user Python file via `importlib`.
**Impact:** running a scenario file is equivalent to running arbitrary Python.
This is expected for a scripting-first load tool, **but must be treated as a
trust boundary**: only run scenario files you authored or trust. Documented in
the README.

### V14 — Database result data aliases the union through a `char[]` cast  *(Fixed)*
**Location:** `database.c` previously cast `response->protocol_data.protocol_data`
(`char[32768]`) to `database_response_data_t*` (which embeds a 64 KiB
`result_set`). Because `database_response_data_t` is itself a member of the same
union, the union was large enough and no out-of-bounds write occurred, but the
aliasing was fragile.
**Fix:** both writer ([database.c:183](../src/protocols/database.c#L183)) and
reader ([python_extension.c:691](../src/python_extension.c#L691)) now use the
named `protocol_data.database` union member instead of the `char[]` cast.

### V15 — SQL injection surface in real database backends  *(By design)*
**Location:** `database_postgres_query` runs the caller's query string verbatim
through `PQexec` ([database.c:185](../src/protocols/database.c#L185));
`database_mysql_query` likewise through `mysql_query`
([database.c:254](../src/protocols/database.c#L254)); MongoDB parses the query
string as a JSON command document for `mongoc_client_command_simple`
([database.c:346](../src/protocols/database.c#L346)). None use parameterized
APIs (`PQexecParams` / `mysql_stmt_*`).
**Impact:** now that PostgreSQL/MySQL/MongoDB backends are real (V6-era pass
made WebSocket/PG real; subsequent work added real MySQL + MongoDB), any scenario
that interpolates untrusted data into a query string is a SQL/NoSQL injection
vector against the *target* database.
**Why by design:** the query string is authored in the scenario, which already
executes arbitrary code (see V13) — the scenario author is inside the trust
boundary, so this is no worse than V13. It is called out explicitly because real
backends make the consequence concrete: **build query strings only from data you
trust, and parameterize at the scenario layer rather than string-formatting
untrusted input.** If first-class parameter binding is wanted later, thread bound
parameters through to `PQexecParams` / prepared statements.

---

## How to reproduce / verify

```bash
# Memory safety (V1–V3, V7, V9): AddressSanitizer + LeakSanitizer
make debug
ASAN_OPTIONS=detect_leaks=1 python3 your_mqtt_or_load_script.py

# Data races (V4, V5): ThreadSanitizer stress harness
make tsan          # -> "TSAN check passed - no data races detected"

# Functional regression coverage
make test          # full suite, all protocols exercised
```

## Summary

The high-severity findings were all in the hand-rolled MQTT packet encoders
(missing bounds checks on caller-controlled strings) and are fixed. The most
impactful *correctness* issue was that the C extension never exposed
TCP/UDP/MQTT/Database, so those `Engine` methods raised `AttributeError`
whenever the C engine was active — now bridged. The former open items (V6, V8,
V11, V14) — robustness/ergonomics gaps, not memory-safety holes — are now all
fixed: length-carrying binary TCP/UDP send (V6), MQTT read-to-length loop (V8),
UDP bind-once (V11), and the named DB union member (V14). The only non-fixed
finding is V15 (SQL/NoSQL injection surface in the now-real DB backends), which
is a trust-boundary note rather than a bug — equivalent to V13: build query
strings only from data you trust.
