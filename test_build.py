#!/usr/bin/env python3
"""
Test script to verify the build works
"""
import sys
import os

# Add the current directory to path so we can import our module
sys.path.insert(0, '.')

# Add the built library to path
sys.path.insert(0, 'obj')

try:
    # Test importing the C extension directly
    import loadtest
    print("✅ Successfully imported loadtest module")
    
    # Test creating engine
    engine = loadtest.Engine(100, 4)
    print("✅ Successfully created Engine")
    
    # Test getting metrics (should be empty initially)
    metrics = engine.get_metrics()
    print(f"✅ Got metrics: {metrics}")
    
    print("\n🎉 Build test successful! The C extension is working.")
    
except ImportError as e:
    print(f"❌ Failed to import loadtest module: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error testing engine: {e}")
    sys.exit(1)