# Autonomous Waypoint Navigation System

A comprehensive autonomous drone navigation system with safety features, failsafe mechanisms, and telemetry logging.

## 🚁 Features

### Core Navigation
- **Autonomous waypoint navigation** - Sequential navigation through GPS coordinates
- **Pre-flight safety checks** - Comprehensive checks before mission start
- **Intelligent takeoff** - Automated arming and takeoff to safe altitude
- **Precision landing** - Automatic RTL and safe landing

### Safety & Failsafe
- **Battery monitoring** - Automatic RTL when battery < 25%
- **GPS monitoring** - ALT_HOLD and recovery attempt if GPS lost
- **Mode safeguard** - Auto-return to GUIDED mode if changed
- **Connection monitoring** - Emergency RTL on connection loss
- **Manual override** - Switch to LOITER mode for manual control
- **Emergency procedures** - Multiple fallback options

### Telemetry & Logging
- **Real-time telemetry** - Position, battery, GPS status monitoring
- **Mission logging** - Complete mission summary with statistics
- **CSV export** - Detailed telemetry data export
- **Status messages** - User-friendly progress updates

## 📋 Requirements

### Hardware
- Compatible drone with MAVLink protocol
- GPS module with 3D fix capability
- Battery level monitoring
- Stable radio/WiFi connection

### Software
- Python 3.7+
- DroneKit-Python
- asyncio support
- Required Python modules (see requirements)

### Pre-flight Conditions
- Drone must be armable (`vehicle.is_armable == True`)
- GPS fix type ≥ 3 (3D fix)
- Battery level > 30%
- Clear flight area
- Valid GPS coordinates for waypoints

## 🚀 Quick Start

### 1. Simple Test Mission
```bash
python waypoint_test.py simple
```

### 2. Custom Waypoint Mission
```bash
python waypoint_test.py custom
```

### 3. Help and Usage
```bash
python waypoint_test.py help
```

## 📍 Waypoint Format

Waypoints are defined as tuples: `(latitude, longitude, altitude)`

```python
waypoints = [
    (28.459497, 77.026638, 20),  # Delhi area
    (28.459800, 77.027000, 20),  # 20 meters altitude
    (28.460000, 77.026800, 20),  # Sequential navigation
]
```

### Waypoint Validation
- **Coordinates**: Must be valid GPS coordinates
- **Altitude**: Automatically clamped to safety limits (0.5m - 50m)
- **Distance**: Waypoints < 2m apart are automatically merged
- **Default altitude**: 20m if not specified

## 🛡️ Safety Features

### Pre-Flight Checks
```
✅ Vehicle armable status
✅ GPS fix type ≥ 3
✅ Battery level > 30%
✅ GUIDED mode activation
✅ Connection stability
```

### During Flight Monitoring
```
🔋 Battery: RTL if < 25%
📡 GPS: ALT_HOLD + recovery if lost
🎮 Mode: Auto-return to GUIDED
📶 Connection: Emergency RTL if lost
👨‍✈️ Manual: Switch to LOITER on override
```

### Emergency Procedures
1. **Critical Battery**: Automatic RTL
2. **GPS Loss**: ALT_HOLD → Wait 15s → RTL or LAND
3. **Connection Loss**: Immediate RTL
4. **Manual Override**: Switch to LOITER mode
5. **Mission Failure**: Emergency landing procedures

## 📊 Mission Configuration

### Default Parameters
```python
mission = AutonomousWaypointMission()

# Altitude settings
mission.takeoff_altitude = 15.0      # Takeoff height (meters)
mission.default_altitude = 20.0      # Default waypoint altitude

# Safety thresholds  
mission.critical_battery_level = 25.0  # RTL trigger (%)
mission.min_waypoint_distance = 2.0    # Merge threshold (meters)
mission.gps_recovery_timeout = 15.0     # GPS recovery wait (seconds)
```

### Custom Configuration
```python
# Create mission with custom settings
mission = AutonomousWaypointMission(connection_string="udp:127.0.0.1:14550")

# Customize parameters
mission.takeoff_altitude = 25.0
mission.critical_battery_level = 30.0

# Execute mission
await mission.execute_waypoint_mission(waypoints)
```

