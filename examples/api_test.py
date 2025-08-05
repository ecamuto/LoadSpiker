#!/usr/bin/env python3
"""
REST API load testing example
"""

from loadspiker import Engine, RESTAPIScenario
from loadspiker.reporters import ConsoleReporter, HTMLReporter, MultiReporter

def main():
    # Create engine
    engine = Engine(max_connections=200, worker_threads=8)
    
    # Create REST API scenario
    scenario = RESTAPIScenario("https://jsonplaceholder.typicode.com", "JSONPlaceholder API Test")
    
    # Add API calls
    scenario.get_resource("posts/1")
    scenario.get_resource("posts")
    scenario.create_resource("posts", {
        "title": "Load Test Post",
        "body": "This is a test post from LoadSpiker",
        "userId": 1
    })
    scenario.update_resource("posts/1", {
        "id": 1,
        "title": "Updated Post",
        "body": "Updated content",
        "userId": 1
    })
    scenario.delete_resource("posts/1")
    
    # Set up multiple reporters
    console_reporter = ConsoleReporter(show_progress=True)
    html_reporter = HTMLReporter("api_test_report.html")
    reporter = MultiReporter([console_reporter, html_reporter])
    
    reporter.start_reporting()
    
    try:
        print("🚀 Starting API load test...")
        
        # Run the test with gradual ramp-up
        results = engine.run_scenario(
            scenario=scenario,
            users=25,
            duration=60,
            ramp_up_duration=15
        )
        
        # Report results
        reporter.report_metrics(results)
        
        print(f"\n📊 Final Results Summary:")
        print(f"Total Requests: {results['total_requests']:,}")
        print(f"Success Rate: {(results['successful_requests'] / results['total_requests'] * 100):.1f}%")
        print(f"Average Response Time: {results['avg_response_time_ms']:.2f} ms")
        print(f"Requests per Second: {results['requests_per_second']:.2f}")
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted")
    finally:
        reporter.end_reporting()

if __name__ == '__main__':
    main()
