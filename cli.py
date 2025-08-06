#!/usr/bin/env python3
"""
LoadSpiker - High-performance load testing tool
Command-line interface
"""

import argparse
import json
import sys
import time
import importlib.util
from pathlib import Path
from typing import Dict, Any, Optional

from loadspiker import Engine
try:
    from loadspiker import Scenario, RESTAPIScenario, WebsiteScenario
    from loadspiker.scenarios import HTTPRequest
    from loadspiker.reporters import ConsoleReporter, JSONReporter, HTMLReporter, MultiReporter
    from loadspiker.utils import parse_load_pattern, ramp_up, constant_load
    _full_features_available = True
except ImportError:
    # Fallback for when full scenario modules are not available
    _full_features_available = False
    
    # Create minimal implementations for CLI functionality
    class Scenario:
        def __init__(self, name="Basic Test"):
            self.name = name
            self.requests = []
        
        def add_request(self, request):
            self.requests.append(request)
            
        def set_variable(self, name, value):
            pass
            
        def build_requests(self):
            return [{"url": req.url, "method": req.method, "headers": "", "body": req.body, "timeout_ms": req.timeout_ms} 
                   for req in self.requests]
    
    class RESTAPIScenario(Scenario):
        def __init__(self, base_url, name="REST API Test"):
            super().__init__(name)
            self.base_url = base_url
    
    class WebsiteScenario(Scenario):
        def __init__(self, base_url, name="Website Test"):
            super().__init__(name)
            self.base_url = base_url
            
    class HTTPRequest:
        def __init__(self, url, method="GET", headers=None, body="", timeout_ms=30000):
            self.url = url
            self.method = method
            self.headers = headers or {}
            self.body = body
            self.timeout_ms = timeout_ms
    
    class ConsoleReporter:
        def __init__(self, show_progress=True, progress_interval=5):
            self.show_progress = show_progress
            self.progress_interval = progress_interval
            self.start_time = None
            
        def start_reporting(self):
            import time
            self.start_time = time.time()
            
        def report_progress(self, elapsed_time, metrics):
            if self.show_progress:
                print(f"⏱️  {elapsed_time:.1f}s - Requests: {metrics.get('total_requests', 0)}")
                
        def report_metrics(self, metrics):
            print("\n📊 Test Results:")
            print(f"   Total requests: {metrics.get('total_requests', 0)}")
            print(f"   Successful: {metrics.get('successful_requests', 0)}")
            print(f"   Failed: {metrics.get('failed_requests', 0)}")
            print(f"   Avg response time: {metrics.get('avg_response_time_ms', 0):.2f} ms")
            print(f"   Requests/sec: {metrics.get('requests_per_second', 0):.2f}")
            
        def end_reporting(self):
            pass
    
    class JSONReporter:
        def __init__(self, filename):
            self.filename = filename
            
        def start_reporting(self): pass
        def report_progress(self, elapsed_time, metrics): pass
        def end_reporting(self): pass
        
        def report_metrics(self, metrics):
            import json
            with open(self.filename, 'w') as f:
                json.dump(metrics, f, indent=2)
                
    class HTMLReporter:
        def __init__(self, filename):
            self.filename = filename
            
        def start_reporting(self): pass
        def report_progress(self, elapsed_time, metrics): pass
        def end_reporting(self): pass
        def report_metrics(self, metrics): pass
    
    class MultiReporter:
        def __init__(self, reporters):
            self.reporters = reporters
            
        def start_reporting(self):
            for reporter in self.reporters:
                reporter.start_reporting()
                
        def report_progress(self, elapsed_time, metrics):
            for reporter in self.reporters:
                reporter.report_progress(elapsed_time, metrics)
                
        def report_metrics(self, metrics):
            for reporter in self.reporters:
                reporter.report_metrics(metrics)
                
        def end_reporting(self):
            for reporter in self.reporters:
                reporter.end_reporting()
    
    def parse_load_pattern(pattern):
        # Simple pattern parsing fallback
        return [(10, 60)]  # Default pattern


def load_scenario_from_file(scenario_file: str) -> Scenario:
    """Load scenario from Python file"""
    spec = importlib.util.spec_from_file_location("scenario", scenario_file)
    scenario_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario_module)
    
    if hasattr(scenario_module, 'scenario'):
        return scenario_module.scenario
    elif hasattr(scenario_module, 'create_scenario'):
        return scenario_module.create_scenario()
    else:
        raise ValueError("Scenario file must define 'scenario' variable or 'create_scenario()' function")


