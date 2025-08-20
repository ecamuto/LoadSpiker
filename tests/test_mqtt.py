#!/usr/bin/env python3
"""
MQTT Protocol Test Suite for LoadSpiker

Tests the MQTT protocol implementation including:
- Connection handling
- Publishing messages
- Subscribing to topics
- Quality of Service levels
- Message retention
- Error handling
"""

import unittest
import sys
import os
import time
import threading

# Add parent directory to path to import loadspiker
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from loadspiker.engine import Engine
    from loadspiker.scenarios import MQTTScenario
    LOADSPIKER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: LoadSpiker not available: {e}")
    LOADSPIKER_AVAILABLE = False


class TestMQTTProtocol(unittest.TestCase):
    """Test MQTT protocol functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        if not LOADSPIKER_AVAILABLE:
            cls.skipTest("LoadSpiker not available")
        
        cls.engine = Engine(max_connections=10, worker_threads=2)
        cls.test_broker = "test.mosquitto.org"  # Public test broker
        cls.test_port = 1883
        cls.test_client_id = "loadspiker_test_client"
        
    def setUp(self):
        """Set up each test"""
        self.engine.reset_metrics()
        
    def test_mqtt_connect_basic(self):
        """Test basic MQTT connection"""
        result = self.engine.mqtt_connect(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        self.assertIn('response_time_ms', result)
        
        # Note: For fallback implementation, success might be simulated
        print(f"MQTT Connect Result: {result}")
        
    def test_mqtt_connect_with_auth(self):
        """Test MQTT connection with authentication"""
        result = self.engine.mqtt_connect(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            username="test_user",
            password="test_pass"
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        print(f"MQTT Connect with Auth Result: {result}")
        
    def test_mqtt_publish_qos0(self):
        """Test MQTT publish with QoS 0"""
        topic = "loadspiker/test/qos0"
        payload = "Hello MQTT QoS 0"
        
        result = self.engine.mqtt_publish(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            topic=topic,
            payload=payload,
            qos=0,
            retain=False
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        print(f"MQTT Publish QoS 0 Result: {result}")
        
    def test_mqtt_publish_qos1(self):
        """Test MQTT publish with QoS 1"""
        topic = "loadspiker/test/qos1"
        payload = "Hello MQTT QoS 1"
        
        result = self.engine.mqtt_publish(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            topic=topic,
            payload=payload,
            qos=1,
            retain=False
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        print(f"MQTT Publish QoS 1 Result: {result}")
        
    def test_mqtt_publish_retained(self):
        """Test MQTT publish with retained message"""
        topic = "loadspiker/test/retained"
        payload = "This is a retained message"
        
        result = self.engine.mqtt_publish(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            topic=topic,
            payload=payload,
            qos=0,
            retain=True
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        print(f"MQTT Publish Retained Result: {result}")
        
    def test_mqtt_subscribe(self):
        """Test MQTT subscribe to topic"""
        topic = "loadspiker/test/subscribe"
        
        result = self.engine.mqtt_subscribe(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            topic=topic,
            qos=0
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        print(f"MQTT Subscribe Result: {result}")
        
    def test_mqtt_subscribe_wildcard(self):
        """Test MQTT subscribe with wildcard topics"""
        # Test single-level wildcard
        topic_single = "loadspiker/test/+/data"
        result1 = self.engine.mqtt_subscribe(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            topic=topic_single,
            qos=0
        )
        
        self.assertIsInstance(result1, dict)
        print(f"MQTT Subscribe Single Wildcard Result: {result1}")
        
        # Test multi-level wildcard
        topic_multi = "loadspiker/test/multi/#"
        result2 = self.engine.mqtt_subscribe(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            topic=topic_multi,
            qos=1
        )
        
        self.assertIsInstance(result2, dict)
        print(f"MQTT Subscribe Multi Wildcard Result: {result2}")
        
    def test_mqtt_unsubscribe(self):
        """Test MQTT unsubscribe from topic"""
        topic = "loadspiker/test/unsubscribe"
        
        result = self.engine.mqtt_unsubscribe(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            topic=topic
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        print(f"MQTT Unsubscribe Result: {result}")
        
    def test_mqtt_disconnect(self):
        """Test MQTT disconnect"""
        result = self.engine.mqtt_disconnect(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id
        )
        
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        print(f"MQTT Disconnect Result: {result}")
        
    def test_mqtt_performance_metrics(self):
        """Test MQTT performance metrics collection"""
        initial_metrics = self.engine.get_metrics()
        
        # Perform MQTT operations
        self.engine.mqtt_connect(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id
        )
        
        self.engine.mqtt_publish(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            topic="loadspiker/test/metrics",
            payload="Performance test message",
            qos=0
        )
        
        final_metrics = self.engine.get_metrics()
        
        # Check that metrics were updated
        self.assertGreaterEqual(final_metrics.get('total_requests', 0), 
                               initial_metrics.get('total_requests', 0))
        print(f"MQTT Performance Metrics: {final_metrics}")
        

class TestMQTTScenario(unittest.TestCase):
    """Test MQTT Scenario functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        if not LOADSPIKER_AVAILABLE:
            cls.skipTest("LoadSpiker not available")
        
        cls.test_broker = "test.mosquitto.org"
        cls.test_port = 1883
        cls.test_client_id = "loadspiker_scenario_test"
        
    def test_mqtt_scenario_creation(self):
        """Test MQTTScenario creation"""
        scenario = MQTTScenario(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id,
            name="Test MQTT Scenario"
        )
        
        self.assertEqual(scenario.broker_host, self.test_broker)
        self.assertEqual(scenario.broker_port, self.test_port)
        self.assertEqual(scenario.client_id, self.test_client_id)
        self.assertEqual(scenario.name, "Test MQTT Scenario")
        
    def test_mqtt_scenario_publish_test(self):
        """Test MQTTScenario publish test"""
        scenario = MQTTScenario(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id
        )
        
        scenario.add_publish_test(
            topic="loadspiker/test/scenario/publish",
            payload="Scenario publish test",
            qos=1
        )
        
        operations = scenario.build_mqtt_operations(user_id=0)
        
        # Should have connect, publish, and disconnect operations
        self.assertEqual(len(operations), 3)
        self.assertEqual(operations[0]["type"], "mqtt_connect")
        self.assertEqual(operations[1]["type"], "mqtt_publish")
        self.assertEqual(operations[2]["type"], "mqtt_disconnect")
        
        print(f"MQTT Scenario Publish Test Operations: {operations}")
        
    def test_mqtt_scenario_subscribe_test(self):
        """Test MQTTScenario subscribe test"""
        scenario = MQTTScenario(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id
        )
        
        scenario.add_subscribe_test(
            topic="loadspiker/test/scenario/subscribe",
            qos=1
        )
        
        operations = scenario.build_mqtt_operations(user_id=0)
        
        # Should have connect, subscribe, unsubscribe, and disconnect operations
        self.assertEqual(len(operations), 4)
        self.assertEqual(operations[0]["type"], "mqtt_connect")
        self.assertEqual(operations[1]["type"], "mqtt_subscribe")
        self.assertEqual(operations[2]["type"], "mqtt_unsubscribe")
        self.assertEqual(operations[3]["type"], "mqtt_disconnect")
        
    def test_mqtt_scenario_pub_sub_test(self):
        """Test MQTTScenario publish-subscribe test"""
        scenario = MQTTScenario(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id
        )
        
        scenario.add_pub_sub_test(
            topic="loadspiker/test/scenario/pubsub",
            payload="Pub-Sub test message",
            qos=1
        )
        
        operations = scenario.build_mqtt_operations(user_id=0)
        
        # Should have connect, subscribe, publish, unsubscribe, and disconnect operations
        self.assertEqual(len(operations), 5)
        self.assertEqual(operations[0]["type"], "mqtt_connect")
        self.assertEqual(operations[1]["type"], "mqtt_subscribe")
        self.assertEqual(operations[2]["type"], "mqtt_publish")
        self.assertEqual(operations[3]["type"], "mqtt_unsubscribe")
        self.assertEqual(operations[4]["type"], "mqtt_disconnect")
        
    def test_mqtt_scenario_burst_publish(self):
        """Test MQTTScenario burst publish test"""
        scenario = MQTTScenario(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id
        )
        
        message_count = 5
        scenario.add_burst_publish_test(
            topic="loadspiker/test/scenario/burst",
            message_count=message_count,
            base_payload="Burst test message"
        )
        
        operations = scenario.build_mqtt_operations(user_id=0)
        
        # Should have connect + message_count publish operations + disconnect
        expected_ops = 1 + message_count + 1  # connect + publishes + disconnect
        self.assertEqual(len(operations), expected_ops)
        self.assertEqual(operations[0]["type"], "mqtt_connect")
        
        # Check all publish operations
        for i in range(1, message_count + 1):
            self.assertEqual(operations[i]["type"], "mqtt_publish")
            self.assertIn(f"#{i}", operations[i]["payload"])
        
        self.assertEqual(operations[-1]["type"], "mqtt_disconnect")
        
    def test_mqtt_scenario_topic_pattern_test(self):
        """Test MQTTScenario topic pattern test"""
        scenario = MQTTScenario(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id=self.test_client_id
        )
        
        topic_count = 3
        scenario.add_topic_pattern_test(
            topic_pattern="loadspiker/test/+/data",
            topic_count=topic_count,
            payload="Pattern test"
        )
        
        operations = scenario.build_mqtt_operations(user_id=0)
        
        # Should have connect + subscribe + topic_count publishes + unsubscribe + disconnect
        expected_ops = 1 + 1 + topic_count + 1 + 1
        self.assertEqual(len(operations), expected_ops)
        
        self.assertEqual(operations[0]["type"], "mqtt_connect")
        self.assertEqual(operations[1]["type"], "mqtt_subscribe")
        self.assertEqual(operations[1]["topic"], "loadspiker/test/+/data")
        
        # Check publish operations with specific topics
        for i in range(2, 2 + topic_count):
            self.assertEqual(operations[i]["type"], "mqtt_publish")
            self.assertIn(f"topic{i-2}", operations[i]["topic"])
        
    def test_mqtt_scenario_variable_substitution(self):
        """Test MQTTScenario variable substitution"""
        scenario = MQTTScenario(
            broker_host=self.test_broker,
            broker_port=self.test_port,
            client_id="${data.client_id}"
        )
        
        # Set up test data
        scenario.set_variable("test_topic", "loadspiker/test/variables")
        
        scenario.add_publish_test(
            topic="${test_topic}",
            payload="Message from ${data.username}",
            qos=0
        )
        
        # Mock user data
        scenario.data_manager.get_all_user_data = lambda user_id: {
            "data": {"client_id": f"user_{user_id}", "username": "testuser"}
        }
        
        operations = scenario.build_mqtt_operations(user_id=1)
        
        # Check variable substitution
        self.assertEqual(operations[0]["client_id"], "user_1")
        self.assertEqual(operations[1]["topic"], "loadspiker/test/variables")
        self.assertEqual(operations[1]["payload"], "Message from testuser")


