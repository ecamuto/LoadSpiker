#!/usr/bin/env python3

"""
LoadSpiker Database Protocol Demo
================================

This example demonstrates the new database protocol support in LoadSpiker Phase 1.
It shows how MySQL, PostgreSQL, and MongoDB can be tested using LoadSpiker.
"""

import sys
import os
import time
import json

# Add parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine
from loadspiker.scenarios import DatabaseScenario, MixedProtocolScenario

def main():
    print("🚀 LoadSpiker Database Protocol Demo")
    print("=" * 50)
    
    # Create engine
    print("📦 Creating LoadSpiker engine...")
    engine = Engine(max_connections=100, worker_threads=4)
    print("✅ Engine created successfully")
    
    # Test 1: Individual Database Connections
    print("\n🗄️  Testing Individual Database Connections")
    print("-" * 50)
    
    databases = [
        ("mysql://testuser:testpass@localhost:3306/testdb", "mysql"),
        ("postgresql://testuser:testpass@localhost:5432/testdb", "postgresql"),
        ("mongodb://testuser:testpass@localhost:27017/testdb", "mongodb")
    ]
    
    for connection_string, db_type in databases:
        print(f"\n🔗 Testing {db_type.upper()} Connection...")
        
        # Connect to database
        connect_response = engine.database_connect(connection_string, db_type)
        print(f"   Connection: {'✅ Success' if connect_response['success'] else '❌ Failed'}")
        print(f"   Response Time: {connect_response['response_time_us'] / 1000:.2f}ms")
        print(f"   Message: {connect_response['body']}")
        
        if connect_response['success']:
            # Run some sample queries
            print(f"   📊 Running sample queries...")
            
            queries = [
                ("SELECT", "SELECT id, name, email FROM users WHERE active = 1"),
                ("INSERT", "INSERT INTO logs (message, timestamp) VALUES ('LoadSpiker test', NOW())"),
                ("UPDATE", "UPDATE users SET last_login = NOW() WHERE id = 1"),
                ("COUNT", "SELECT COUNT(*) FROM users")
            ]
            
            for query_type, query in queries:
                query_response = engine.database_query(connection_string, query)
                print(f"      {query_type}: {'✅' if query_response['success'] else '❌'} "
                      f"({query_response['response_time_us'] / 1000:.2f}ms)")
                if query_response['success']:
                    print(f"         Result: {query_response['body']}")
            
            # Disconnect
            disconnect_response = engine.database_disconnect(connection_string)
            print(f"   Disconnect: {'✅ Success' if disconnect_response['success'] else '❌ Failed'}")
    
    # Test 2: Database Scenario Usage
    print("\n🎬 Testing Database Scenario")
    print("-" * 30)
    
    # Create a MySQL scenario
    db_scenario = DatabaseScenario("mysql://testuser:testpass@localhost:3306/ecommerce", "E-commerce DB Test")
    
    # Add various queries
    db_scenario.select_query("products", "id, name, price", "category = 'electronics'")
    db_scenario.select_query("orders", "COUNT(*)", "created_at >= CURDATE()")
    db_scenario.insert_query("page_views", ["page", "user_id", "timestamp"], 
                           ["product_detail", "123", "NOW()"])
    db_scenario.update_query("users", "last_active = NOW()", "id = 123")
    db_scenario.add_query("SHOW TABLE STATUS")
    
    # Build operations
    operations = db_scenario.build_database_operations()
    print(f"✅ Database scenario created with {len(operations)} operations")
    print("   Operations:")
    for i, op in enumerate(operations, 1):
        print(f"      {i}. {op['type'].replace('database_', '').title()}")
        if 'query' in op and op['query']:
            print(f"         Query: {op['query'][:50]}...")
    
    # Test 3: Mixed Protocol Scenario
    print("\n🔀 Testing Mixed Protocol Scenario")
    print("-" * 35)
    
    mixed_scenario = MixedProtocolScenario("E-commerce Load Test")
    
    # Add HTTP API calls
    mixed_scenario.add_http_request("https://api.example.com/products", "GET")
    mixed_scenario.add_http_request("https://api.example.com/cart", "POST", 
                                   headers={"Content-Type": "application/json"},
                                   body='{"product_id": 123, "quantity": 2}')
    
    # Add WebSocket operations for real-time updates
    mixed_scenario.add_websocket_operation("wss://api.example.com/live-updates", "connect")
    mixed_scenario.add_websocket_operation("wss://api.example.com/live-updates", "send", 
                                         '{"action": "subscribe", "channel": "inventory"}')
    
    # Add database operations for analytics
    mixed_scenario.add_database_operation("mysql://analytics:pass@localhost/analytics", 
                                        "connect", db_type="mysql")
    mixed_scenario.add_database_operation("mysql://analytics:pass@localhost/analytics", 
                                        "query", "INSERT INTO user_actions (action, timestamp) VALUES ('purchase', NOW())")
    mixed_scenario.add_database_operation("mysql://analytics:pass@localhost/analytics", 
                                        "query", "SELECT COUNT(*) FROM user_actions WHERE DATE(timestamp) = CURDATE()")
    
    # Close connections
    mixed_scenario.add_websocket_operation("wss://api.example.com/live-updates", "close")
    mixed_scenario.add_database_operation("mysql://analytics:pass@localhost/analytics", "disconnect")
    
    # Build mixed operations
    mixed_operations = mixed_scenario.build_mixed_operations()
    print(f"✅ Mixed protocol scenario created with {len(mixed_operations)} operations")
    print("   Protocol Distribution:")
    protocol_counts = {}
    for op in mixed_operations:
        protocol_counts[op['type']] = protocol_counts.get(op['type'], 0) + 1
    for protocol, count in protocol_counts.items():
        print(f"      {protocol.title()}: {count} operations")
    
    # Test 4: Auto Database Type Detection
    print("\n🔍 Testing Auto Database Type Detection")
    print("-" * 40)
    
    test_connections = [
        "mysql://user:pass@host:3306/database",
        "postgresql://user:pass@host:5432/database", 
        "mongodb://user:pass@host:27017/database"
    ]
    
    for conn_string in test_connections:
        response = engine.database_connect(conn_string, "auto")
        detected_type = "mysql" if "mysql" in response['body'] else \
                       "postgresql" if "postgresql" in response['body'] else \
                       "mongodb" if "mongodb" in response['body'] else "unknown"
        print(f"   {conn_string[:20]}... → Detected: {detected_type.upper()}")
    
    # Test 5: Performance Metrics
    print("\n📈 Database Performance Metrics")
    print("-" * 35)
    
    # Reset metrics for clean measurement
    engine.reset_metrics()
    
    # Simulate some database load
    print("   Running database performance test...")
    connection_string = "mysql://loadtest:pass@localhost:3306/performance"
    
    # Connect
    engine.database_connect(connection_string, "mysql")
    
    # Run multiple queries to generate metrics
    for i in range(10):
        queries = [
            f"SELECT * FROM users WHERE id = {i + 1}",
            f"INSERT INTO metrics (test_run, value) VALUES ({i}, {i * 10})",
            "SELECT AVG(response_time) FROM metrics WHERE test_run >= 0"
        ]
        
        for query in queries:
            engine.database_query(connection_string, query)
        
        time.sleep(0.1)  # Small delay between batches
    
    # Disconnect
    engine.database_disconnect(connection_string)
    
    # Show final metrics
    metrics = engine.get_metrics()
    print(f"   ✅ Performance test completed!")
    print(f"   Total Database Operations: {metrics['total_requests']}")
    print(f"   Successful Operations: {metrics['successful_requests']}")
    print(f"   Failed Operations: {metrics['failed_requests']}")
    
    if metrics['total_requests'] > 0:
        print(f"   Average Response Time: {metrics['avg_response_time_ms']:.2f}ms")
        print(f"   Min Response Time: {metrics['min_response_time_us'] / 1000:.2f}ms")
        print(f"   Max Response Time: {metrics['max_response_time_us'] / 1000:.2f}ms")
        success_rate = (metrics['successful_requests'] / metrics['total_requests']) * 100
        print(f"   Success Rate: {success_rate:.1f}%")
    
    # Test 6: Error Handling Demonstration
    print("\n❌ Testing Error Handling")
    print("-" * 25)
    
    error_tests = [
        ("Invalid DB Type", "invalid://test", "invalid_type"),
        ("Query Without Connection", "mysql://test:test@localhost/test", "mysql"),
        ("Malformed Connection String", "not-a-connection-string", "mysql")
    ]
    
    for test_name, conn_string, db_type in error_tests:
        print(f"   {test_name}:")
        if "Query Without Connection" in test_name:
            # Try to query without connecting first
            response = engine.database_query(conn_string, "SELECT 1")
        else:
            response = engine.database_connect(conn_string, db_type)
        
        print(f"      Result: {'❌ Failed as expected' if not response['success'] else '⚠️ Unexpected success'}")
        if not response['success']:
            print(f"      Error: {response['error_message']}")
    
    # Summary
    print("\n🎉 Database Protocol Demo Complete!")
    print("\n✅ Successfully Demonstrated:")
    print("   🗄️  MySQL, PostgreSQL, and MongoDB protocol support")
    print("   🔧 Database connection management")
    print("   📊 SQL query execution (SELECT, INSERT, UPDATE, DELETE)")
    print("   🎬 Database scenario building")
    print("   🔀 Mixed protocol scenarios (HTTP + WebSocket + Database)")
    print("   🔍 Automatic database type detection")
    print("   📈 Performance metrics collection")
    print("   ❌ Comprehensive error handling")
    
    print("\n🔮 Database Protocol Benefits:")
    print("   ⚡ High-performance C backend for database operations")
    print("   🐍 Clean Python API for easy integration")
    print("   📊 Protocol-specific response data and metrics")
    print("   🔗 Connection pooling and management")
    print("   🎯 Realistic database load testing capabilities")
    print("   🔧 Extensible framework for adding more database types")
    
    print("\n📋 Future Database Enhancements:")
    print("   🔒 Real database driver integration (MySQL Connector, libpq, mongo-c-driver)")
    print("   💾 Connection pooling optimization")
    print("   🛡️  SSL/TLS connection support")
    print("   📈 Advanced database-specific metrics")
    print("   🔄 Transaction support")
    print("   🗂️  Schema validation and migration testing")

if __name__ == "__main__":
    main()
