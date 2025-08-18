#!/usr/bin/env python3

"""
LoadSpiker Database Protocol Tests
=================================

Test suite for the database protocol implementation in LoadSpiker Phase 1.
Tests MySQL, PostgreSQL, and MongoDB connection and query functionality.
"""

import sys
import os
import unittest
import time

# Add parent directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from loadspiker import Engine
from loadspiker.scenarios import DatabaseScenario, MixedProtocolScenario

class TestDatabaseProtocol(unittest.TestCase):
    """Test database protocol functionality"""
    
    def setUp(self):
        """Set up test engine"""
        self.engine = Engine(max_connections=10, worker_threads=2)
        self.engine.reset_metrics()
    
    def tearDown(self):
        """Clean up after tests"""
        pass
    
    def test_mysql_connection(self):
        """Test MySQL database connection"""
        print("\n🔗 Testing MySQL Connection...")
        
        connection_string = "mysql://testuser:testpass@localhost:3306/testdb"
        
        response = self.engine.database_connect(connection_string, "mysql")
        
        self.assertTrue(response['success'])
        self.assertEqual(response['status_code'], 200)
        self.assertIn("Connected to mysql database", response['body'])
        self.assertGreater(response['response_time_us'], 0)
        
        print(f"   ✅ MySQL connection successful in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_postgresql_connection(self):
        """Test PostgreSQL database connection"""
        print("\n🔗 Testing PostgreSQL Connection...")
        
        connection_string = "postgresql://testuser:testpass@localhost:5432/testdb"
        
        response = self.engine.database_connect(connection_string, "postgresql")
        
        self.assertTrue(response['success'])
        self.assertEqual(response['status_code'], 200)
        self.assertIn("Connected to postgresql database", response['body'])
        
        print(f"   ✅ PostgreSQL connection successful in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_mongodb_connection(self):
        """Test MongoDB database connection"""
        print("\n🔗 Testing MongoDB Connection...")
        
        connection_string = "mongodb://testuser:testpass@localhost:27017/testdb"
        
        response = self.engine.database_connect(connection_string, "mongodb")
        
        self.assertTrue(response['success'])
        self.assertEqual(response['status_code'], 200)
        self.assertIn("Connected to mongodb database", response['body'])
        
        print(f"   ✅ MongoDB connection successful in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_auto_detect_database_type(self):
        """Test automatic database type detection"""
        print("\n🔍 Testing Auto Database Type Detection...")
        
        # Test MySQL auto-detection
        response = self.engine.database_connect("mysql://user:pass@host/db", "auto")
        self.assertTrue(response['success'])
        self.assertIn("mysql", response['body'])
        
        # Test PostgreSQL auto-detection
        response = self.engine.database_connect("postgresql://user:pass@host/db", "auto")
        self.assertTrue(response['success'])
        self.assertIn("postgresql", response['body'])
        
        # Test MongoDB auto-detection
        response = self.engine.database_connect("mongodb://user:pass@host/db", "auto")
        self.assertTrue(response['success'])
        self.assertIn("mongodb", response['body'])
        
        print("   ✅ Auto-detection working for all database types")
    
    def test_database_select_query(self):
        """Test SELECT query execution"""
        print("\n📊 Testing SELECT Query...")
        
        connection_string = "mysql://testuser:testpass@localhost:3306/testdb"
        
        # First connect
        connect_response = self.engine.database_connect(connection_string, "mysql")
        self.assertTrue(connect_response['success'])
        
        # Execute SELECT query
        query = "SELECT id, name, email FROM users WHERE active = 1"
        response = self.engine.database_query(connection_string, query)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['status_code'], 200)
        self.assertIn("3 rows returned", response['body'])
        
        # Check if response contains database-specific data
        if 'database_data' in response:
            db_data = response['database_data']
            self.assertEqual(db_data['rows_returned'], 3)
            self.assertEqual(db_data['rows_affected'], 0)
            self.assertTrue(len(db_data['result_set']) > 0)
        
        print(f"   ✅ SELECT query executed in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_database_insert_query(self):
        """Test INSERT query execution"""
        print("\n➕ Testing INSERT Query...")
        
        connection_string = "mysql://testuser:testpass@localhost:3306/testdb"
        
        # Connect first
        self.engine.database_connect(connection_string, "mysql")
        
        # Execute INSERT query
        query = "INSERT INTO users (name, email) VALUES ('John Doe', 'john@example.com')"
        response = self.engine.database_query(connection_string, query)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['status_code'], 200)
        self.assertIn("1 row(s) inserted", response['body'])
        
        print(f"   ✅ INSERT query executed in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_database_update_query(self):
        """Test UPDATE query execution"""
        print("\n📝 Testing UPDATE Query...")
        
        connection_string = "mysql://testuser:testpass@localhost:3306/testdb"
        
        # Connect first
        self.engine.database_connect(connection_string, "mysql")
        
        # Execute UPDATE query
        query = "UPDATE users SET email = 'newemail@example.com' WHERE name = 'John Doe'"
        response = self.engine.database_query(connection_string, query)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['status_code'], 200)
        self.assertIn("2 row(s) updated", response['body'])
        
        print(f"   ✅ UPDATE query executed in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_database_delete_query(self):
        """Test DELETE query execution"""
        print("\n🗑️  Testing DELETE Query...")
        
        connection_string = "mysql://testuser:testpass@localhost:3306/testdb"
        
        # Connect first
        self.engine.database_connect(connection_string, "mysql")
        
        # Execute DELETE query
        query = "DELETE FROM users WHERE id = 999"
        response = self.engine.database_query(connection_string, query)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['status_code'], 200)
        self.assertIn("1 row(s) deleted", response['body'])
        
        print(f"   ✅ DELETE query executed in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_database_disconnect(self):
        """Test database disconnection"""
        print("\n🔌 Testing Database Disconnect...")
        
        connection_string = "mysql://testuser:testpass@localhost:3306/testdb"
        
        # Connect first
        connect_response = self.engine.database_connect(connection_string, "mysql")
        self.assertTrue(connect_response['success'])
        
        # Disconnect
        response = self.engine.database_disconnect(connection_string)
        
        self.assertTrue(response['success'])
        self.assertEqual(response['status_code'], 200)
        self.assertIn("Database connection closed successfully", response['body'])
        
        print(f"   ✅ Disconnect successful in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_error_handling(self):
        """Test error handling for invalid operations"""
        print("\n❌ Testing Error Handling...")
        
        # Test query without connection
        response = self.engine.database_query("mysql://test:test@localhost/test", "SELECT * FROM users")
        self.assertFalse(response['success'])
        self.assertEqual(response['status_code'], 400)
        self.assertIn("No active database connection", response['error_message'])
        
        # Test invalid database type
        response = self.engine.database_connect("invalid://test", "invalid_type")
        self.assertFalse(response['success'])
        self.assertEqual(response['status_code'], 400)
        self.assertIn("Unsupported database type", response['error_message'])
        
        print("   ✅ Error handling working correctly")

class TestDatabaseScenario(unittest.TestCase):
    """Test database scenario functionality"""
    
    def setUp(self):
        """Set up test scenario"""
        self.connection_string = "mysql://testuser:testpass@localhost:3306/testdb"
    
    def test_database_scenario_creation(self):
        """Test database scenario creation"""
        print("\n🎬 Testing Database Scenario Creation...")
        
        scenario = DatabaseScenario(self.connection_string, "Test DB Scenario")
        
        self.assertEqual(scenario.name, "Test DB Scenario")
        self.assertEqual(scenario.connection_string, self.connection_string)
        self.assertEqual(scenario.db_type, "mysql")
        self.assertEqual(len(scenario.queries), 0)
        
        print("   ✅ Database scenario created successfully")
    
    def test_database_scenario_queries(self):
        """Test adding queries to database scenario"""
        print("\n📝 Testing Database Scenario Query Building...")
        
        scenario = DatabaseScenario(self.connection_string, "Test DB Scenario")
        
        # Add various types of queries
        scenario.select_query("users", "id, name", "active = 1")
        scenario.insert_query("users", ["name", "email"], ["John Doe", "john@example.com"])
        scenario.update_query("users", "last_login = NOW()", "id = 1")
        scenario.delete_query("users", "active = 0")
        scenario.add_query("SHOW TABLES")
        
        self.assertEqual(len(scenario.queries), 5)
        self.assertIn("SELECT id, name FROM users WHERE active = 1", scenario.queries[0])
        self.assertIn("INSERT INTO users", scenario.queries[1])
        self.assertIn("UPDATE users SET last_login", scenario.queries[2])
        self.assertIn("DELETE FROM users WHERE active = 0", scenario.queries[3])
        self.assertEqual("SHOW TABLES", scenario.queries[4])
        
        print("   ✅ All query types added successfully")
    
    def test_database_scenario_operations(self):
        """Test building database operations from scenario"""
        print("\n🔧 Testing Database Scenario Operations...")
        
        scenario = DatabaseScenario(self.connection_string, "Test DB Scenario")
        scenario.select_query("users", "*")
        scenario.insert_query("logs", ["message"], ["Test log entry"])
        
        operations = scenario.build_database_operations()
        
        # Should have connect, 2 queries, and disconnect
        self.assertEqual(len(operations), 4)
        
        self.assertEqual(operations[0]["type"], "database_connect")
        self.assertEqual(operations[1]["type"], "database_query")
        self.assertEqual(operations[2]["type"], "database_query")
        self.assertEqual(operations[3]["type"], "database_disconnect")
        
        print("   ✅ Database operations built correctly")

class TestMixedProtocolScenario(unittest.TestCase):
    """Test mixed protocol scenarios including database"""
    
    def test_mixed_protocol_scenario(self):
        """Test scenario with HTTP, WebSocket, and Database operations"""
        print("\n🔀 Testing Mixed Protocol Scenario...")
        
        scenario = MixedProtocolScenario("Mixed Test")
        
        # Add HTTP request
        scenario.add_http_request("https://httpbin.org/json", "GET")
        
        # Add WebSocket operations
        scenario.add_websocket_operation("wss://echo.websocket.org", "connect")
        scenario.add_websocket_operation("wss://echo.websocket.org", "send", "Hello WebSocket!")
        scenario.add_websocket_operation("wss://echo.websocket.org", "close")
        
        # Add Database operations
        scenario.add_database_operation("mysql://user:pass@localhost/db", "connect")
        scenario.add_database_operation("mysql://user:pass@localhost/db", "query", "SELECT * FROM users")
        scenario.add_database_operation("mysql://user:pass@localhost/db", "disconnect")
        
        operations = scenario.build_mixed_operations()
        
        self.assertEqual(len(operations), 7)
        
        # Check operation types
        self.assertEqual(operations[0]["type"], "http")
        self.assertEqual(operations[1]["type"], "websocket")
        self.assertEqual(operations[4]["type"], "database")
        
        print("   ✅ Mixed protocol scenario created successfully")

def run_database_protocol_demo():
    """Run a comprehensive database protocol demonstration"""
    print("🚀 LoadSpiker Database Protocol Demo")
    print("=" * 45)
    
    engine = Engine(max_connections=50, worker_threads=4)
    
    # Test different database types
    databases = [
        ("mysql://testuser:testpass@localhost:3306/testdb", "mysql"),
        ("postgresql://testuser:testpass@localhost:5432/testdb", "postgresql"),
        ("mongodb://testuser:testpass@localhost:27017/testdb", "mongodb")
    ]
    
    for connection_string, db_type in databases:
        print(f"\n📊 Testing {db_type.upper()} Database...")
        print("-" * 30)
        
        # Connect
        response = engine.database_connect(connection_string, db_type)
        print(f"Connect: {response['success']} ({response['response_time_us']/1000:.2f}ms)")
        
        if response['success']:
            # Run queries
            queries = [
                "SELECT * FROM users LIMIT 10",
                "INSERT INTO logs (message, timestamp) VALUES ('Test entry', NOW())",
                "UPDATE users SET last_seen = NOW() WHERE active = 1",
                "SELECT COUNT(*) FROM users"
            ]
            
            for query in queries:
                query_response = engine.database_query(connection_string, query)
                print(f"Query: {query_response['success']} - {query_response['body'][:50]}...")
                time.sleep(0.1)
            
            # Disconnect
            disconnect_response = engine.database_disconnect(connection_string)
            print(f"Disconnect: {disconnect_response['success']}")
    
    # Show metrics
    print(f"\n📈 Final Metrics:")
    metrics = engine.get_metrics()
    print(f"Total Requests: {metrics['total_requests']}")
    print(f"Successful: {metrics['successful_requests']}")
    print(f"Failed: {metrics['failed_requests']}")
    if metrics['total_requests'] > 0:
        print(f"Average Response Time: {metrics['avg_response_time_ms']:.2f}ms")

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'demo':
        run_database_protocol_demo()
    else:
        print("🧪 Running LoadSpiker Database Protocol Tests")
        print("=" * 50)
        unittest.main(verbosity=2)
