# LoadSpiker Contributor Guide

A deep, practical reference for anyone who wants to **study, build, debug, or
extend** LoadSpiker. If you only want to *use* the tool, read the
[README](../README.md) instead — this document is about the internals.

> Companion docs: [SECURITY_AUDIT.md](SECURITY_AUDIT.md) (known issues and the
> reasoning behind several fixes referenced here) and [API.md](API.md) (user-facing
> API surface).

---

## 1. The big picture

LoadSpiker is a **load-testing tool with a C core and a Python front end**. It is
deliberately split into three layers so that the hot path (issuing requests and
recording metrics) runs in C, while test authoring stays in ergonomic Python.

```
┌───────────────────────────────────────────────────────────────┐
│ Layer 3 — Python authoring & orchestration  (loadspiker/*.py)   │
│   Engine wrapper, Scenario builders, assertions, reporters,     │
│   session/auth managers, CSV data sources, CLI                  │
└───────────────────────────────────────────────────────────────┘
                              │  (keyword-argument method calls)
┌───────────────────────────────────────────────────────────────┐
│ Layer 2 — CPython C extension  (src/python_extension.c)         │
│   `loadspiker.Engine` type. Marshals Python args → C structs,   │
│   releases the GIL around blocking work, builds result dicts.   │
└───────────────────────────────────────────────────────────────┘
                              │  (engine_* / protocol_* C calls)
┌───────────────────────────────────────────────────────────────┐
│ Layer 1 — C engine core  (src/engine.c + src/protocols/*.c)     │
│   Worker-thread pool, request queue, libcurl HTTP, metrics      │
│   histogram, and per-protocol modules (TCP/UDP/MQTT/WS/DB).     │
└───────────────────────────────────────────────────────────────┘
```

### Life of an HTTP request

1. Python: `engine.execute_request(url=...)` → `loadspiker/engine.py` joins the
   headers dict into a `\n`-separated string and calls the C method.
2. C extension: `LoadTestEngine_execute_request` copies the args into an
   `http_request_t`, releases the GIL, and calls `engine_execute_request_sync`.
3. C core: `http_execute()` drives libcurl, writes the body/headers into
   pre-sized buffers via the write/header callbacks, fills an `http_response_t`,
   and folds the result into the metrics under `metrics_mutex`.
4. C extension: `build_response_dict()` (and a small per-protocol addendum)
   converts the struct into a Python `dict`, decref-ing every temporary.
5. Python: the dict is returned to the caller / assertions / reporters.

### Life of a load test

`engine.run_scenario(scenario, users, duration)` branches on
`scenario.is_http_only()`:

- **HTTP-only** → `scenario.build_requests()` produces request dicts →
  `start_load_test` copies them into the C request queue, spawns up to
  `min(users, num_requests)` **per-test worker threads** (`load_test_worker_func`),
  waits for the queue to drain (or a hard timeout of `duration + 5s`), then joins.
- **Protocol scenarios** (TCP/UDP/MQTT/Database/Mixed) → `_run_protocol_load_test`
  spawns one Python thread per virtual user; each thread repeatedly runs the
  scenario’s `get_load_operations(user_id)` list for `duration`, dispatching each
  op through `_execute_operation` to the (C-bridged) per-op engine methods.
  Metrics are still recorded inside the C engine via `engine_record_metrics`.

Either way, metrics are read back with `get_metrics()`.

> **Known limitation:** the protocol connection pools are keyed by `host:port`
> (not per virtual user), so multiple users targeting the same endpoint share a
> pool slot and their connect/send/receive/disconnect calls can interleave —
> some operations will legitimately fail under high user counts. Per-user
> connection isolation is a future improvement.

---

## 2. Source map

