"""
Result reporting and visualization utilities
"""

import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime


class BaseReporter:
    """Base class for test result reporters"""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        
    def start_reporting(self):
        """Called when test starts"""
        self.start_time = time.time()
    
    def end_reporting(self):
        """Called when test ends"""
        self.end_time = time.time()
    
    def report_metrics(self, metrics: Dict[str, Any]):
        """Report test metrics"""
        raise NotImplementedError
    
    def report_progress(self, elapsed_time: float, metrics: Dict[str, Any]):
        """Report progress during test execution"""
        pass


class ConsoleReporter(BaseReporter):
    """Reporter that outputs results to console"""
    
    def __init__(self, show_progress: bool = True, progress_interval: int = 10):
        super().__init__()
        self.show_progress = show_progress
        self.progress_interval = progress_interval
        self.last_progress_time = 0
        
    def start_reporting(self):
        super().start_reporting()
        print("🚀 Load test started...")
        print("=" * 60)
        
    def end_reporting(self):
        super().end_reporting()
        duration = self.end_time - self.start_time if self.start_time else 0
        print("=" * 60)
        print(f"✅ Load test completed in {duration:.2f} seconds")
        
    def report_metrics(self, metrics: Dict[str, Any]):
        """Print formatted metrics to console"""
        print("\n📊 Final Test Results")
        print("=" * 40)
        
        # Request statistics
        total = metrics.get('total_requests', 0)
        successful = metrics.get('successful_requests', 0)
        failed = metrics.get('failed_requests', 0)
        success_rate = (successful / total * 100) if total > 0 else 0
        
        print(f"Total Requests:     {total:,}")
        print(f"Successful:         {successful:,}")
        print(f"Failed:             {failed:,}")
        print(f"Success Rate:       {success_rate:.2f}%")
        
        # Performance metrics
        print(f"\nRequests/sec:       {metrics.get('requests_per_second', 0):.2f}")
        print(f"Avg Response Time:  {metrics.get('avg_response_time_ms', 0):.2f} ms")
        print(f"Min Response Time:  {metrics.get('min_response_time_us', 0) / 1000:.2f} ms")
        print(f"Max Response Time:  {metrics.get('max_response_time_us', 0) / 1000:.2f} ms")
        
        # Status indicators
        if success_rate >= 95:
            print("🟢 Test Status: EXCELLENT")
        elif success_rate >= 90:
            print("🟡 Test Status: GOOD")
        elif success_rate >= 80:
            print("🟠 Test Status: FAIR")
        else:
            print("🔴 Test Status: POOR")
            
    def report_progress(self, elapsed_time: float, metrics: Dict[str, Any]):
        """Show progress updates during test"""
        if not self.show_progress:
            return
            
        current_time = time.time()
        if current_time - self.last_progress_time < self.progress_interval:
            return
            
        self.last_progress_time = current_time
        
        total = metrics.get('total_requests', 0)
        rps = metrics.get('requests_per_second', 0)
        avg_time = metrics.get('avg_response_time_ms', 0)
        
        print(f"⏱️  {elapsed_time:.0f}s | Requests: {total:,} | RPS: {rps:.1f} | Avg: {avg_time:.1f}ms")


class JSONReporter(BaseReporter):
    """Reporter that outputs results to JSON file"""
    
    def __init__(self, output_file: str):
        super().__init__()
        self.output_file = output_file
        self.test_data = {
            'test_info': {},
            'progress': [],
            'final_metrics': {}
        }
        
    def start_reporting(self):
        super().start_reporting()
        self.test_data['test_info'] = {
            'start_time': datetime.fromtimestamp(self.start_time).isoformat(),
            'start_timestamp': self.start_time
        }
        
    def end_reporting(self):
        super().end_reporting()
        self.test_data['test_info'].update({
            'end_time': datetime.fromtimestamp(self.end_time).isoformat(),
            'end_timestamp': self.end_time,
            'duration_seconds': self.end_time - self.start_time
        })
        
    def report_metrics(self, metrics: Dict[str, Any]):
        """Save final metrics to JSON"""
        self.test_data['final_metrics'] = metrics
        
        with open(self.output_file, 'w') as f:
            json.dump(self.test_data, f, indent=2)
            
        print(f"📄 Results saved to: {self.output_file}")
        
    def report_progress(self, elapsed_time: float, metrics: Dict[str, Any]):
        """Save progress data"""
        progress_entry = {
            'elapsed_time': elapsed_time,
            'timestamp': time.time(),
            'metrics': metrics.copy()
        }
        self.test_data['progress'].append(progress_entry)


