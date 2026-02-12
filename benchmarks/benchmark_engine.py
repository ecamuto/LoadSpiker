#!/usr/bin/env python3
"""
LoadSpiker Performance Benchmark Suite
=======================================

Automated benchmarks for measuring engine performance including:
- Engine creation/destruction overhead
- HTTP request throughput
- Metrics collection overhead
- Protocol operation latency
- Memory usage patterns
"""

import sys
import os
import time
import statistics

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine


def benchmark(name, func, iterations=1000, warmup=10):
    """Run a benchmark and report results."""
    # Warmup
    for _ in range(warmup):
        func()

    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = time.perf_counter() - start
        times.append(elapsed * 1_000_000)  # Convert to microseconds

    avg = statistics.mean(times)
    med = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95)]
    p99 = sorted(times)[int(len(times) * 0.99)]
    ops_per_sec = 1_000_000 / avg if avg > 0 else float('inf')

    print(f"  {name}:")
    print(f"    Iterations: {iterations}")
    print(f"    Avg: {avg:.2f} µs | Median: {med:.2f} µs")
    print(f"    P95: {p95:.2f} µs | P99: {p99:.2f} µs")
    print(f"    Throughput: {ops_per_sec:,.0f} ops/s")
    print()
    return avg


def benchmark_engine_lifecycle():
    """Benchmark engine creation and destruction."""
    print("=" * 60)
    print("ENGINE LIFECYCLE BENCHMARKS")
    print("=" * 60)

    def create_destroy():
        e = Engine(max_connections=10, worker_threads=2)
        del e

    benchmark("Engine create + destroy (10 conn, 2 threads)", create_destroy, iterations=100, warmup=5)

    def create_destroy_large():
        e = Engine(max_connections=100, worker_threads=8)
        del e

    benchmark("Engine create + destroy (100 conn, 8 threads)", create_destroy_large, iterations=50, warmup=3)


def benchmark_metrics():
    """Benchmark metrics operations."""
    print("=" * 60)
    print("METRICS BENCHMARKS")
    print("=" * 60)

    engine = Engine(max_connections=10, worker_threads=2)

    benchmark("get_metrics()", lambda: engine.get_metrics(), iterations=10000)
    benchmark("reset_metrics()", lambda: engine.reset_metrics(), iterations=10000)

    del engine


def benchmark_database_simulated():
    """Benchmark simulated database operations (no network)."""
    print("=" * 60)
    print("SIMULATED DATABASE BENCHMARKS (no network I/O)")
    print("=" * 60)

    engine = Engine(max_connections=10, worker_threads=2)

    def db_connect_disconnect():
        engine.database_connect("mysql://user:pass@localhost/db", "mysql")
        engine.database_disconnect("mysql://user:pass@localhost/db")

    benchmark("DB connect + disconnect (simulated)", db_connect_disconnect, iterations=1000)

    engine.database_connect("mysql://user:pass@localhost/db", "mysql")

    def db_query():
        engine.database_query("mysql://user:pass@localhost/db", "SELECT * FROM users")

    benchmark("DB query (simulated, after connect)", db_query, iterations=1000)

    del engine


def benchmark_websocket_simulated():
    """Benchmark simulated WebSocket operations."""
    print("=" * 60)
    print("SIMULATED WEBSOCKET BENCHMARKS (no network I/O)")
    print("=" * 60)

    engine = Engine(max_connections=10, worker_threads=2)

    def ws_lifecycle():
        engine.websocket_connect("ws://echo.websocket.org")
        engine.websocket_send("ws://echo.websocket.org", "Hello!")
        engine.websocket_close("ws://echo.websocket.org")

    benchmark("WS connect + send + close (simulated)", ws_lifecycle, iterations=500)

    del engine


def benchmark_http_request():
    """Benchmark actual HTTP requests (requires network)."""
    print("=" * 60)
    print("HTTP REQUEST BENCHMARKS (requires network)")
    print("=" * 60)

    engine = Engine(max_connections=10, worker_threads=2)

    def http_get():
        engine.execute_request(url="http://example.com", method="GET", timeout_ms=10000)

    try:
        # Quick connectivity check
        resp = engine.execute_request(url="http://example.com", method="GET", timeout_ms=5000)
        if not resp.get('success', False):
            print("  ⚠️  Network unavailable, skipping HTTP benchmarks")
            del engine
            return

        benchmark("HTTP GET http://example.com", http_get, iterations=20, warmup=2)

    except Exception as e:
        print(f"  ⚠️  HTTP benchmark skipped: {e}")

    del engine


def benchmark_metrics_accumulation():
    """Benchmark metrics accumulation under load."""
    print("=" * 60)
    print("METRICS ACCUMULATION BENCHMARK")
    print("=" * 60)

    engine = Engine(max_connections=10, worker_threads=2)
    engine.reset_metrics()

    iterations = 2000
    start = time.perf_counter()

    for _ in range(iterations):
        engine.database_connect("mysql://user:pass@localhost/db", "mysql")
        engine.database_disconnect("mysql://user:pass@localhost/db")

    elapsed = time.perf_counter() - start
    metrics = engine.get_metrics()

    print(f"  {iterations * 2} operations in {elapsed:.3f}s")
    print(f"  Throughput: {(iterations * 2) / elapsed:,.0f} ops/s")
    print(f"  Total requests tracked: {metrics.get('total_requests', 0)}")
    print(f"  Successful: {metrics.get('successful_requests', 0)}")
    print(f"  Failed: {metrics.get('failed_requests', 0)}")
    print()

    del engine


def main():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        LoadSpiker Performance Benchmark Suite           ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    benchmark_engine_lifecycle()
    benchmark_metrics()
    benchmark_database_simulated()
    benchmark_websocket_simulated()
    benchmark_metrics_accumulation()
    benchmark_http_request()

    print("=" * 60)
    print("ALL BENCHMARKS COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    main()