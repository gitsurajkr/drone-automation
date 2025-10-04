#!/usr/bin/env python3
"""
Enhanced Main with Autonomous Mission Support
============================================
Integrates autonomous waypoint missions with the existing WebSocket server.
"""

import asyncio
from ws_server.ws_server import start_ws_server
from config import WS_HOST, WS_PORT
from autonomous_waypoint_mission import AutonomousWaypointMission

class DroneControlSystem:
    """Enhanced drone control system with autonomous mission support."""
    
    def __init__(self):
        self.mission = None
        self.mission_active = False
    
    async def start_autonomous_mission(self, waypoints):
        """Start an autonomous waypoint mission."""
        if self.mission_active:
            print("⚠️ Mission already active")
            return False
        
        try:
            print("🚀 Starting autonomous mission...")
            self.mission = AutonomousWaypointMission()
            self.mission_active = True
            
            success = await self.mission.execute_waypoint_mission(waypoints)
            
            if success:
                print("✅ Autonomous mission completed successfully!")
            else:
                print("❌ Autonomous mission failed")
            
            return success
            
        except Exception as e:
            print(f"❌ Mission error: {e}")
            return False
        finally:
            self.mission_active = False
            self.mission = None
    
    def stop_mission(self):
        """Stop current mission."""
        if self.mission and self.mission_active:
            self.mission.set_manual_override(True)
            print("⚠️ Mission stopped - manual override activated")
            return True
        return False

async def run_test_mission():
    """Run a test autonomous mission."""
    print("🧪 Running Test Autonomous Mission")
    print("=" * 40)
    
    # Test waypoints (replace with your coordinates)
    test_waypoints = [
        (28.459497, 77.026638, 20),
        (28.459800, 77.027000, 20),
        (28.460000, 77.026800, 20),
    ]
    
    control_system = DroneControlSystem()
    success = await control_system.start_autonomous_mission(test_waypoints)
    
    return success

async def run_websocket_server():
    """Run the WebSocket server."""
    print(f"🌐 Starting WebSocket server at ws://{WS_HOST}:{WS_PORT}...")
    await start_ws_server()

async def main():
    """Main entry point with multiple modes."""
    import sys
    
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        
        if mode == "mission" or mode == "autonomous":
            # Run autonomous mission mode
            await run_test_mission()
            
        elif mode == "server" or mode == "websocket":
            # Run WebSocket server mode
            await run_websocket_server()
            
        elif mode == "both":
            # Run both (for advanced users)
            print("🚀 Starting integrated system...")
            # You could run both WebSocket server and mission system here
            # This would require more complex integration
            await run_websocket_server()
            
        elif mode == "help":
            print("""
🚁 Drone Control System - Usage
==============================

MODES:
  python main.py mission     - Run autonomous waypoint mission
  python main.py server      - Run WebSocket server (default)
  python main.py both        - Run integrated system
  python main.py help        - Show this help

AUTONOMOUS MISSION:
  - Fully automated waypoint navigation
  - Pre-flight safety checks
  - Battery and GPS monitoring
  - Emergency failsafe procedures
  - Mission logging and telemetry

WEBSOCKET SERVER:
  - Manual drone control via web interface
  - Real-time telemetry streaming
  - Interactive control panel
            """)
        else:
            print(f"❌ Unknown mode: {mode}")
            print("Use 'python main.py help' for usage information")
    else:
        # Default: run WebSocket server
        await run_websocket_server()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 System shutdown requested by user.")
    except Exception as e:
        print(f"❌ System encountered an error: {e}")
        import traceback
        traceback.print_exc()