class HTMLReporter(BaseReporter):
    """Reporter that generates HTML report with charts"""
    
    def __init__(self, output_file: str):
        super().__init__()
        self.output_file = output_file
        self.progress_data: List[Dict[str, Any]] = []
        
    def report_progress(self, elapsed_time: float, metrics: Dict[str, Any]):
        """Collect progress data for charts"""
        self.progress_data.append({
            'time': elapsed_time,
            'requests_per_second': metrics.get('requests_per_second', 0),
            'avg_response_time': metrics.get('avg_response_time_ms', 0),
            'total_requests': metrics.get('total_requests', 0)
        })
        
    def report_metrics(self, metrics: Dict[str, Any]):
        """Generate HTML report"""
        duration = self.end_time - self.start_time if self.start_time else 0
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Load Test Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background: #f5f5f5; padding: 20px; border-radius: 8px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 20px 0; }}
        .metric {{ background: white; padding: 15px; border: 1px solid #ddd; border-radius: 4px; }}
        .metric h3 {{ margin-top: 0; color: #333; }}
        .metric .value {{ font-size: 24px; font-weight: bold; color: #007acc; }}
        .chart-container {{ width: 100%; height: 400px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Load Test Report</h1>
        <p><strong>Duration:</strong> {duration:.2f} seconds</p>
        <p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="metrics">
        <div class="metric">
            <h3>Total Requests</h3>
            <div class="value">{metrics.get('total_requests', 0):,}</div>
        </div>
        <div class="metric">
            <h3>Success Rate</h3>
            <div class="value">{(metrics.get('successful_requests', 0) / max(metrics.get('total_requests', 1), 1) * 100):.1f}%</div>
        </div>
        <div class="metric">
            <h3>Requests/sec</h3>
            <div class="value">{metrics.get('requests_per_second', 0):.1f}</div>
        </div>
        <div class="metric">
            <h3>Avg Response Time</h3>
            <div class="value">{metrics.get('avg_response_time_ms', 0):.1f} ms</div>
        </div>
    </div>
    
    <div class="chart-container">
        <canvas id="rpsChart"></canvas>
    </div>
    
    <div class="chart-container">
        <canvas id="responseTimeChart"></canvas>
    </div>
    
    <script>
        const progressData = {json.dumps(self.progress_data)};
        
        // RPS Chart
        const rpsCtx = document.getElementById('rpsChart').getContext('2d');
        new Chart(rpsCtx, {{
            type: 'line',
            data: {{
                labels: progressData.map(d => d.time.toFixed(0) + 's'),
                datasets: [{{
                    label: 'Requests per Second',
                    data: progressData.map(d => d.requests_per_second),
                    borderColor: '#007acc',
                    backgroundColor: 'rgba(0, 122, 204, 0.1)',
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Requests per Second Over Time'
                    }}
                }}
            }}
        }});
        
        // Response Time Chart
        const rtCtx = document.getElementById('responseTimeChart').getContext('2d');
        new Chart(rtCtx, {{
            type: 'line',
            data: {{
                labels: progressData.map(d => d.time.toFixed(0) + 's'),
                datasets: [{{
                    label: 'Average Response Time (ms)',
                    data: progressData.map(d => d.avg_response_time),
                    borderColor: '#28a745',
                    backgroundColor: 'rgba(40, 167, 69, 0.1)',
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    title: {{
                        display: true,
                        text: 'Average Response Time Over Time'
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
        """
        
        with open(self.output_file, 'w') as f:
            f.write(html_content)
            
        print(f"📊 HTML report saved to: {self.output_file}")


class MultiReporter(BaseReporter):
    """Reporter that combines multiple reporters"""
    
    def __init__(self, reporters: List[BaseReporter]):
        super().__init__()
        self.reporters = reporters
        
    def start_reporting(self):
        super().start_reporting()
        for reporter in self.reporters:
            reporter.start_reporting()
            
    def end_reporting(self):
        super().end_reporting()
        for reporter in self.reporters:
            reporter.end_reporting()
            
    def report_metrics(self, metrics: Dict[str, Any]):
        for reporter in self.reporters:
            reporter.report_metrics(metrics)
            
    def report_progress(self, elapsed_time: float, metrics: Dict[str, Any]):
        for reporter in self.reporters:
            reporter.report_progress(elapsed_time, metrics)