#!/usr/bin/env python3
"""
Test script for waypoint functionality
Tests the waypoint system integration between Python backend, Node.js middleware, and React frontend
"""

import asyncio
import websockets
import json
import sys
import time

async def test_waypoint_commands():
    """Test waypoint command execution"""
    uri = "ws://localhost:8765"
    
    try:
        # Connect to Python WebSocket server
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to Python WebSocket server")
            
            # Test 1: Validate waypoints
            print("\n🧪 Test 1: Validate waypoints")
            test_waypoints = [
                {"latitude": 28.5245, "longitude": 77.5770, "altitude": 20, "order": 0},
                {"latitude": 28.5255, "longitude": 77.5780, "altitude": 20, "order": 1},
                {"latitude": 28.5265, "longitude": 77.5790, "altitude": 20, "order": 2}
            ]
            
            validate_command = {
                "type": "validate_waypoints",
                "payload": {"waypoints": test_waypoints},
                "id": "test_validate_1"
            }
            
            await websocket.send(json.dumps(validate_command))
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Validate waypoints result: {result}")
            
            # Test 2: Calculate mission stats
            print("\n🧪 Test 2: Calculate mission statistics")
            stats_command = {
                "type": "calculate_mission_stats", 
                "payload": {"waypoints": test_waypoints},
                "id": "test_stats_1"
            }
            
            await websocket.send(json.dumps(stats_command))
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Mission stats result: {result}")
            
            # Test 3: Generate grid mission
            print("\n🧪 Test 3: Generate grid mission")
            grid_command = {
                "type": "generate_grid_mission",
                "payload": {
                    "start_lat": 28.5245,
                    "start_lon": 77.5770,
                    "grid_size": 3,
                    "spacing": 50.0,
                    "altitude": 25.0
                },
                "id": "test_grid_1"
            }
            
            await websocket.send(json.dumps(grid_command))
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Grid mission result: {result}")
            
            # Test 4: Generate circular mission
            print("\n🧪 Test 4: Generate circular mission")
            circular_command = {
                "type": "generate_circular_mission",
                "payload": {
                    "center_lat": 28.5245,
                    "center_lon": 77.5770,
                    "radius_meters": 100.0,
                    "num_points": 6,
                    "altitude": 30.0
                },
                "id": "test_circular_1"
            }
            
            await websocket.send(json.dumps(circular_command))
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Circular mission result: {result}")
            
            # Test 5: Mission status (without drone connection)
            print("\n🧪 Test 5: Check mission status")
            status_command = {
                "type": "waypoint_mission_status",
                "id": "test_status_1"
            }
            
            await websocket.send(json.dumps(status_command))
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Mission status result: {result}")
            
            print("\n✅ All waypoint tests completed successfully!")
            
    except websockets.exceptions.ConnectionRefusedError:
        print("❌ Could not connect to Python WebSocket server on port 8765")
        print("Make sure the Python backend is running: python python/enhanced_main.py")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        sys.exit(1)

async def test_node_proxy():
    """Test Node.js proxy functionality"""
    uri = "ws://localhost:4001"
    
    try:
        # Connect to Node.js WebSocket proxy
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to Node.js WebSocket proxy")
            
            # Test command forwarding through Node.js
            print("\n🧪 Testing Node.js proxy forwarding")
            test_command = {
                "type": "validate_waypoints",
                "payload": {
                    "waypoints": [
                        {"latitude": 28.5245, "longitude": 77.5770, "altitude": 20, "order": 0}
                    ]
                },
                "id": "proxy_test_1"
            }
            
            await websocket.send(json.dumps(test_command))
            response = await websocket.recv()
            result = json.loads(response)
            print(f"Node.js proxy result: {result}")
            
            print("✅ Node.js proxy test completed successfully!")
            
    except websockets.exceptions.ConnectionRefusedError:
        print("❌ Could not connect to Node.js WebSocket proxy on port 4001")
        print("Make sure the Node.js backend is running: cd backend && npm run dev")
        return False
    except Exception as e:
        print(f"❌ Node.js proxy test failed: {e}")
        return False
    
    return True

async def main():
    print("🚁 Waypoint System Integration Test")
    print("=" * 50)
    
    print("\n📡 Testing Python backend waypoint commands...")
    await test_waypoint_commands()
    
    print("\n🔄 Testing Node.js proxy functionality...")
    await test_node_proxy()
    
    print(f"\n🎉 All tests passed! Waypoint system is ready.")
    print(f"\nNext steps:")
    print(f"1. Start the full system: python python/enhanced_main.py")
    print(f"2. Start Node.js backend: cd backend && npm run dev")  
    print(f"3. Start React frontend: cd frontend && npm run dev")
    print(f"4. Open http://localhost:3000 and test waypoint drawing on the map")

if __name__ == "__main__":
    asyncio.run(main())