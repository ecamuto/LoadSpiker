#!/usr/bin/env python3
"""
MQTT Load Testing Demo for LoadSpiker

This demo showcases the MQTT protocol support in LoadSpiker, demonstrating:
- Basic MQTT operations (connect, publish, subscribe, disconnect)
- Different Quality of Service levels (QoS 0, 1, 2)
- Message retention testing
- Topic wildcards and patterns
- Burst publishing scenarios
- Performance monitoring and metrics

Prerequisites:
- LoadSpiker with MQTT support
- Access to an MQTT broker (uses test.mosquitto.org by default)

Usage:
    python examples/mqtt_demo.py
"""

import sys
import os
import time
import random
from datetime import datetime

# Add parent directory to path to import loadspiker
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from loadspiker.engine import Engine
    from loadspiker.scenarios import MQTTScenario
    LOADSPIKER_AVAILABLE = True
except ImportError as e:
    print(f"❌ Error: LoadSpiker not available: {e}")
    print("Please ensure LoadSpiker is installed and built correctly.")
    sys.exit(1)


def print_banner():
    """Print demo banner"""
    print("=" * 70)
    print("🚀 LoadSpiker MQTT Protocol Demo")
    print("=" * 70)
    print("This demo demonstrates MQTT load testing capabilities including:")
    print("• Basic MQTT operations (connect, publish, subscribe)")
    print("• Quality of Service levels (QoS 0, 1, 2)")
    print("• Message retention and topic patterns")
    print("• High-throughput publishing scenarios")
    print("• Performance metrics and monitoring")
    print("=" * 70)


def demo_basic_mqtt_operations():
    """Demonstrate basic MQTT operations"""
    print("\n🔗 Demo 1: Basic MQTT Operations")
    print("-" * 50)
    
    engine = Engine(max_connections=5, worker_threads=2)
    
    # MQTT broker configuration
    broker_host = "test.mosquitto.org"  # Public test broker
    broker_port = 1883
    client_id = f"loadspiker_demo_{int(time.time())}"
    
    print(f"Connecting to MQTT broker: {broker_host}:{broker_port}")
    print(f"Client ID: {client_id}")
    
    # Test connection
    print("\n📡 Testing MQTT Connection...")
    result = engine.mqtt_connect(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id=client_id,
        keep_alive=60
    )
    print(f"Connection result: {result.get('success', False)}")
    print(f"Response time: {result.get('response_time_ms', 0):.2f} ms")
    
    # Test publishing
    print("\n📤 Testing MQTT Publishing...")
    topic = "loadspiker/demo/basic"
    payload = f"Hello from LoadSpiker! Time: {datetime.now().isoformat()}"
    
    result = engine.mqtt_publish(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id=client_id,
        topic=topic,
        payload=payload,
        qos=0,
        retain=False
    )
    print(f"Publish result: {result.get('success', False)}")
    print(f"Topic: {topic}")
    print(f"Payload: {payload}")
    print(f"Response time: {result.get('response_time_ms', 0):.2f} ms")
    
    # Test subscribing
    print("\n📥 Testing MQTT Subscribe...")
    sub_topic = "loadspiker/demo/subscribe"
    result = engine.mqtt_subscribe(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id=client_id,
        topic=sub_topic,
        qos=0
    )
    print(f"Subscribe result: {result.get('success', False)}")
    print(f"Subscribed to topic: {sub_topic}")
    print(f"Response time: {result.get('response_time_ms', 0):.2f} ms")
    
    # Test disconnect
    print("\n🔌 Testing MQTT Disconnect...")
    result = engine.mqtt_disconnect(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id=client_id
    )
    print(f"Disconnect result: {result.get('success', False)}")
    print(f"Response time: {result.get('response_time_ms', 0):.2f} ms")
    
    # Show metrics
    metrics = engine.get_metrics()
    print(f"\n📊 Basic Operations Metrics:")
    print(f"Total requests: {metrics.get('total_requests', 0)}")
    print(f"Successful requests: {metrics.get('successful_requests', 0)}")
    print(f"Failed requests: {metrics.get('failed_requests', 0)}")