def create_scenario_from_config(config: Dict[str, Any]) -> Scenario:
    """Create scenario from configuration dictionary"""
    scenario_type = config.get('type', 'basic')
    
    if scenario_type == 'rest_api':
        base_url = config['base_url']
        scenario = RESTAPIScenario(base_url, config.get('name', 'REST API Test'))
    elif scenario_type == 'website':
        base_url = config['base_url']
        scenario = WebsiteScenario(base_url, config.get('name', 'Website Test'))
    else:
        scenario = Scenario(config.get('name', 'Load Test'))
    
    # Add requests from config
    for req_config in config.get('requests', []):
        url = req_config['url']
        method = req_config.get('method', 'GET')
        headers = req_config.get('headers', {})
        body = req_config.get('body', '')
        timeout_ms = req_config.get('timeout_ms', 30000)
        
        scenario.add_request(HTTPRequest(url, method, headers, body, timeout_ms))
    
    # Set variables
    for name, value in config.get('variables', {}).items():
        scenario.set_variable(name, value)
    
    return scenario


def run_interactive_mode(engine: Engine):
    """Run in interactive mode for testing individual requests"""
    print("🔧 Interactive Mode - Type 'help' for commands, 'quit' to exit")
    
    while True:
        try:
            command = input("loadtest> ").strip()
            
            if command.lower() in ['quit', 'exit', 'q']:
                break
            elif command.lower() == 'help':
                print("Available commands:")
                print("  get <url>                    - Execute GET request")
                print("  post <url> <body>           - Execute POST request")
                print("  metrics                     - Show current metrics")
                print("  reset                       - Reset metrics")
                print("  quit                        - Exit interactive mode")
            elif command.lower() == 'metrics':
                metrics = engine.get_metrics()
                reporter = ConsoleReporter()
                reporter.report_metrics(metrics)
            elif command.lower() == 'reset':
                engine.reset_metrics()
                print("✅ Metrics reset")
            elif command.startswith('get '):
                url = command[4:].strip()
                if url:
                    print(f"🔄 GET {url}")
                    response = engine.execute_request(url)
                    print(f"Status: {response['status_code']}")
                    print(f"Time: {response['response_time_us'] / 1000:.2f} ms")
                    if response['body'][:200]:
                        print(f"Body: {response['body'][:200]}...")
            elif command.startswith('post '):
                parts = command[5:].split(' ', 1)
                if len(parts) >= 1:
                    url = parts[0]
                    body = parts[1] if len(parts) > 1 else ""
                    print(f"🔄 POST {url}")
                    response = engine.execute_request(url, method="POST", body=body)
                    print(f"Status: {response['status_code']}")
                    print(f"Time: {response['response_time_us'] / 1000:.2f} ms")
            else:
                print("❌ Unknown command. Type 'help' for available commands.")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("👋 Exiting interactive mode")