## 📈 Telemetry Output

### Real-time Console Output
```
📊 Telemetry - Lat: 28.459497, Lon: 77.026638, Alt: 20.1m, Battery: 87%, GPS: 3, Mode: GUIDED
📍 Flying to waypoint 2/3
   Distance to target: 15.2m
✅ Reached waypoint 2/3
```

### Mission Summary
```
📈 Mission Stats:
   Duration: 245.3 seconds
   Waypoints visited: 3
   Minimum battery: 78.2%
```

### CSV Export
Detailed telemetry data exported to timestamped CSV files:
- Position data (lat, lon, alt)
- Battery levels and voltage
- GPS status and satellite count
- Flight mode and ground speed
- Timestamps for analysis

## 🔧 Advanced Usage

### Integration with Existing Code
```python
from autonomous_waypoint_mission import AutonomousWaypointMission

async def my_mission():
    mission = AutonomousWaypointMission()
    
    # Define waypoints
    waypoints = [(lat1, lon1, alt1), (lat2, lon2, alt2)]
    
    # Execute mission
    success = await mission.execute_waypoint_mission(waypoints)
    
    return success
```

### Manual Override
```python
# During mission execution
mission.set_manual_override(True)  # Switch to LOITER mode
mission.set_manual_override(False) # Resume mission
```

### Custom Failsafe Actions
```python
# Override failsafe behavior
def custom_battery_failsafe(self, battery_level):
    if battery_level < 20:
        self.trigger_emergency_land("Custom battery failsafe")
    elif battery_level < 30:
        self.trigger_emergency_rtl("Low battery warning")
```

## 📁 File Output

### Mission Summary (`mission_summary_YYYYMMDD_HHMMSS.json`)
```json
{
  "mission_date": "2025-10-04T10:30:00",
  "mission_duration_seconds": 245.3,
  "waypoints_visited": 3,
  "min_battery_level": 78.2,
  "telemetry_points": 245
}
```

### Telemetry Data (`mission_telemetry_YYYYMMDD_HHMMSS.csv`)
```csv
timestamp,lat,lon,alt,battery_level,battery_voltage,gps_fix,satellites,groundspeed,mode
2025-10-04T10:30:00,28.459497,77.026638,20.1,87.5,12.6,3,8,5.2,GUIDED
```

## 🚨 Troubleshooting

### Common Issues

#### "Vehicle not armable"
- Check GPS lock (need 3D fix)
- Verify battery level > 30%
- Ensure proper calibration
- Check for error messages

#### "GPS fix insufficient"
- Wait for satellite lock (may take 1-2 minutes)
- Check antenna orientation
- Verify GPS module health
- Move to open area

#### "Battery too low"
- Charge battery to > 30%
- Check battery voltage levels
- Verify battery monitoring calibration

#### "Connection failed"
- Verify connection string
- Check radio/WiFi link
- Confirm MAVLink protocol
- Test with basic connection first

### Debug Mode
Enable debug logging for detailed troubleshooting:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## ⚠️ Safety Warnings

### Important Notes
- **Always maintain visual line of sight**
- **Check local regulations and airspace**
- **Test in safe, open areas first**
- **Have manual override ready**
- **Monitor weather conditions**
- **Ensure adequate battery for return**

### Pre-flight Checklist
- [ ] GPS lock achieved (≥6 satellites)
- [ ] Battery > 30% and healthy
- [ ] Flight area clear of obstacles
- [ ] Weather conditions suitable
- [ ] Emergency procedures reviewed
- [ ] Manual override tested

## 📞 Support

For issues, questions, or contributions:
1. Check troubleshooting section
2. Review console output and logs
3. Test with simple waypoint missions first
4. Verify all safety requirements met

## 📄 License

This autonomous waypoint navigation system is provided for educational and research purposes. Users are responsible for compliance with local regulations and safe operation.

---

**🚁 Safe flying! Remember: Safety first, automation second.**