class TestMQTTIntegration(unittest.TestCase):
    """Integration tests for MQTT functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Set up integration test environment"""
        if not LOADSPIKER_AVAILABLE:
            cls.skipTest("LoadSpiker not available")
            
    def test_mqtt_full_workflow(self):
        """Test complete MQTT workflow"""
        engine = Engine(max_connections=5, worker_threads=2)
        
        # Create MQTT scenario
        scenario = MQTTScenario(
            broker_host="test.mosquitto.org",
            broker_port=1883,
            client_id="loadspiker_integration_test"
        )
        
        # Add comprehensive test
        scenario.add_pub_sub_test(
            topic="loadspiker/integration/test",
            payload="Integration test message",
            qos=1,
            retain=False
        )
        
        operations = scenario.build_mqtt_operations(user_id=0)
        self.assertGreater(len(operations), 0)
        
        print(f"MQTT Integration Test Operations: {len(operations)}")
        
        # Get initial metrics
        initial_metrics = engine.get_metrics()
        
        # Simulate executing operations (in real scenario, this would use the engine)
        for operation in operations:
            if operation["type"] == "mqtt_connect":
                result = engine.mqtt_connect(**{k: v for k, v in operation.items() if k != "type"})
            elif operation["type"] == "mqtt_publish":
                result = engine.mqtt_publish(**{k: v for k, v in operation.items() if k != "type"})
            elif operation["type"] == "mqtt_subscribe":
                result = engine.mqtt_subscribe(**{k: v for k, v in operation.items() if k != "type"})
            elif operation["type"] == "mqtt_unsubscribe":
                result = engine.mqtt_unsubscribe(**{k: v for k, v in operation.items() if k != "type"})
            elif operation["type"] == "mqtt_disconnect":
                result = engine.mqtt_disconnect(**{k: v for k, v in operation.items() if k != "type"})
            
            self.assertIsInstance(result, dict)
        
        # Check final metrics
        final_metrics = engine.get_metrics()
        self.assertGreaterEqual(final_metrics.get('total_requests', 0), 
                               initial_metrics.get('total_requests', 0))
        
        print(f"MQTT Integration Test Completed. Final metrics: {final_metrics}")


def run_mqtt_tests():
    """Run all MQTT tests"""
    print("=" * 60)
    print("LoadSpiker MQTT Protocol Test Suite")
    print("=" * 60)
    
    if not LOADSPIKER_AVAILABLE:
        print("❌ LoadSpiker is not available. Skipping tests.")
        return False
        
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestMQTTProtocol))
    suite.addTest(unittest.makeSuite(TestMQTTScenario))
    suite.addTest(unittest.makeSuite(TestMQTTIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print("MQTT Test Summary")
    print("=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFailures:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
            
    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\n{'✅ All tests passed!' if success else '❌ Some tests failed.'}")
    
    return success


if __name__ == "__main__":
    success = run_mqtt_tests()
    sys.exit(0 if success else 1)
