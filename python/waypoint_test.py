#!/usr/bin/env python3
"""
Simple Autonomous Waypoint Mission Test
======================================
A simple script to test the autonomous waypoint navigation system.
"""

import asyncio
from autonomous_waypoint_mission import AutonomousWaypointMission

async def run_simple_mission():
    """Run a simple predefined mission for testing."""
    
    print("🚁 Simple Autonomous Mission Test")
    print("=" * 40)
    
    # Define test waypoints (replace with your actual GPS coordinates)
    waypoints = [
        # Format: (latitude, longitude, altitude_in_meters)
        (28.459497, 77.026638, 20),  # Waypoint 1
        (28.459800, 77.027000, 20),  # Waypoint 2  
        (28.460000, 77.026800, 20),  # Waypoint 3
        (28.459700, 77.026500, 20),  # Waypoint 4 (return near start)
    ]
    
    print(f"📍 Mission plan: {len(waypoints)} waypoints")
    for i, (lat, lon, alt) in enumerate(waypoints, 1):
        print(f"   Waypoint {i}: {lat:.6f}, {lon:.6f}, {alt}m")
    
    # Create mission instance
    mission = AutonomousWaypointMission()
    
    # You can customize mission parameters here:
    mission.takeoff_altitude = 15.0  # meters
    mission.default_altitude = 20.0  # meters  
    mission.critical_battery_level = 25.0  # percentage
    mission.min_waypoint_distance = 2.0  # meters
    
    try:
        # Execute the mission
        print(f"\n🚀 Starting mission execution...")
        success = await mission.execute_waypoint_mission(waypoints)
        
        if success:
            print("\n🎉 MISSION COMPLETED SUCCESSFULLY!")
            print("✅ All waypoints reached")
            print("✅ Safe return to launch")
            print("✅ Landing completed")
        else:
            print("\n❌ MISSION FAILED!")
            print("⚠️ Check logs for details")
            
    except KeyboardInterrupt:
        print("\n⚠️ Mission interrupted by user")
        print("🔄 Attempting safe return...")
        # The mission class will handle cleanup automatically
    
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        print("🚨 Emergency procedures activated")

async def run_custom_mission():
    """Run a mission with user-defined waypoints."""
    
    print("🚁 Custom Waypoint Mission")
    print("=" * 40)
    
    waypoints = []
    
    print("📍 Enter waypoints (press Enter without input to finish):")
    print("   Format: latitude,longitude,altitude")
    print("   Example: 28.459497,77.026638,20")
    
    while True:
        try:
            user_input = input(f"Waypoint {len(waypoints)+1}: ").strip()
            
            if not user_input:
                break
                
            parts = [p.strip() for p in user_input.split(',')]
            
            if len(parts) < 2:
                print("❌ Need at least latitude and longitude")
                continue
                
            lat = float(parts[0])
            lon = float(parts[1])
            alt = float(parts[2]) if len(parts) > 2 else 20.0
            
            # Basic validation
            if not (-90 <= lat <= 90):
                print("❌ Latitude must be between -90 and 90")
                continue
                
            if not (-180 <= lon <= 180):
                print("❌ Longitude must be between -180 and 180")
                continue
                
            if alt < 1 or alt > 100:
                print("❌ Altitude should be between 1 and 100 meters")
                continue
            
            waypoints.append((lat, lon, alt))
            print(f"✅ Added: {lat:.6f}, {lon:.6f}, {alt}m")
            
        except ValueError:
            print("❌ Invalid format. Use: latitude,longitude,altitude")
        except KeyboardInterrupt:
            print("\n⚠️ Cancelled")
            return
    
    if not waypoints:
        print("❌ No waypoints provided")
        return
    
    print(f"\n📋 Mission Summary:")
    print(f"   Total waypoints: {len(waypoints)}")
    
    # Calculate approximate mission distance
    total_distance = 0
    for i in range(len(waypoints) - 1):
        # Simple distance calculation (not precise but good enough for estimate)
        lat1, lon1, _ = waypoints[i]
        lat2, lon2, _ = waypoints[i + 1]
        distance = ((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2) ** 0.5 * 111000  # Rough conversion to meters
        total_distance += distance
    
    print(f"   Approximate distance: {total_distance:.0f}m")
    print(f"   Estimated flight time: {(total_distance / 10):.0f} seconds (at 10m/s)")
    
    # Confirm mission start
    confirm = input("\n🚀 Start mission? (y/N): ").strip().lower()
    if confirm != 'y':
        print("❌ Mission cancelled")
        return
    
    # Execute mission
    mission = AutonomousWaypointMission()
    await mission.execute_waypoint_mission(waypoints)

def print_usage():
    """Print usage instructions."""
    print("""
🚁 Autonomous Waypoint Mission System
===================================

USAGE:
  python waypoint_test.py [mode]

MODES:
  simple   - Run predefined test mission
  custom   - Enter waypoints interactively  
  help     - Show this help message

FEATURES:
✅ Autonomous waypoint navigation
✅ Pre-flight safety checks
✅ Battery monitoring & failsafe
✅ GPS monitoring & recovery
✅ Manual override capability
✅ Connection loss handling
✅ Mission logging & telemetry
✅ CSV telemetry export

SAFETY FEATURES:
🛡️ Pre-flight checks (GPS, battery, armable status)
🛡️ Automatic RTL on critical battery (<25%)
🛡️ GPS loss recovery (ALT_HOLD + recovery attempt)
🛡️ Mode safeguard (auto-return to GUIDED)
🛡️ Connection loss detection
🛡️ Manual override (switch to LOITER)
🛡️ Emergency landing procedures

REQUIREMENTS:
- Drone must be connected and ready
- GPS lock required (fix_type >= 3)
- Battery > 30% for takeoff
- Clear flight area
- Valid GPS coordinates for waypoints

EXAMPLE WAYPOINTS:
  Delhi area: 28.459497,77.026638,20
  Mumbai area: 19.076090,72.877426,20
  Bangalore area: 12.971599,77.594566,20
""")

async def main():
    """Main entry point."""
    import sys
    
    if len(sys.argv) < 2:
        mode = "simple"  # Default mode
    else:
        mode = sys.argv[1].lower()
    
    if mode == "help" or mode == "-h" or mode == "--help":
        print_usage()
    elif mode == "simple":
        await run_simple_mission()
    elif mode == "custom":
        await run_custom_mission()
    else:
        print(f"❌ Unknown mode: {mode}")
        print("Use 'python waypoint_test.py help' for usage information")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Mission terminated by user")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()