def demo_qos_levels():
    """Demonstrate different QoS levels"""
    print("\n⚡ Demo 2: Quality of Service Levels")
    print("-" * 50)
    
    engine = Engine(max_connections=5, worker_threads=2)
    
    broker_host = "test.mosquitto.org"
    broker_port = 1883
    client_id = f"loadspiker_qos_demo_{int(time.time())}"
    
    qos_levels = [0, 1, 2]
    qos_descriptions = {
        0: "At most once delivery (fire and forget)",
        1: "At least once delivery (acknowledged)",
        2: "Exactly once delivery (assured)"
    }
    
    for qos in qos_levels:
        print(f"\n🎯 Testing QoS {qos}: {qos_descriptions[qos]}")
        
        topic = f"loadspiker/demo/qos{qos}"
        payload = f"QoS {qos} test message - {datetime.now().isoformat()}"
        
        result = engine.mqtt_publish(
            broker_host=broker_host,
            broker_port=broker_port,
            client_id=client_id,
            topic=topic,
            payload=payload,
            qos=qos,
            retain=False
        )
        
        print(f"  Result: {result.get('success', False)}")
        print(f"  Response time: {result.get('response_time_ms', 0):.2f} ms")
        
        # Small delay between QoS tests
        time.sleep(0.5)


def demo_retained_messages():
    """Demonstrate retained message functionality"""
    print("\n💾 Demo 3: Retained Messages")
    print("-" * 50)
    
    engine = Engine(max_connections=5, worker_threads=2)
    
    broker_host = "test.mosquitto.org"
    broker_port = 1883
    client_id = f"loadspiker_retained_demo_{int(time.time())}"
    
    topic = "loadspiker/demo/retained"
    retained_payload = f"This message will be retained! Published at {datetime.now().isoformat()}"
    
    print(f"📌 Publishing retained message...")
    print(f"Topic: {topic}")
    print(f"Payload: {retained_payload}")
    
    result = engine.mqtt_publish(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id=client_id,
        topic=topic,
        payload=retained_payload,
        qos=1,
        retain=True
    )
    
    print(f"Publish result: {result.get('success', False)}")
    print(f"Response time: {result.get('response_time_ms', 0):.2f} ms")
    print("Note: This message will be delivered to future subscribers!")


def demo_mqtt_scenario():
    """Demonstrate MQTT scenario usage"""
    print("\n🎭 Demo 4: MQTT Scenario Testing")
    print("-" * 50)
    
    broker_host = "test.mosquitto.org"
    broker_port = 1883
    client_id = f"loadspiker_scenario_demo_{int(time.time())}"
    
    print("Creating comprehensive MQTT test scenario...")
    
    # Create scenario with pub-sub test
    scenario = MQTTScenario(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id=client_id,
        name="Demo Pub-Sub Test"
    )
    
    scenario.add_pub_sub_test(
        topic="loadspiker/demo/scenario/pubsub",
        payload="Scenario-based pub-sub test message",
        qos=1,
        retain=False
    )
    
    # Build and display operations
    operations = scenario.build_mqtt_operations(user_id=0)
    print(f"Generated {len(operations)} MQTT operations:")
    
    for i, op in enumerate(operations, 1):
        op_type = op.get('type', 'unknown').replace('mqtt_', '').upper()
        print(f"  {i}. {op_type}")
        if 'topic' in op:
            print(f"     Topic: {op['topic']}")
        if 'payload' in op:
            print(f"     Payload: {op['payload'][:50]}...")
    
    # Execute scenario operations
    engine = Engine(max_connections=5, worker_threads=2)
    print(f"\n🚀 Executing scenario operations...")
    
    for i, operation in enumerate(operations, 1):
        op_type = operation["type"]
        print(f"  Executing {i}/{len(operations)}: {op_type.replace('mqtt_', '').upper()}")
        
        if op_type == "mqtt_connect":
            result = engine.mqtt_connect(**{k: v for k, v in operation.items() if k != "type"})
        elif op_type == "mqtt_publish":
            result = engine.mqtt_publish(**{k: v for k, v in operation.items() if k != "type"})
        elif op_type == "mqtt_subscribe":
            result = engine.mqtt_subscribe(**{k: v for k, v in operation.items() if k != "type"})
        elif op_type == "mqtt_unsubscribe":
            result = engine.mqtt_unsubscribe(**{k: v for k, v in operation.items() if k != "type"})
        elif op_type == "mqtt_disconnect":
            result = engine.mqtt_disconnect(**{k: v for k, v in operation.items() if k != "type"})
        
        if not result.get('success', False):
            print(f"    ⚠️  Operation failed: {result.get('error_message', 'Unknown error')}")
        else:
            print(f"    ✅ Success ({result.get('response_time_ms', 0):.2f} ms)")


