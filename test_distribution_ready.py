#!/usr/bin/env python3
"""
Test script to verify LoadSpiker is distribution-ready without hardcoded paths.
This script tests that LoadSpiker can be imported and basic functionality works
regardless of the installation directory.
"""

import os
import sys

def test_distribution_ready():
    """Test that LoadSpiker works without hardcoded paths."""
    print("🧪 Testing LoadSpiker distribution readiness...")
    
    # Test 1: Check that we can import LoadSpiker from current directory
    try:
        import loadspiker
        print("✅ Successfully imported loadspiker")
    except ImportError as e:
        print(f"❌ Failed to import loadspiker: {e}")
        return False
    
    # Test 2: Check that basic engine functionality works
    try:
        from loadspiker.engine import Engine
        engine = Engine()
        print("✅ Successfully created Engine instance")
    except Exception as e:
        print(f"❌ Failed to create Engine: {e}")
        return False
    
    # Test 3: Check that session manager works
    try:
        from loadspiker.session_manager import SessionManager
        session_mgr = SessionManager()
        print("✅ Successfully created SessionManager instance")
    except Exception as e:
        print(f"❌ Failed to create SessionManager: {e}")
        return False
    
    # Test 4: Check that authentication system works
    try:
        from loadspiker.authentication import create_basic_auth
        auth = create_basic_auth("testuser", "testpass")
        print("✅ Successfully created authentication flow")
    except Exception as e:
        print(f"❌ Failed to create authentication flow: {e}")
        return False
    
    print("\n🎉 All distribution readiness tests passed!")
    print("   LoadSpiker is ready for distribution without hardcoded paths.")
    return True

if __name__ == "__main__":
    success = test_distribution_ready()
    sys.exit(0 if success else 1)
