#!/usr/bin/env python3
"""
Test script for SITL functionality.
This script demonstrates the enhanced SITL features:
1. Auto-disables ARMING_CHECK
2. Ensures GUIDED mode before arming
3. Waits for arm confirmation
4. Provides safe takeoff functionality

To use with SITL:
1. Start SITL: sim_vehicle.py --console --map
2. Update config.py: DEFAULT_CONNECTION_STRING = "tcp:127.0.0.1:5760"
3. Run this test script: python test_sitl.py
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from connection import Connection
from controller import Controller

async def test_sitl_functionality():
    """Test the enhanced SITL functionality."""
    print("🚁 Testing SITL Functionality")
    print("=" * 50)
    
    # Connect to vehicle
    conn = Connection()
    connection_string = "tcp:127.0.0.1:5760"  # SITL default
    
    print(f"Connecting to SITL at {connection_string}...")
    connected = await conn.connect(connection_string, 115200)
    
    if not connected or conn.vehicle is None:
        print("❌ Failed to connect to SITL")
        return False
    
    print("✅ Connected to SITL")
    
    try:
        # Create controller
        controller = Controller(conn)
        
        # Test 1: Setup SITL configuration
        print("\n🔧 Step 1: Setting up SITL configuration...")
        setup_result = await controller.setup_sitl_connection()
        if setup_result:
            print("✅ SITL setup successful")
        else:
            print("❌ SITL setup failed")
            return False
        
        # Test 2: Arm the vehicle (should automatically set GUIDED mode)
        print("\n🔫 Step 2: Arming vehicle...")
        arm_result = await controller.arm()
        if arm_result:
            print("✅ Vehicle armed successfully")
        else:
            print("❌ Failed to arm vehicle")
            return False
        
        # Test 3: Takeoff to 10 meters
        print("\n🚀 Step 3: Taking off to 10 meters...")
        takeoff_result = await controller.takeoff(10.0)
        if takeoff_result:
            print("✅ Takeoff successful")
        else:
            print("❌ Takeoff failed")
            return False
        
        # Wait a bit to enjoy the flight
        print("\n⏳ Hovering for 5 seconds...")
        await asyncio.sleep(5)
        
        # Test 4: Disarm (this will cause the vehicle to land/crash in SITL)
        print("\n🛑 Step 4: Disarming vehicle...")
        disarm_result = await controller.disarm()
        if disarm_result:
            print("✅ Vehicle disarmed successfully")
        else:
            print("❌ Failed to disarm vehicle")
        
        print("\n🎉 All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        return False
    
    finally:
        # Cleanup
        if conn and conn.is_connected:
            await conn.disconnect()
            print("🔌 Disconnected from SITL")

def main():
    """Main entry point."""
    print("SITL Test Script")
    print("Make sure SITL is running: sim_vehicle.py --console --map")
    print("Press Ctrl+C to exit\n")
    
    try:
        asyncio.run(test_sitl_functionality())
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()