def demo_burst_publishing():
    """Demonstrate high-throughput burst publishing"""
    print("\n💥 Demo 5: Burst Publishing Performance")
    print("-" * 50)
    
    broker_host = "test.mosquitto.org"
    broker_port = 1883
    client_id = f"loadspiker_burst_demo_{int(time.time())}"
    
    # Create burst scenario
    scenario = MQTTScenario(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id=client_id,
        name="High-Throughput Burst Test"
    )
    
    message_count = 20
    print(f"Setting up burst publish test with {message_count} messages...")
    
    scenario.add_burst_publish_test(
        topic="loadspiker/demo/burst",
        message_count=message_count,
        base_payload="High-speed burst message",
        qos=0,  # Use QoS 0 for maximum speed
        retain=False
    )
    
    # Execute burst test
    engine = Engine(max_connections=10, worker_threads=4)
    engine.reset_metrics()
    
    print(f"🚀 Executing burst publish test...")
    start_time = time.time()
    
    operations = scenario.build_mqtt_operations(user_id=0)
    
    for operation in operations:
        op_type = operation["type"]
        
        if op_type == "mqtt_connect":
            engine.mqtt_connect(**{k: v for k, v in operation.items() if k != "type"})
        elif op_type == "mqtt_publish":
            engine.mqtt_publish(**{k: v for k, v in operation.items() if k != "type"})
        elif op_type == "mqtt_disconnect":
            engine.mqtt_disconnect(**{k: v for k, v in operation.items() if k != "type"})
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Display performance metrics
    metrics = engine.get_metrics()
    print(f"\n📊 Burst Test Performance Results:")
    print(f"Messages published: {message_count}")
    print(f"Total duration: {duration:.3f} seconds")
    print(f"Messages per second: {message_count / duration:.2f}")
    print(f"Total requests: {metrics.get('total_requests', 0)}")
    print(f"Successful requests: {metrics.get('successful_requests', 0)}")
    print(f"Failed requests: {metrics.get('failed_requests', 0)}")
    if metrics.get('total_requests', 0) > 0:
        avg_response_time = metrics.get('total_response_time_ms', 0) / metrics.get('total_requests', 1)
        print(f"Average response time: {avg_response_time:.2f} ms")


def demo_topic_patterns():
    """Demonstrate topic patterns and wildcards"""
    print("\n🌿 Demo 6: Topic Patterns and Wildcards")
    print("-" * 50)
    
    broker_host = "test.mosquitto.org"
    broker_port = 1883
    client_id = f"loadspiker_pattern_demo_{int(time.time())}"
    
    # Create pattern scenario
    scenario = MQTTScenario(
        broker_host=broker_host,
        broker_port=broker_port,
        client_id=client_id,
        name="Topic Pattern Test"
    )
    
    print("🎯 Setting up topic pattern test...")
    print("Pattern: loadspiker/demo/+/data (single-level wildcard)")
    
    scenario.add_topic_pattern_test(
        topic_pattern="loadspiker/demo/+/data",
        payload="Pattern test message",
        topic_count=5,
        qos=0,
        retain=False
    )
    
    # Show what topics will be used
    operations = scenario.build_mqtt_operations(user_id=0)
    print(f"\nGenerated operations:")
    
    subscribe_op = next((op for op in operations if op['type'] == 'mqtt_subscribe'), None)
    if subscribe_op:
        print(f"  📥 Subscribe to pattern: {subscribe_op['topic']}")
    
    publish_ops = [op for op in operations if op['type'] == 'mqtt_publish']
    print(f"  📤 Publishing to {len(publish_ops)} specific topics:")
    for i, op in enumerate(publish_ops, 1):
        print(f"    {i}. {op['topic']}")
    
    # Execute pattern test
    engine = Engine(max_connections=5, worker_threads=2)
    print(f"\n🚀 Executing topic pattern test...")
    
    for operation in operations:
        op_type = operation["type"]
        
        if op_type == "mqtt_connect":
            engine.mqtt_connect(**{k: v for k, v in operation.items() if k != "type"})
        elif op_type == "mqtt_subscribe":
            result = engine.mqtt_subscribe(**{k: v for k, v in operation.items() if k != "type"})
            print(f"  ✅ Subscribed to pattern: {operation['topic']}")
        elif op_type == "mqtt_publish":
            result = engine.mqtt_publish(**{k: v for k, v in operation.items() if k != "type"})
            print(f"  ✅ Published to: {operation['topic']}")
        elif op_type == "mqtt_unsubscribe":
            result = engine.mqtt_unsubscribe(**{k: v for k, v in operation.items() if k != "type"})
            print(f"  ✅ Unsubscribed from pattern: {operation['topic']}")
        elif op_type == "mqtt_disconnect":
            engine.mqtt_disconnect(**{k: v for k, v in operation.items() if k != "type"})


