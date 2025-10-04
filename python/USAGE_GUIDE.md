# How to Use the Autonomous Waypoint System

## 🎯 What You Actually Need

You only need **ONE** of these files to run autonomous missions:

### Core Files (Required):
- `autonomous_waypoint_mission.py` - The main autonomous system
- `controller.py` - Your existing drone controller
- `connection.py` - Your existing connection handler
- `safety_config.py` - Your existing safety configuration

### Helper Files (Optional):
- `mission_planner.py` - Plan missions beforehand (optional)
- `waypoint_test.py` - Test scripts (optional)
- `simple_mission.py` - Minimal example (optional)

## 🚀 Three Ways to Run Missions

### 1. Simplest Way - Direct Script
```bash
python simple_mission.py
```

### 2. Test Different Scenarios
```bash
python waypoint_test.py simple    # Predefined test mission
python waypoint_test.py custom    # Enter waypoints interactively
```

### 3. Integrated with Your System
```bash
python enhanced_main.py mission   # Run autonomous mission
python enhanced_main.py server    # Run your normal WebSocket server
```

## 📝 Quick Example Code

If you want to add autonomous missions to your **existing code**, just add this:

```python
from autonomous_waypoint_mission import AutonomousWaypointMission

async def run_my_mission():
    # Your waypoints (replace with real GPS coordinates)
    waypoints = [
        (28.459497, 77.026638, 20),  # lat, lon, altitude
        (28.459800, 77.027000, 20),
        (28.460000, 77.026800, 20),
    ]
    
    # Create and run mission
    mission = AutonomousWaypointMission()
    success = await mission.execute_waypoint_mission(waypoints)
    
    return success

# Run it
asyncio.run(run_my_mission())
```

## 🗑️ What You Can Delete

If you want to keep it simple, you can **delete** these optional files:
- `mission_planner.py` (just a planning tool)
- `waypoint_test.py` (just test scripts)
- `simple_mission.py` (just an example)
- `enhanced_main.py` (just an example integration)

**Keep only:**
- `autonomous_waypoint_mission.py` (the core system)

## 🎮 What It Does

The `AutonomousWaypointMission` class handles everything:

✅ **Pre-flight checks** - GPS, battery, armable status
✅ **Automatic takeoff** - Arms and takes off to safe altitude  
✅ **Waypoint navigation** - Flies to each GPS coordinate
✅ **Safety monitoring** - Battery, GPS, connection monitoring
✅ **Emergency handling** - RTL on low battery, GPS loss recovery
✅ **Automatic landing** - RTL and safe landing after mission
✅ **Mission logging** - Saves telemetry and mission summary

## 🔧 Integration Example

To add this to your existing WebSocket system:

```python
# In your WebSocket message handler
async def handle_start_mission(waypoints):
    mission = AutonomousWaypointMission()
    success = await mission.execute_waypoint_mission(waypoints)
    
    # Send success/failure back to frontend
    await websocket.send(json.dumps({
        "type": "mission_complete",
        "success": success
    }))
```

## 📍 Waypoint Format

Just use simple tuples:
```python
waypoints = [
    (latitude, longitude, altitude_in_meters),
    (28.459497, 77.026638, 20),
    (28.459800, 77.027000, 20),
]
```

That's it! The system handles all the complexity for you.