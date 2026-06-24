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

| ID | Sev | Location | Issue | Suggested fix |
| -- | --- | -------- | ----- | ------------- |
| P1 | 🟠 | [data_sources.py:98-125](../loadspiker/data_sources.py#L98) | **Silent CSV type coercion corrupts string data.** `value.isdigit()`→int, `'.' in value`→float, `"true"/"false"`→bool. Leading-zero IDs (`"007"`→7), zip codes (`"01234"`→1234), version strings (`"1.10"`→1.1), `"false"`→bool. Data-driven request parameters are mangled with no opt-out. | Make coercion opt-in (`coerce_types=False` default), or never coerce values with leading zeros, or keep raw strings and let scenarios cast explicitly. |
| P2 | 🟡 | [authentication.py:440-500](../loadspiker/authentication.py#L440) | OAuth2 `state` is generated and stored but **never validated** on code exchange — the CSRF value is unused. | Compare returned `state` against `session.get('oauth2_state')` before exchanging the code. |
| P3 | 🟡 | [authentication.py:193](../loadspiker/authentication.py#L193) | Bearer `_fetch_token_from_endpoint` returns the **full `token_response`** (access + refresh tokens) in its result dict; logging the result leaks secrets. OAuth2 flow truncates its token (inconsistent). | Drop or redact `token_response` from the returned dict; expose only metadata (`expires_in`, `has_refresh_token`). |
| P4 | 🟡 | [reporters.py:233](../loadspiker/reporters.py#L233) | HTMLReporter embeds `json.dumps(progress_data)` in a `<script>` block and metrics via f-string. **Currently safe** (only numeric data flows in), but no escaping / `</script>` handling — latent XSS if any string field (URL/error/body) is ever added to the report. | Escape with `</` → `<\/` in the JSON dump and HTML-escape any string fields before interpolation, as defense-in-depth. |
| P5 | 🟡 | [cli.py:152-167](../cli.py#L152) | Config access `config['base_url']` / `req_config['url']` is unguarded → a missing key surfaces as a generic "Test failed" rather than a clear message. | Validate required keys and emit a specific error. |

**Verified clean:** `session_manager.py` (properly `RLock`-guarded, no lock
inversion); no `eval`/`exec`/`pickle`/`yaml.load`/`shell=True`/`verify=False`
anywhere; `parse_load_pattern` only does `int()` parsing; assertions modules
have no risky patterns.

---

## 2. C audit — still open

From [SECURITY_AUDIT.md](SECURITY_AUDIT.md). None are memory-safety holes.

- [ ] 🟠 **V6 — binary payload truncation.** `tcp_send`/`udp_send` use
      `strlen(data)`; the extension marshals `data` as a `str`. Payloads with
      embedded NULs are truncated. Needs length-carrying (`y#`) marshalling and
      signature changes through to the protocol functions.
- [ ] 🟡 **V8 — MQTT control-packet partial reads.** CONNACK/SUBACK/UNSUBACK use
      a single `recv()`; a split TCP segment yields a false failure. Add a
      read-to-length loop.
- [ ] 🟡 **V11 — UDP re-`bind()` on every receive.** `udp_receive` still calls
      `bind()` each call (best-effort, ignored after the first). Bind once at
      endpoint creation.
- [ ] 🟡 **V14 — DB result aliases the union via `char[]` cast.** Benign today
      (union is large enough) but fragile; write through the named union member.

---

## 3. Concurrency / performance follow-ups

- [ ] 🟠 **MQTT & Database lock narrowing.** TCP/UDP now release the pool mutex
      during blocking I/O; MQTT (`mqtt_connect` blocking `connect`/`recv`) and
      Database (`usleep` under `db_pool_mutex`) still hold their pool mutex
      across the whole operation, serializing those protocols process-wide.
      Apply the same find/reserve-then-unlock pattern.
- [ ] 🟡 **Per-user Database isolation.** DB connections are keyed by
      `connection_string`, shared across virtual users; one user's disconnect
      flips `is_connected` for all. (Simulated backend, so low impact today.)

---

## 4. Functional gaps

- [ ] 🔴 **WebSocket is simulated.** `websocket.c` does `usleep`-based fake
      handshakes/sends — no real RFC 6455 frames. Implement real WS (or wire
      libcurl's WebSocket API).
- [ ] 🔴 **Database is simulated.** `database.c` parses connection strings and
      returns canned results; no real driver is linked.
- [ ] 🟡 `websocket.c` uses `gettimeofday` (wall clock) while everything else
      uses `get_time_us()` (monotonic). Unify.

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

- [ ] 🟠 **Run AddressSanitizer.** `make test-asan` has not been run this pass;
      the V1–V3/V9 fixes were verified by code review + tests, not by ASan.
- [ ] 🟡 **Regression tests for security fixes.** Add tests for MQTT over-length
      rejection (V1–V3), the refcount-leak fix (V9), and ephemeral UDP port.
- [ ] 🟡 **CI.** No CI config; add one that runs `make test` + `make tsan`.

---

## 7. Documentation reconciliation

- [ ] 🟠 **`docs/site/*.html` is stale.** The static site still presents
      WebSocket/Database/protocol support as fully working; reconcile with the
      capability matrix in the [README](../README.md).
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