| Path | Purpose |
| ---- | ------- |
| `src/engine.h` | Public C API + all shared structs (`request_t`, `response_t`, `metrics_t`, legacy `http_*`). Start here. |
| `src/common.h` | Shared constants, timeouts, `get_time_us()` (monotonic), and the `INIT_RESPONSE` / `SET_*_RESPONSE` macros used by protocol modules. |
| `src/engine.c` | Engine lifecycle, worker pools, request queue, libcurl HTTP (`http_execute`), metrics + percentile histogram, protocol wrapper functions. |
| `src/python_extension.c` | The CPython extension. Defines the `loadspiker.Engine` type and every method exposed to Python. |
| `src/protocols/tcp.c/.h` | TCP connection pool, connect/send/receive/disconnect. |
| `src/protocols/udp.c/.h` | UDP endpoint pool, create/send/receive/close. |
| `src/protocols/mqtt.c/.h` | Hand-rolled MQTT 3.1.1 packet encoder + connection pool. |
| `src/protocols/websocket.c/.h` | **Simulated** WebSocket (no real handshake yet — see §7). |
| `src/protocols/database.c/.h` | **Simulated** DB connector (parses connection strings, fakes query results). |
| `loadspiker/engine.py` | The `Engine` wrapper class + a pure-Python fallback used when the C extension is missing. |
| `loadspiker/scenarios.py` | Scenario builders (HTTP/REST/Website/TCP/UDP/MQTT/Database/Mixed) and `${var}` substitution. |
| `loadspiker/assertions.py`, `performance_assertions.py` | Response and aggregate-metric assertions. |
| `loadspiker/reporters.py` | Console/JSON/HTML/Multi reporters. |
| `loadspiker/session_manager.py`, `authentication.py` | Per-user session storage, cookie handling, auth flows. |
| `loadspiker/data_sources.py` | CSV-backed data with sequential/random/circular/unique strategies. |
| `cli.py` | Command-line entry point. |
| `tests/` | Pytest suite (the canonical one — `make test`). |
| `tests/tsan_check.c` | Standalone ThreadSanitizer stress harness (`make tsan`). |

---

## 3. Core data structures (`src/engine.h`)

- **`request_t` / `response_t`** — the generic, protocol-aware structs. Both end
  with a `union protocol_data` so a single fixed-size struct can carry
  WebSocket / TCP / UDP / MQTT / Database specifics without per-protocol
  allocation. The union’s size is dominated by `database_response_data_t`
  (it embeds a `result_set[MAX_BODY_LENGTH]`).
- **`http_request_t` / `http_response_t`** — legacy fixed HTTP structs still used
  by the request queue and the libcurl path. All character fields are fixed-size
  (`MAX_URL_LENGTH`, `MAX_HEADER_LENGTH`, `MAX_BODY_LENGTH`) and filled with
  bounded `strncpy`.
- **`metrics_t`** — counters plus a **latency histogram**:
  `histogram_buckets[HISTOGRAM_BUCKET_COUNT]` with 1 ms buckets covering 0–10 s
  and a final overflow bucket. p95/p99 are computed from the histogram in
  `engine_get_metrics`; RPS is wall-clock based (`test_start_time`).

**Why fixed buffers?** Predictable memory under high concurrency and no
per-request malloc on the hot path. The cost is hard caps (e.g. 64 KiB bodies)
and the need for careful bounds checks in the protocol encoders — see the
SECURITY_AUDIT.

---

## 4. Threading model (`src/engine.c`)

There are **two** kinds of worker threads:

1. **Pool workers** (`worker_thread_func`) — created in `engine_create`, one per
   `worker_threads`. They block on `queue_cond` until work arrives, and are
   *gated off* while a load test runs (`load_test_active`).
2. **Per-test workers** (`load_test_worker_func`) — spawned by
   `engine_start_load_test`, capped at `min(concurrent_users, num_requests)`.
   They drain the request queue and exit when it is empty or `stop_flag` is set.

### Synchronization primitives

| Field | Guarded by | Notes |
| ----- | ---------- | ----- |
| `metrics`, `histogram_buckets` | `metrics_mutex` | All metric updates go through `update_metrics()` / `engine_record_metrics()`. |
| `request_queue`, `queue_head/tail`, `load_test_active` | `queue_mutex` + `queue_cond` | Single ring buffer shared by both worker kinds. |
| `shutdown`, `worker.active` | `_Atomic` | Read in worker loops without the lock; written in `engine_destroy`. Atomicity prevents the torn-read race TSan used to flag. |
| `stop_flag` | `_Atomic int` | Cooperative cancel for per-test workers. |

