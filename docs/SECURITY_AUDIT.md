# LoadSpiker Security & Correctness Audit

Audit of the C engine, the CPython extension, and the protocol modules, focused
on memory safety, concurrency, resource handling, and correctness. Each finding
lists severity, location, impact, and the fix (with status). Findings marked
**Fixed** were addressed in the refactor that accompanies this document;
**Open** items are tracked in the [Contributor Guide](CONTRIBUTOR_GUIDE.md) TODO.

Severity: 🔴 high · 🟠 medium · 🟡 low

| ID | Sev | Area | Status |
| -- | --- | ---- | ------ |
| V1 | 🔴 | MQTT CONNECT stack overflow | ✅ Fixed |
| V2 | 🔴 | MQTT PUBLISH stack overflow | ✅ Fixed |
| V3 | 🔴 | MQTT SUBSCRIBE/UNSUBSCRIBE stack overflow | ✅ Fixed |
| V4 | 🟠 | Data race on `shutdown`/`active` | ✅ Fixed |
| V5 | 🟠 | Racy fd→host lookup in TCP/UDP engine wrappers | ✅ Fixed (removed) |
| V6 | 🟠 | Binary payload truncation (`strlen`) | ⚠️ Open (documented) |
| V7 | 🟠 | MQTT connect error paths leak/alias sockets | ✅ Fixed |
| V8 | 🟠 | MQTT control-packet partial reads | ⚠️ Open (documented) |
| V9 | 🟡 | Python refcount leak in dict building | ✅ Fixed |
| V10 | 🟡 | Empty error messages on WS failure | ✅ Fixed |
| V11 | 🟡 | UDP re-`bind()` on every receive | ⚠️ Open (documented) |
| V12 | 🟡 | Dead `response_queue` allocation | ✅ Fixed |
| V13 | 🟡 | Arbitrary code execution via scenario files | ⚠️ By design (documented) |
| V14 | 🟡 | DB result aliases union via `char[]` cast | ⚠️ Open (benign) |

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
bridge talks to the protocol functions directly by `host:port`). They were
removed entirely, eliminating the unsafe lookup path.

### V6 — Binary payloads truncated at the first NUL  *(Open)*
**Location:** `tcp_send()`, `udp_send()` use `strlen(data)`; the extension
marshals `data` as a `str`.
**Impact:** payloads containing `0x00` are silently truncated; true binary load
testing is not possible.
**Why open:** fixing it correctly is an API change (length-carrying `y#`
marshalling end-to-end plus signature changes to `tcp_send`/`udp_send` and the
header). Deferred to keep this pass reviewable; tracked in the TODO.

### V7 — MQTT connect error paths leaked/aliased sockets
**Location:** `mqtt_connect()` DNS-fail, connect-fail, and CONNECT-send-fail
branches.
**Impact:** these branches called `close(socket_fd)` but left `socket_fd >= 0`
and left a freshly-allocated pool slot in place. `mqtt_cleanup_all()` would then
`close()` the same fd again (double close / fd aliasing).
**Fix:** every error branch now sets `socket_fd = -1` and rolls back a
newly-allocated slot (`new_entry`).

### V8 — MQTT control packets assume single-read delivery  *(Open)*
**Location:** CONNACK (`mqtt_connect`), SUBACK (`mqtt_subscribe`), UNSUBACK
(`mqtt_unsubscribe`) use one `recv()`.
**Impact:** a TCP segment boundary splitting the control packet yields a false
failure. Not a memory-safety issue; a robustness gap.
**Why open:** needs a read-to-length loop; low priority for the simulated/test
broker workflow. Tracked in the TODO.

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

### V11 — UDP `bind()` on every receive  *(Open)*
**Location:** `udp_receive()` calls `bind()` each time and ignores failure.
**Impact:** only the first bind succeeds; subsequent calls silently rely on the
existing binding. Harmless today but surprising. Bind once at endpoint creation.

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

### V14 — Database result data aliases the union through a `char[]` cast  *(Benign)*
**Location:** `database.c` casts `response->protocol_data.protocol_data`
(`char[32768]`) to `database_response_data_t*` (which embeds a 64 KiB
`result_set`). Because `database_response_data_t` is itself a member of the same
union, the union is large enough and no out-of-bounds write occurs, but the
aliasing is fragile. Prefer writing through the named union member.

---

## How to reproduce / verify

```bash
# Memory safety (V1–V3, V7, V9): AddressSanitizer + LeakSanitizer
make debug
ASAN_OPTIONS=detect_leaks=1 python3 your_mqtt_or_load_script.py

# Data races (V4, V5): ThreadSanitizer stress harness
make tsan          # -> "TSAN check passed - no data races detected"

# Functional regression coverage
make test          # 207 tests, all protocols exercised
```

## Summary

The high-severity findings were all in the hand-rolled MQTT packet encoders
(missing bounds checks on caller-controlled strings) and are fixed. The most
impactful *correctness* issue was that the C extension never exposed
TCP/UDP/MQTT/Database, so those `Engine` methods raised `AttributeError`
whenever the C engine was active — now bridged. The remaining open items (V6,
V8, V11, V14) are robustness/ergonomics improvements, not memory-safety holes,
and are tracked in the Contributor Guide.