def main():
    parser = argparse.ArgumentParser(
        description="LoadSpiker - High-performance load testing tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick URL test
  loadspiker https://api.example.com/health -u 10 -d 30
  
  # Test with scenario file
  loadspiker -s scenario.py -u 50 -d 60
  
  # Test with configuration file
  loadspiker -c config.json -u 20 -d 120
  
  # Interactive mode
  loadspiker -i
  
  # Advanced load pattern
  loadspiker https://api.example.com -p "ramp:1:50:60" --html report.html
        """
    )
    
    # Target specification
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument('url', nargs='?', help='Target URL for simple tests')
    target_group.add_argument('-s', '--scenario', help='Python scenario file')
    target_group.add_argument('-c', '--config', help='JSON configuration file')
    target_group.add_argument('-i', '--interactive', action='store_true', help='Interactive mode')
    
    # Load parameters
    parser.add_argument('-u', '--users', type=int, default=10, help='Number of concurrent users (default: 10)')
    parser.add_argument('-d', '--duration', type=int, default=60, help='Test duration in seconds (default: 60)')
    parser.add_argument('-r', '--ramp-up', type=int, default=0, help='Ramp-up duration in seconds (default: 0)')
    parser.add_argument('-p', '--pattern', help='Load pattern (e.g., "ramp:1:100:60", "constant:50:120")')
    
    # Engine configuration
    parser.add_argument('--max-connections', type=int, default=1000, help='Max connections (default: 1000)')
    parser.add_argument('--threads', type=int, default=10, help='Worker threads (default: 10)')
    
    # Request configuration
    parser.add_argument('-m', '--method', default='GET', help='HTTP method (default: GET)')
    parser.add_argument('-H', '--header', action='append', help='HTTP header (can be used multiple times)')
    parser.add_argument('-b', '--body', help='Request body')
    parser.add_argument('-t', '--timeout', type=int, default=30000, help='Request timeout in ms (default: 30000)')
    
    # Output options
    parser.add_argument('--json', help='Save results to JSON file')
    parser.add_argument('--html', help='Save results to HTML file')
    parser.add_argument('-q', '--quiet', action='store_true', help='Suppress progress output')
    parser.add_argument('--no-progress', action='store_true', help='Disable progress reporting')
    
    args = parser.parse_args()
    
    # Validate arguments
    if not any([args.url, args.scenario, args.config, args.interactive]):
        parser.error("Must specify URL, scenario file, config file, or interactive mode")
    
    # Create engine
    print(f"🚀 Initializing engine (connections: {args.max_connections}, threads: {args.threads})")
    engine = Engine(max_connections=args.max_connections, worker_threads=args.threads)
    
    # Check if we have the Python wrapper or raw C extension
    has_run_scenario = hasattr(engine, 'run_scenario')
    if not has_run_scenario:
        # Create a compatibility wrapper class for the CLI
        class EngineWrapper:
            def __init__(self, engine):
                self._engine = engine
                
            def __getattr__(self, name):
                return getattr(self._engine, name)
                
            def run_scenario(self, scenario, users=10, duration=60, ramp_up_duration=0):
                requests = scenario.build_requests()
                return self._engine.start_load_test(
                    requests=requests,
                    concurrent_users=users,
                    duration_seconds=duration
                )
        
        engine = EngineWrapper(engine)
    
    # Interactive mode
    if args.interactive:
        run_interactive_mode(engine)
        return
    
    # Create scenario
    if args.scenario:
        scenario = load_scenario_from_file(args.scenario)
    elif args.config:
        with open(args.config, 'r') as f:
            config = json.load(f)
        scenario = create_scenario_from_config(config)
    else:
        # Simple URL test
        scenario = Scenario("Simple URL Test")
        
        # Parse headers
        headers = {}
        if args.header:
            for header in args.header:
                if ':' in header:
                    key, value = header.split(':', 1)
                    headers[key.strip()] = value.strip()
        
        scenario.add_request(HTTPRequest(
            url=args.url,
            method=args.method,
            headers=headers,
            body=args.body or "",
            timeout_ms=args.timeout
        ))
    
    # Create reporters
    reporters = []
    if not args.quiet:
        console_reporter = ConsoleReporter(
            show_progress=not args.no_progress,
            progress_interval=5
        )
        reporters.append(console_reporter)
    
    if args.json:
        reporters.append(JSONReporter(args.json))
    
    if args.html:
        reporters.append(HTMLReporter(args.html))
    
    if not reporters:
        reporters.append(ConsoleReporter())
    
    reporter = MultiReporter(reporters) if len(reporters) > 1 else reporters[0]
    
    # Start reporting
    reporter.start_reporting()
    
    try:
        # Determine load pattern
        if args.pattern:
            load_pattern = parse_load_pattern(args.pattern)
            
            for users, duration in load_pattern:
                print(f"📊 Running {users} users for {duration} seconds...")
                
                if args.ramp_up > 0:
                    engine.run_scenario(scenario, users, duration, args.ramp_up)
                else:
                    engine.run_scenario(scenario, users, duration)
                
                # Report progress
                elapsed_time = time.time() - reporter.start_time
                metrics = engine.get_metrics()
                reporter.report_progress(elapsed_time, metrics)
                
        else:
            # Single test run
            print(f"📊 Running {args.users} users for {args.duration} seconds...")
            
            if args.ramp_up > 0:
                print(f"🔄 Ramp-up: {args.ramp_up} seconds")
                engine.run_scenario(scenario, args.users, args.duration, args.ramp_up)
            else:
                engine.run_scenario(scenario, args.users, args.duration)
        
        # Final results
        final_metrics = engine.get_metrics()
        reporter.report_metrics(final_metrics)
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        final_metrics = engine.get_metrics()
        if final_metrics.get('total_requests', 0) > 0:
            reporter.report_metrics(final_metrics)
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)
    finally:
        reporter.end_reporting()


if __name__ == '__main__':
    main()