**Lock ordering:** never hold `queue_mutex` and `metrics_mutex` at the same
time. `update_metrics` is always called *after* releasing `queue_mutex`.

**`engine_record_metrics`** is the public hook the extension uses to fold
protocol calls (TCP/UDP) that don’t flow through the HTTP queue into the same
metrics, under the same mutex.

Run `make tsan` after any change to this file — it is the fast feedback loop for
data races.

---

## 5. Protocol module contract

Every module in `src/protocols/` follows the same shape. If you add one, copy
this contract:

- A **fixed-size static pool** of connection structs guarded by a single
  module-level `pthread_mutex_t` (e.g. `tcp_pool_mutex`). Pool-full is reported
  once via a `*_warned` flag to avoid log spam.
- Public functions take primitive args + a `response_t*`, **own the mutex for
  the whole operation**, and `memset(response, 0, …)` + set `protocol` at the
  top. They time themselves with `get_time_us()`.
- They return `0`/`-1` *and* fill `response->success` + `status_code` +
  `error_message`; callers rely on the populated response, not just the int.
- A `*_cleanup_all()` that closes every fd and resets the pool count. It is
  called from `engine_destroy`.
- **Bounds-check any caller-supplied string before `memcpy`-ing it into a
  fixed stack buffer** (the MQTT encoders learned this the hard way — see
  SECURITY_AUDIT V1–V3).

---

## 6. The C ↔ Python boundary (`src/python_extension.c`)

This file is where most contributor mistakes happen. Rules:

1. **Reference counting.** `PyDict_SetItemString` does *not* steal a reference.
   Always insert through the local `dict_set(dict, key, value)` helper — it
   inserts and then `Py_DECREF`s the temporary. Building a dict with raw
   `PyDict_SetItemString(d, k, PyLong_FromLong(x))` leaks one object per call
   (this was a real, load-proportional leak — SECURITY_AUDIT V9).
2. **Strings.** Use `safe_str()` to turn C strings into `str`. It decodes UTF-8
   with `errors="replace"` so arbitrary protocol bytes never raise.
3. **The GIL.** Wrap every blocking C call in
   `Py_BEGIN_ALLOW_THREADS / Py_END_ALLOW_THREADS` so other Python threads run
   during network I/O. Do **not** touch any `PyObject` between those macros.
4. **Response dicts.** Use `build_response_dict()` for the common fields
   (`status_code`, `headers`, `body`, `response_time_us`, `response_time_ms`,
   `success`, `error_message`) and add a `protocol_data` sub-dict for
   protocol-specific fields.
5. **Argument parsing.** Keep `kwlist[]` names identical to the keyword names
   the Python `Engine` wrapper passes, and make sure the format string has
   exactly one specifier per argument (a mismatch raises `TypeError` at call
   time, not compile time).

### Adding a new engine method (checklist)

1. Implement the core logic in `src/engine.c` (or a protocol module) with a
   clean C signature.
2. Declare it in `src/engine.h`.
3. Add a `LoadTestEngine_<name>` function in `src/python_extension.c` and an
   entry in `LoadTestEngine_methods[]` (use the `KW_METH` macro for
   keyword methods).
4. Add a thin forwarding method on the `Engine` class in `loadspiker/engine.py`
   **and** a mirrored implementation in `_PythonEngine` (the fallback).
5. Add tests under `tests/`.
6. `make build && python3 setup.py build_ext --inplace --force && make test`.

---

## 7. Build, test, debug

### Building — read this first

There are **two** build paths and they are not interchangeable:

- **`make build`** compiles `obj/loadspiker.so` using whatever `python3-config`
  points at (often Homebrew Python). Good for a quick compile check.
- **`python3 setup.py build_ext --inplace`** compiles
  `loadspiker/loadspiker_c.cpython-<abi>.so` for the **interpreter that runs your
  tests**. This is the artifact Python actually imports.

> Gotcha: `pytest` imports the ABI-tagged `.so` next to the package. Always run
> `setup.py build_ext --inplace` (add `--force` after editing a `.h`, because
> setuptools does **not** track header dependencies and will otherwise reuse a
> stale `.o`). Stray `*.so` files from old builds can shadow your fresh one —
> delete them if imports look stale.

