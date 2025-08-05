#!/usr/bin/env python3
"""
Stress testing example with multiple load patterns
"""

from loadspiker import Engine, Scenario
from loadspiker.reporters import ConsoleReporter, JSONReporter, MultiReporter
from loadspiker.utils import stress_test, spike_test, ramp_up
import time

def create_stress_scenario():
    """Create a scenario that simulates realistic user behavior"""
    scenario = Scenario("Stress Test Scenario")
    
    # Homepage
    scenario.get("https://httpbin.org/get")
    
    # Simulate user browsing
    scenario.get("https://httpbin.org/status/200")
    scenario.get("https://httpbin.org/json")
    
    # API interactions
    scenario.post("https://httpbin.org/post", body='{"action": "search", "query": "test"}')
    scenario.get("https://httpbin.org/cache/60")  # Cached content
    
    # Heavy operations
    scenario.get("https://httpbin.org/delay/1")  # Slow endpoint
    
    return scenario

def run_load_pattern(engine, scenario, pattern_name, load_generator, reporter):
    """Run a specific load pattern"""
    print(f"\n🔥 Starting {pattern_name}...")
    reporter.reset_metrics()
    
    for users, duration in load_generator:
        print(f"   📊 {users} users for {duration} seconds")
        engine.run_scenario(scenario, users, duration)
        
        # Show intermediate results
        metrics = engine.get_metrics()
        print(f"   ⏱️  RPS: {metrics['requests_per_second']:.1f}, "
              f"Avg: {metrics['avg_response_time_ms']:.1f}ms, "
              f"Success: {(metrics['successful_requests']/max(metrics['total_requests'], 1)*100):.1f}%")
        
        time.sleep(1)  # Brief pause between load steps
    
    final_metrics = engine.get_metrics()
    print(f"✅ {pattern_name} completed")
    return final_metrics

def main():
    # Create high-performance engine for stress testing
    engine = Engine(max_connections=500, worker_threads=16)
    scenario = create_stress_scenario()
    
    # Set up reporting
    console_reporter = ConsoleReporter(show_progress=False)
    json_reporter = JSONReporter("stress_test_results.json")
    reporter = MultiReporter([console_reporter, json_reporter])
    
    reporter.start_reporting()
    
    all_results = {}
    
    try:
        print("🚀 Starting comprehensive stress test...")
        print("This will run multiple load patterns to test system limits")
        
        # 1. Warm-up phase
        print("\n🔥 Phase 1: Warm-up")
        engine.run_scenario(scenario, users=5, duration=30)
        
        # 2. Gradual ramp-up
        ramp_results = run_load_pattern(
            engine, scenario, "Ramp-up Test", 
            ramp_up(1, 50, 120), reporter
        )
        all_results['ramp_up'] = ramp_results
        
        # Reset and wait
        engine.reset_metrics()
        time.sleep(10)
        
        # 3. Stress test - increasing load
        stress_results = run_load_pattern(
            engine, scenario, "Stress Test",
            stress_test(max_users=100, step_size=10, step_duration=20),
            reporter
        )
        all_results['stress'] = stress_results
        
        # Reset and wait
        engine.reset_metrics()
        time.sleep(10)
        
        # 4. Spike test
        spike_results = run_load_pattern(
            engine, scenario, "Spike Test",
            spike_test(normal_users=20, spike_users=80, normal_duration=60, spike_duration=30),
            reporter
        )
        all_results['spike'] = spike_results
        
        # Final summary
        print("\n" + "="*60)
        print("📊 STRESS TEST SUMMARY")
        print("="*60)
        
        for test_name, results in all_results.items():
            success_rate = (results['successful_requests'] / max(results['total_requests'], 1)) * 100
            print(f"\n{test_name.upper()}:")
            print(f"  Total Requests: {results['total_requests']:,}")
            print(f"  Success Rate: {success_rate:.1f}%")
            print(f"  Avg Response Time: {results['avg_response_time_ms']:.2f} ms")
            print(f"  Max Response Time: {results['max_response_time_us']/1000:.2f} ms")
            print(f"  Requests/sec: {results['requests_per_second']:.2f}")
            
            if success_rate >= 95:
                print(f"  Status: 🟢 EXCELLENT")
            elif success_rate >= 90:
                print(f"  Status: 🟡 GOOD")
            elif success_rate >= 80:
                print(f"  Status: 🟠 FAIR")
            else:
                print(f"  Status: 🔴 POOR - System may be overloaded")
        
        # Overall assessment
        overall_success = sum(r['successful_requests'] for r in all_results.values())
        overall_total = sum(r['total_requests'] for r in all_results.values())
        overall_rate = (overall_success / max(overall_total, 1)) * 100
        
        print(f"\nOVERALL SYSTEM PERFORMANCE:")
        print(f"  Combined Success Rate: {overall_rate:.1f}%")
        print(f"  Total Requests Processed: {overall_total:,}")
        
        if overall_rate >= 95:
            print("  🎉 System handles stress very well!")
        elif overall_rate >= 90:
            print("  ✅ System performs well under stress")
        elif overall_rate >= 80:
            print("  ⚠️  System shows some stress under high load")
        else:
            print("  🚨 System struggles under heavy load - investigate bottlenecks")
        
    except KeyboardInterrupt:
        print("\n⏹️  Stress test interrupted")
        current_metrics = engine.get_metrics()
        if current_metrics.get('total_requests', 0) > 0:
            reporter.report_metrics(current_metrics)
    finally:
        reporter.end_reporting()

if __name__ == '__main__':
    main()
