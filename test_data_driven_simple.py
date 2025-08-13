#!/usr/bin/env python3
"""
Simple test for CSV data-driven load testing that bypasses import issues
"""

import sys
import os

def test_data_sources_directly():
    """Test data sources by importing modules directly"""
    print("🧪 Testing CSV Data-Driven System (Direct Module Import)")
    print("=" * 60)
    
    try:
        # Add loadspiker directory to path
        sys.path.insert(0, './loadspiker')
        
        # Import modules directly
        import data_sources
        import scenarios
        
        # Test 1: CSV Data Source
        print("\n1. Testing CSV Data Source...")
        csv_source = data_sources.CSVDataSource("test_csv_data.csv")
        csv_source.load_data()
        print(f"   ✅ Loaded {csv_source.get_row_count()} rows")
        print(f"   ✅ Columns: {', '.join(csv_source.get_columns())}")
        
        # Test 2: Data Distribution
        print("\n2. Testing data distribution...")
        distributor = data_sources.DataDistributor(csv_source, data_sources.DataStrategy.SEQUENTIAL)
        
        for user_id in range(3):
            user_data = distributor.get_data_for_user(user_id)
            print(f"   User {user_id}: {user_data['username']} ({user_data['email']})")
        
        # Test 3: Scenario Integration
        print("\n3. Testing scenario integration...")
        scenario = scenarios.Scenario("CSV Test")
        scenario.load_data_file("test_csv_data.csv", strategy="sequential")
        
        data_info = scenario.get_data_info()
        print(f"   ✅ Scenario loaded {data_info['total_rows']} rows")
        print(f"   ✅ Strategy: {data_info['strategy']}")
        
        # Test 4: Variable Substitution
        print("\n4. Testing variable substitution...")
        scenario.add_request(scenarios.HTTPRequest(
            url="https://api.example.com/login",
            method="POST",
            body='{"username": "${data.username}", "password": "${data.password}"}'
        ))
        
        requests = scenario.build_requests(0)
        print(f"   ✅ Generated request with substituted data: {requests[0]['body']}")
        
        print("\n🎉 All tests passed! CSV data-driven system is working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_data_sources_directly()
    if success:
        print("\n📚 System is ready for:")
        print("- Data-driven load testing with CSV files")  
        print("- Multiple distribution strategies")
        print("- Variable substitution in requests")
        print("- Multi-source data scenarios")
