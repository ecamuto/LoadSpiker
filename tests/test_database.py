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

# MySQL and MongoDB now use real client drivers (libmysqlclient / libmongoc)
# when available, mirroring the PostgreSQL/libpq path. These tests connect to a
# live server when one is reachable and skip otherwise. Override the targets
# with LOADSPIKER_TEST_MYSQL / LOADSPIKER_TEST_MONGO.
MYSQL_CONN = os.environ.get(
    "LOADSPIKER_TEST_MYSQL", "mysql://testuser:testpass@localhost:3306/testdb")
MONGO_CONN = os.environ.get(
    "LOADSPIKER_TEST_MONGO", "mongodb://localhost:27017/testdb")


class TestDatabaseProtocol(unittest.TestCase):
    """Test database protocol functionality"""
    
    def setUp(self):
        """Set up test engine"""
        self.engine = Engine(max_connections=10, worker_threads=2)
        self.engine.reset_metrics()
    
    def tearDown(self):
        """Clean up after tests"""
        pass

    def _require_mysql(self):
        """Connect to MySQL or skip if no server is reachable. Returns conn str."""
        response = self.engine.database_connect(MYSQL_CONN, "mysql")
        if not response['success']:
            # Real driver: no reachable server -> reports a MySQL error.
            self.assertIn("MySQL", response.get('error_message', ''))
            self.skipTest("No MySQL server reachable for real libmysqlclient test")
        return MYSQL_CONN

    def _require_mongo(self):
        """Connect to MongoDB or skip if no server is reachable. Returns conn str."""
        response = self.engine.database_connect(MONGO_CONN, "mongodb")
        if not response['success']:
            self.assertIn("MongoDB", response.get('error_message', ''))
            self.skipTest("No MongoDB server reachable for real libmongoc test")
        return MONGO_CONN

    def test_mysql_connection(self):
        """Test MySQL database connection (real libmysqlclient; needs a live server)"""
        print("\n🔗 Testing MySQL Connection...")

        response = self.engine.database_connect(MYSQL_CONN, "mysql")

        if not response['success']:
            self.assertIn("MySQL", response.get('error_message', ''))
            self.skipTest("No MySQL server reachable for real libmysqlclient test")

        self.assertEqual(response['status_code'], 200)
        self.assertIn("Connected to mysql database", response['body'])
        self.assertGreater(response['response_time_us'], 0)

        print(f"   ✅ MySQL connection successful in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_postgresql_connection(self):
        """Test PostgreSQL database connection (real libpq; needs a live server)"""
        print("\n🔗 Testing PostgreSQL Connection...")

        connection_string = os.environ.get(
            "LOADSPIKER_TEST_PG",
            "postgresql://testuser:testpass@localhost:5432/testdb",
        )

        response = self.engine.database_connect(connection_string, "postgresql")

        if not response['success']:
            # Real driver: no reachable server -> reports a PostgreSQL error.
            self.assertIn("PostgreSQL", response.get('error_message', ''))
            self.skipTest("No PostgreSQL server reachable for real libpq test")

        self.assertEqual(response['status_code'], 200)
        self.assertIn("Connected to postgresql database", response['body'])

        print(f"   ✅ PostgreSQL connection successful in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")
    
    def test_mongodb_connection(self):
        """Test MongoDB database connection (real libmongoc; needs a live server)"""
        print("\n🔗 Testing MongoDB Connection...")

        response = self.engine.database_connect(MONGO_CONN, "mongodb")

        if not response['success']:
            self.assertIn("MongoDB", response.get('error_message', ''))
            self.skipTest("No MongoDB server reachable for real libmongoc test")

        self.assertEqual(response['status_code'], 200)
        self.assertIn("Connected to mongodb database", response['body'])

        print(f"   ✅ MongoDB connection successful in {response['response_time_us']/1000:.2f}ms")
        print(f"   📄 Response: {response['body']}")

    def test_auto_detect_database_type(self):
        """Test automatic database type detection.

        All three backends use real drivers, so a successful connect requires a
        live server; either way the response confirms the right driver was
        selected (success body, or a driver-named error message).
        """
        print("\n🔍 Testing Auto Database Type Detection...")

        cases = [
            ("mysql://user:pass@host/db", "mysql", "MySQL"),
            ("postgresql://user:pass@host/db", "postgresql", "PostgreSQL"),
            ("mongodb://localhost:27017/db", "mongodb", "MongoDB"),
        ]
        for conn, body_token, err_token in cases:
            response = self.engine.database_connect(conn, "auto")
            if response['success']:
                self.assertIn(body_token, response['body'])
            else:
                self.assertIn(err_token, response.get('error_message', ''))

        print("   ✅ Auto-detection selects the right driver for all database types")

    def test_mysql_crud_lifecycle(self):
        """Real MySQL SELECT/INSERT/UPDATE/DELETE via a temporary table.

        Uses a TEMPORARY TABLE so no pre-existing schema is required and nothing
        persists. Skips when no MySQL server is reachable.
        """
        print("\n📊 Testing MySQL CRUD lifecycle...")
        conn = self._require_mysql()

        # Sanity SELECT
        r = self.engine.database_query(conn, "SELECT 1 AS n")
        self.assertTrue(r['success'], r.get('error_message'))
        self.assertIn("1 rows returned", r['body'])

        # Temp table avoids needing a known schema and auto-drops on disconnect.
        r = self.engine.database_query(
            conn, "CREATE TEMPORARY TABLE ls_test (id INT PRIMARY KEY, name VARCHAR(32))")
        self.assertTrue(r['success'], r.get('error_message'))

        r = self.engine.database_query(conn, "INSERT INTO ls_test VALUES (1,'a'),(2,'b')")
        self.assertTrue(r['success'], r.get('error_message'))
        self.assertIn("2 row(s) affected", r['body'])

        r = self.engine.database_query(conn, "UPDATE ls_test SET name='c' WHERE id IN (1,2)")
        self.assertTrue(r['success'], r.get('error_message'))
        self.assertIn("2 row(s) affected", r['body'])

        r = self.engine.database_query(conn, "SELECT id, name FROM ls_test ORDER BY id")
        self.assertTrue(r['success'], r.get('error_message'))
        self.assertIn("2 rows returned", r['body'])
        if 'database_data' in r:
            self.assertIn("id,name", r['database_data']['result_set'])

        r = self.engine.database_query(conn, "DELETE FROM ls_test WHERE id = 1")
        self.assertTrue(r['success'], r.get('error_message'))
        self.assertIn("1 row(s) affected", r['body'])

        print("   ✅ MySQL CRUD lifecycle verified")

    def test_mysql_query_error(self):
        """A malformed query against real MySQL surfaces a driver error."""
        conn = self._require_mysql()
        r = self.engine.database_query(conn, "SELECT * FROM no_such_table_xyz")
        self.assertFalse(r['success'])
        self.assertEqual(r['status_code'], 500)
        self.assertIn("MySQL", r.get('error_message', ''))

    def test_mongodb_command(self):
        """Real MongoDB command: query string is a JSON command document."""
        print("\n📊 Testing MongoDB command...")
        conn = self._require_mongo()

        # ping is always available and returns {"ok": 1}.
        r = self.engine.database_query(conn, '{"ping": 1}')
        self.assertTrue(r['success'], r.get('error_message'))
        if 'database_data' in r:
            self.assertIn("ok", r['database_data']['result_set'])

        print("   ✅ MongoDB command executed")

    def test_mongodb_invalid_command_json(self):
        """Invalid command JSON is rejected before hitting the server."""
        conn = self._require_mongo()
        r = self.engine.database_query(conn, "not valid json")
        self.assertFalse(r['success'])
        self.assertEqual(r['status_code'], 400)
        self.assertIn("MongoDB command JSON", r.get('error_message', ''))

    def test_database_disconnect(self):
        """Test database disconnection (real MySQL; needs a live server)"""
        print("\n🔌 Testing Database Disconnect...")

        conn = self._require_mysql()

        response = self.engine.database_disconnect(conn)

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
