#!/usr/bin/env python3
"""
Simple LoadSpiker example
"""

from loadspiker import Engine, Scenario
from loadspiker.reporters import ConsoleReporter

def main():
    # Create engine
    engine = Engine(max_connections=100, worker_threads=4)
    
    # Create simple scenario
    scenario = Scenario("Simple HTTP Test")
    scenario.get("https://httpbin.org/get")
    scenario.get("https://httpbin.org/status/200")
    scenario.post("https://httpbin.org/post", body='{"test": "data"}')
    
    # Set up reporting
    reporter = ConsoleReporter()
    reporter.start_reporting()
    
    try:
        print("🚀 Starting load test...")
        
        # Run the test
        results = engine.run_scenario(
            scenario=scenario,
            users=10,
            duration=30,
            ramp_up_duration=5
        )
        
        # Report results
        reporter.report_metrics(results)
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted")
    finally:
        reporter.end_reporting()

if __name__ == '__main__':
    main()
