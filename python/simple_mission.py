#!/usr/bin/env python3
"""
Simple Direct Waypoint Mission
=============================
Just run waypoints directly without any extra tools.
"""

import asyncio
from autonomous_waypoint_mission import AutonomousWaypointMission

async def run_direct_mission():
    """Run a mission directly with hardcoded waypoints."""
    
    print("🚁 Direct Waypoint Mission")
    print("=" * 30)
    
    # Define your waypoints here (replace with your GPS coordinates)
    waypoints = [
        (28.459497, 77.026638, 20),  # Waypoint 1
        (28.459800, 77.027000, 20),  # Waypoint 2  
        (28.460000, 77.026800, 20),  # Waypoint 3
    ]
    
    # Create and run mission
    mission = AutonomousWaypointMission()
    success = await mission.execute_waypoint_mission(waypoints)
    
    if success:
        print("✅ Mission completed!")
    else:
        print("❌ Mission failed!")

if __name__ == "__main__":
    asyncio.run(run_direct_mission())