### Targets

| Command | What it does |
| ------- | ------------ |
| `make build` | Compile the C extension (`obj/loadspiker.so`). |
| `make debug` | Build with AddressSanitizer (`-fsanitize=address`). |
| `make tsan` | Build + run the ThreadSanitizer stress check. **Run after any `engine.c` change.** |
| `make test` | Install + run the pytest suite. |
| `make test-asan` | Rebuild with ASan and run the suite (memory-error/leak detection). |
| `make clean` | Remove build artifacts. |

### Debugging tips

- **Memory errors / leaks:** `make debug`, then run your script with
  `ASAN_OPTIONS=detect_leaks=1 python3 your_test.py`.
- **Data races:** `make tsan`. Extend `tests/tsan_check.c` to reproduce a
  suspected race under load.
- **Which engine am I on?** Importing `loadspiker` prints whether the C
  extension or the Python fallback loaded.

---

## 8. Known gaps & refactor TODO

Tracked, intentional debt. PRs welcome — each item links to the SECURITY_AUDIT
where relevant.

### Functional gaps
- [ ] **WebSocket is simulated.** `websocket.c` does `usleep`-based fake
      handshakes/sends, no real frames. Implement RFC 6455 or wire libcurl’s
      WebSocket API.
- [ ] **Database is simulated.** `database.c` parses connection strings and
      returns canned results; no real driver is linked.
- [ ] **Binary payloads for TCP/UDP.** `tcp_send`/`udp_send` use `strlen(data)`,
      so payloads with embedded NULs are truncated; the extension also marshals
      data as a `str`. Add length-aware (`y#`) send paths. (SECURITY_AUDIT V6)
- [ ] **Partial reads.** MQTT CONNACK/SUBACK reads are single `recv()` calls and
      assume the whole control packet arrives at once. (SECURITY_AUDIT V8)

### Cleanups
- [ ] **Dedup protocol pool boilerplate.** The find-or-create + pool-full logic
      is copy-pasted across `tcp.c`, `udp.c`, `mqtt.c`. Extract a shared helper
      or macro.
- [ ] **`_run_with_ramp_up`** in `engine.py` re-runs `start_load_test` in 5 s
      bursts with a `sleep(1)`; the ramp granularity is coarse. Consider driving
      ramp inside the C core.
- [ ] **Consolidate root-level `test_*.py` scripts.** ~17 ad-hoc scripts live in
      the repo root alongside the real `tests/` suite. Fold the useful ones into
      `tests/` and delete the rest.
- [ ] **`websocket.c` uses `gettimeofday`** (wall clock) while everything else
      uses `get_time_us()` (monotonic). Unify.

### Done in this pass (for reference)
- C extension now bridges **all** protocols (TCP/UDP/MQTT/Database) — previously
  only HTTP + WebSocket were exposed, so every other `engine.*` call raised
  `AttributeError` when the C extension was active.
- `run_scenario` now **executes non-HTTP scenarios under load** via
  `_run_protocol_load_test` + `_execute_operation`. Previously the load path
  only ran HTTP requests, so TCP/UDP/MQTT/Database/Mixed scenario operations
  were built but never executed.
- Reference-counting leak in every response/metrics dict fixed via `dict_set`.
- MQTT packet encoders bounds-checked (stack overflow class). (V1–V3)
- `shutdown`/`active` made atomic; TSan clean. (V4)
- libcurl request path de-triplicated into `http_execute()`.
- Dead, racy fd-based `engine_tcp_*`/`engine_udp_*` wrappers removed. (V5)
- TCP/UDP `receive` now return the actual payload (was a description string).
- Dead `response_queue` allocation removed. (V12)

---

## 9. Pull-request checklist

- [ ] `make build` is warning-clean.
- [ ] `python3 setup.py build_ext --inplace --force` succeeds.
- [ ] `make test` is green (207+ tests).
- [ ] `make tsan` is clean if you touched `engine.c` or any pool.
- [ ] New C↔Python code uses `dict_set` / `safe_str` and releases the GIL around
      blocking work.
- [ ] New behavior has a test in `tests/`.
- [ ] User-facing changes are reflected in the README and `docs/API.md`.
