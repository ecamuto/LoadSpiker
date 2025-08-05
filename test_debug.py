#!/usr/bin/env python3
"""
Debug test to isolate segmentation fault
"""
import sys
import os
sys.path.insert(0, '.')

def test_direct_import():
    """Test importing the C extension directly"""
    print("🔍 Testing direct import of loadtest module...")
    try:
        import loadtest
        print("✅ Successfully imported loadtest module")
        return True
    except ImportError as e:
        print(f"❌ Failed to import loadtest: {e}")
        return False
    except Exception as e:
        print(f"❌ Error importing loadtest: {e}")
        return False

def test_engine_creation():
    """Test creating the Engine object"""
    print("🔍 Testing Engine creation...")
    try:
        import loadtest
        engine = loadtest.Engine(10, 2)
        print("✅ Successfully created Engine")
        return engine
    except Exception as e:
        print(f"❌ Failed to create Engine: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_simple_request():
    """Test making a simple request"""
    print("🔍 Testing simple request...")
    try:
        import loadtest
        engine = loadtest.Engine(10, 2)
        print("   Engine created, making request...")
        
        response = engine.execute_request(
            url="https://httpbin.org/get",
            method="GET",
            headers="",
            body="",
            timeout_ms=30000
        )
        print(f"✅ Request successful: {response}")
        return True
    except Exception as e:
        print(f"❌ Request failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🐛 LoadSpiker Debug Test")
    print("=" * 40)
    
    # Test 1: Direct import
    if not test_direct_import():
        return False
    
    # Test 2: Engine creation
    engine = test_engine_creation()
    if not engine:
        return False
    
    # Test 3: Simple request
    if not test_simple_request():
        return False
    
    print("\n🎉 All debug tests passed!")
    return True

if __name__ == '__main__':
    if not main():
        sys.exit(1)