def demo_load_testing_scenarios():
    """Demonstrate various load testing scenarios"""
    print("\n🏋️ Demo 7: Load Testing Scenarios")
    print("-" * 50)
    
    scenarios = [
        {
            "name": "Light Load Test",
            "messages": 10,
            "description": "Basic connectivity and functionality test"
        },
        {
            "name": "Medium Load Test", 
            "messages": 50,
            "description": "Moderate throughput test"
        },
        {
            "name": "Heavy Load Test",
            "messages": 100,
            "description": "High-throughput stress test"
        }
    ]
    
    broker_host = "test.mosquitto.org"
    broker_port = 1883
    
    for test_scenario in scenarios:
        print(f"\n📊 {test_scenario['name']}")
        print(f"   {test_scenario['description']}")
        print(f"   Messages: {test_scenario['messages']}")
        
        client_id = f"loadspiker_load_test_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Create MQTT scenario
        scenario = MQTTScenario(
            broker_host=broker_host,
            broker_port=broker_port,
            client_id=client_id,
            name=test_scenario['name']
        )
        
        scenario.add_burst_publish_test(
            topic=f"loadspiker/demo/loadtest/{test_scenario['name'].lower().replace(' ', '_')}",
            message_count=test_scenario['messages'],
            base_payload=f"{test_scenario['name']} message",
            qos=0
        )
        
        # Execute load test
        engine = Engine(max_connections=20, worker_threads=8)
        engine.reset_metrics()
        
        start_time = time.time()
        operations = scenario.build_mqtt_operations(user_id=0)
        
        # Execute all operations
        for operation in operations:
            op_type = operation["type"]
            
            if op_type == "mqtt_connect":
                engine.mqtt_connect(**{k: v for k, v in operation.items() if k != "type"})
            elif op_type == "mqtt_publish":
                engine.mqtt_publish(**{k: v for k, v in operation.items() if k != "type"})
            elif op_type == "mqtt_disconnect":
                engine.mqtt_disconnect(**{k: v for k, v in operation.items() if k != "type"})
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Show results
        metrics = engine.get_metrics()
        messages_per_sec = test_scenario['messages'] / duration if duration > 0 else 0
        
        print(f"   ✅ Completed in {duration:.3f} seconds")
        print(f"   📈 Throughput: {messages_per_sec:.2f} messages/second")
        print(f"   📊 Success rate: {metrics.get('successful_requests', 0)}/{metrics.get('total_requests', 0)}")
        
        # Brief pause between tests
        time.sleep(1)


def main():
    """Run MQTT demo"""
    print_banner()
    
    try:
        # Run demo sections
        demo_basic_mqtt_operations()
        demo_qos_levels()
        demo_retained_messages()
        demo_mqtt_scenario()
        demo_burst_publishing()
        demo_topic_patterns()
        demo_load_testing_scenarios()
        
        # Final summary
        print("\n" + "=" * 70)
        print("🎉 MQTT Demo Completed Successfully!")
        print("=" * 70)
        print("This demo showcased:")
        print("✅ Basic MQTT operations (connect, publish, subscribe, disconnect)")
        print("✅ Quality of Service levels (QoS 0, 1, 2)")
        print("✅ Retained message functionality")
        print("✅ Scenario-based testing with MQTTScenario")
        print("✅ High-throughput burst publishing")
        print("✅ Topic patterns and wildcards")
        print("✅ Various load testing scenarios")
        print("\n💡 Next Steps:")
        print("• Try connecting to your own MQTT broker")
        print("• Experiment with different QoS levels and message sizes")
        print("• Create custom scenarios for your use cases")
        print("• Scale up the load tests for performance analysis")
        print("• Integrate with your monitoring and alerting systems")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
        print("Exiting gracefully...")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
