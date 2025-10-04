#!/usr/bin/env python3
"""
Fully Autonomous Waypoint Navigation System
==========================================
Implements complete autonomous waypoint navigation with safety, failsafe, and telemetry logging.

Features:
- Pre-flight safety checks
- Autonomous waypoint navigation
- Battery monitoring and failsafe
- GPS monitoring and recovery
- Manual override capability
- Connection loss handling
- Mission logging and telemetry
"""

import asyncio
import json
import csv
import time
import threading
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict, Any
import math

# Import dronekit components
try:
    from dronekit import VehicleMode, LocationGlobalRelative
except ImportError:
    print("Warning: dronekit not available - using mock objects for development")
    class VehicleMode:
        def __init__(self, mode): self.name = mode
    class LocationGlobalRelative:
        def __init__(self, lat, lon, alt): self.lat, self.lon, self.alt = lat, lon, alt

from controller import Controller
from connection import create_connection
from safety_config import SafetyConfig, FlightLogger


class AutonomousWaypointMission:
    """Autonomous waypoint navigation with comprehensive safety features."""
    
    def __init__(self, connection_string: str = None):
        self.connection_string = connection_string
        self.connection = None
        self.controller = None
        self.vehicle = None
        self.flight_logger = FlightLogger()
        
        # Mission parameters
        self.default_altitude = 20.0  # meters
        self.takeoff_altitude = 15.0  # meters
        self.min_waypoint_distance = 2.0  # meters
        
        # Failsafe parameters
        self.critical_battery_level = 25.0  # percentage
        self.gps_recovery_timeout = 15.0  # seconds
        
        # Mission state
        self.mission_active = False
        self.manual_override = False
        self.mission_start_time = None
        self.waypoints_visited = 0
        self.min_battery_recorded = 100.0
        self.telemetry_data = []
        
        # Threading
        self.telemetry_thread = None
        self.failsafe_thread = None
        self.stop_monitoring = threading.Event()

    async def initialize_connection(self) -> bool:
        """Initialize connection to the drone."""
        try:
            print("🔌 Initializing connection to drone...")
            
            if self.connection_string:
                self.connection = create_connection(self.connection_string)
            else:
                self.connection = create_connection()  # Use default from config
                
            if not self.connection or not self.connection.is_connected:
                print("❌ Failed to establish connection")
                return False
                
            self.controller = Controller(self.connection)
            self.vehicle = self.connection.vehicle
            
            print("✅ Connection established successfully")
            return True
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False

    async def pre_flight_safety_checks(self) -> bool:
        """Comprehensive pre-flight safety checks."""
        print("\n🔍 Performing pre-flight safety checks...")
        
        try:
            # Wait for vehicle to be armable
            print("⏳ Waiting for vehicle to be armable...")
            max_wait_time = 60  # seconds
            start_time = time.time()
            
            while not getattr(self.vehicle, "is_armable", False):
                if time.time() - start_time > max_wait_time:
                    print("❌ Timeout waiting for vehicle to be armable")
                    return False
                await asyncio.sleep(1)
                
            print("✅ Vehicle is armable")
            
            # Check GPS fix
            gps = getattr(self.vehicle, "gps_0", None)
            if not gps or getattr(gps, "fix_type", 0) < 3:
                print("❌ GPS fix insufficient (need 3D fix)")
                return False
            print(f"✅ GPS fix OK (fix_type: {gps.fix_type}, satellites: {gps.satellites_visible})")
            
            # Check battery level
            battery = getattr(self.vehicle, "battery", None)
            if battery:
                level = getattr(battery, "level", None)
                if level is not None and level < SafetyConfig.MIN_BATTERY_LEVEL:
                    print(f"❌ Battery too low: {level}% (need ≥{SafetyConfig.MIN_BATTERY_LEVEL}%)")
                    return False
                print(f"✅ Battery OK: {level}%")
            
            # Ensure GUIDED mode
            current_mode = getattr(self.vehicle.mode, "name", "UNKNOWN")
            if current_mode != "GUIDED":
                print(f"🔄 Switching from {current_mode} to GUIDED mode...")
                self.vehicle.mode = VehicleMode("GUIDED")
                
                # Wait for mode change
                mode_timeout = 10
                start_time = time.time()
                while getattr(self.vehicle.mode, "name", None) != "GUIDED":
                    if time.time() - start_time > mode_timeout:
                        print("❌ Failed to switch to GUIDED mode")
                        return False
                    await asyncio.sleep(0.5)
                    
                print("✅ Mode set to GUIDED")
            else:
                print("✅ Already in GUIDED mode")
            
            print("✅ All pre-flight checks passed!")
            return True
            
        except Exception as e:
            print(f"❌ Pre-flight check failed: {e}")
            return False

    def validate_and_process_waypoints(self, waypoints: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
        """Validate and process waypoint list with safety checks."""
        print(f"\n📍 Processing {len(waypoints)} waypoints...")
        
        processed_waypoints = []
        
        for i, waypoint in enumerate(waypoints):
            lat, lon, alt = waypoint
            
            # Assign default altitude if missing or invalid
            if alt is None or alt <= 0:
                alt = self.default_altitude
                print(f"📍 Waypoint {i+1}: Assigned default altitude {alt}m")
            
            # Validate altitude limits
            if alt < SafetyConfig.MIN_ALTITUDE:
                alt = SafetyConfig.MIN_ALTITUDE
                print(f"📍 Waypoint {i+1}: Altitude increased to minimum {alt}m")
            elif alt > SafetyConfig.MAX_ALTITUDE:
                alt = SafetyConfig.MAX_ALTITUDE
                print(f"📍 Waypoint {i+1}: Altitude reduced to maximum {alt}m")
            
            # Validate coordinates
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                print(f"❌ Invalid coordinates at waypoint {i+1}: ({lat}, {lon})")
                continue
                
            processed_waypoints.append((lat, lon, alt))
        
        # Merge waypoints that are too close together
        if len(processed_waypoints) > 1:
            merged_waypoints = [processed_waypoints[0]]
            
            for waypoint in processed_waypoints[1:]:
                last_waypoint = merged_waypoints[-1]
                distance = self.calculate_distance(last_waypoint, waypoint)
                
                if distance < self.min_waypoint_distance:
                    print(f"📍 Merging waypoints too close together ({distance:.1f}m < {self.min_waypoint_distance}m)")
                else:
                    merged_waypoints.append(waypoint)
            
            processed_waypoints = merged_waypoints
        
        print(f"✅ Processed {len(processed_waypoints)} valid waypoints")
        return processed_waypoints

    def calculate_distance(self, wp1: Tuple[float, float, float], wp2: Tuple[float, float, float]) -> float:
        """Calculate distance between two waypoints in meters."""
        lat1, lon1, _ = wp1
        lat2, lon2, _ = wp2
        
        # Haversine formula for distance calculation
        R = 6371000  # Earth radius in meters
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat/2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c

    async def arm_and_takeoff(self, target_altitude: float) -> bool:
        """Arm drone and takeoff to target altitude."""
        print(f"\n🚀 Starting takeoff sequence to {target_altitude}m...")
        
        try:
            # Use controller's arm_and_takeoff method
            success = await self.controller.arm_and_takeoff(
                altitude=target_altitude,
                wait_mode_timeout=15.0,
                wait_arm_timeout=30.0
            )
            
            if success:
                print(f"✅ Takeoff successful - now at {target_altitude}m")
                self.flight_logger.log_takeoff(target_altitude, {
                    "battery": getattr(self.vehicle.battery, "level", "unknown"),
                    "gps_sats": getattr(self.vehicle.gps_0, "satellites_visible", "unknown")
                })
                return True
            else:
                print("❌ Takeoff failed")
                return False
                
        except Exception as e:
            print(f"❌ Takeoff exception: {e}")
            return False

    async def fly_to_waypoint(self, waypoint: Tuple[float, float, float], waypoint_num: int, total_waypoints: int) -> bool:
        """Fly to a specific waypoint."""
        lat, lon, alt = waypoint
        
        print(f"\n📍 Flying to waypoint {waypoint_num}/{total_waypoints}")
        print(f"   Target: {lat:.6f}, {lon:.6f}, {alt}m")
        
        try:
            # Create LocationGlobalRelative object
            target_location = LocationGlobalRelative(lat, lon, alt)
            
            # Command drone to fly to waypoint
            self.vehicle.simple_goto(target_location)
            
            # Wait for arrival with timeout
            arrival_threshold = 2.0  # meters
            max_wait_time = 120  # seconds
            start_time = time.time()
            
            while True:
                # Check for manual override or mission stop
                if self.manual_override or not self.mission_active:
                    print("⚠️ Mission override detected")
                    return False
                
                # Check current position
                current_location = self.vehicle.location.global_relative_frame
                if current_location:
                    distance = self.calculate_distance(
                        (current_location.lat, current_location.lon, current_location.alt),
                        waypoint
                    )
                    
                    print(f"   Distance to target: {distance:.1f}m", end='\r')
                    
                    # Check if arrived
                    if distance <= arrival_threshold:
                        print(f"\n✅ Reached waypoint {waypoint_num}/{total_waypoints}")
                        self.waypoints_visited += 1
                        return True
                
                # Check timeout
                if time.time() - start_time > max_wait_time:
                    print(f"\n⏰ Timeout reaching waypoint {waypoint_num}")
                    return False
                
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"\n❌ Error flying to waypoint: {e}")
            return False

    async def fly_to_waypoints(self, waypoints: List[Tuple[float, float, float]]) -> bool:
        """Navigate through all waypoints sequentially."""
        print(f"\n🗺️ Starting waypoint navigation ({len(waypoints)} waypoints)")
        
        self.mission_active = True
        self.waypoints_visited = 0
        
        try:
            for i, waypoint in enumerate(waypoints, 1):
                if not self.mission_active or self.manual_override:
                    print("⚠️ Mission stopped or overridden")
                    return False
                
                success = await self.fly_to_waypoint(waypoint, i, len(waypoints))
                if not success:
                    print(f"❌ Failed to reach waypoint {i}")
                    return False
                
                # Brief pause between waypoints
                await asyncio.sleep(2)
            
            print("✅ All waypoints completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Waypoint navigation failed: {e}")
            return False
        finally:
            self.mission_active = False

    def start_telemetry_monitoring(self):
        """Start telemetry monitoring in a separate thread."""
        def telemetry_loop():
            print("📊 Starting telemetry monitoring...")
            
            while not self.stop_monitoring.is_set() and self.mission_active:
                try:
                    # Get current telemetry
                    current_time = datetime.now()
                    location = self.vehicle.location.global_relative_frame
                    battery = self.vehicle.battery
                    gps = self.vehicle.gps_0
                    
                    if location and battery:
                        battery_level = getattr(battery, "level", 0)
                        
                        # Update minimum battery
                        if battery_level < self.min_battery_recorded:
                            self.min_battery_recorded = battery_level
                        
                        # Create telemetry record
                        telemetry_record = {
                            "timestamp": current_time.isoformat(),
                            "lat": location.lat,
                            "lon": location.lon,
                            "alt": location.alt,
                            "battery_level": battery_level,
                            "battery_voltage": getattr(battery, "voltage", 0),
                            "gps_fix": getattr(gps, "fix_type", 0),
                            "satellites": getattr(gps, "satellites_visible", 0),
                            "groundspeed": getattr(self.vehicle, "groundspeed", 0),
                            "mode": getattr(self.vehicle.mode, "name", "UNKNOWN")
                        }
                        
                        self.telemetry_data.append(telemetry_record)
                        
                        # Print telemetry every 5 seconds
                        if len(self.telemetry_data) % 5 == 0:
                            print(f"\n📊 Telemetry - Lat: {location.lat:.6f}, Lon: {location.lon:.6f}, "
                                  f"Alt: {location.alt:.1f}m, Battery: {battery_level}%, "
                                  f"GPS: {getattr(gps, 'fix_type', 0)}, Mode: {getattr(self.vehicle.mode, 'name', 'UNKNOWN')}")
                    
                    time.sleep(1)  # Update every second
                    
                except Exception as e:
                    print(f"⚠️ Telemetry error: {e}")
                    time.sleep(1)
        
        self.telemetry_thread = threading.Thread(target=telemetry_loop, daemon=True)
        self.telemetry_thread.start()

    def start_failsafe_monitoring(self):
        """Start failsafe monitoring in a separate thread."""
        def failsafe_loop():
            print("🛡️ Starting failsafe monitoring...")
            
            while not self.stop_monitoring.is_set() and self.mission_active:
                try:
                    # Battery monitoring
                    battery = getattr(self.vehicle, "battery", None)
                    if battery:
                        level = getattr(battery, "level", None)
                        if level is not None and level < self.critical_battery_level:
                            print(f"🚨 CRITICAL BATTERY: {level}% - Triggering RTL!")
                            self.trigger_emergency_rtl("Critical battery level")
                            break
                    
                    # GPS monitoring
                    gps = getattr(self.vehicle, "gps_0", None)
                    if gps:
                        fix_type = getattr(gps, "fix_type", 0)
                        if fix_type < 3:
                            print(f"⚠️ GPS fix lost (fix_type: {fix_type}) - Switching to ALT_HOLD")
                            self.handle_gps_loss()
                    
                    # Mode safeguard
                    current_mode = getattr(self.vehicle.mode, "name", "UNKNOWN")
                    if current_mode != "GUIDED" and self.mission_active and not self.manual_override:
                        print(f"⚠️ Mode changed unexpectedly to {current_mode} - Forcing GUIDED")
                        self.vehicle.mode = VehicleMode("GUIDED")
                    
                    time.sleep(2)  # Check every 2 seconds
                    
                except Exception as e:
                    print(f"⚠️ Failsafe monitoring error: {e}")
                    print("🚨 Connection lost - Triggering emergency RTL!")
                    self.trigger_emergency_rtl("Connection lost")
                    break
        
        self.failsafe_thread = threading.Thread(target=failsafe_loop, daemon=True)
        self.failsafe_thread.start()

    def handle_gps_loss(self):
        """Handle GPS fix loss with recovery attempt."""
        try:
            # Switch to ALT_HOLD
            self.vehicle.mode = VehicleMode("ALT_HOLD")
            print("📍 Switched to ALT_HOLD - Waiting for GPS recovery...")
            
            # Wait for GPS recovery
            start_time = time.time()
            while time.time() - start_time < self.gps_recovery_timeout:
                gps = getattr(self.vehicle, "gps_0", None)
                if gps and getattr(gps, "fix_type", 0) >= 3:
                    print("✅ GPS recovered - Resuming mission")
                    self.vehicle.mode = VehicleMode("GUIDED")
                    return
                time.sleep(1)
            
            # GPS not recovered - emergency land
            print("❌ GPS not recovered - Initiating emergency landing")
            self.trigger_emergency_land("GPS fix not recovered")
            
        except Exception as e:
            print(f"❌ GPS loss handling failed: {e}")
            self.trigger_emergency_land("GPS handling error")

    def trigger_emergency_rtl(self, reason: str):
        """Trigger emergency return to launch."""
        print(f"🚨 EMERGENCY RTL: {reason}")
        self.mission_active = False
        self.flight_logger.log_emergency("emergency_rtl", reason)
        
        try:
            asyncio.create_task(self.controller.rtl(emergency_override=True))
        except Exception as e:
            print(f"❌ Emergency RTL failed: {e}")
            self.trigger_emergency_land("RTL failed")

    def trigger_emergency_land(self, reason: str):
        """Trigger emergency landing."""
        print(f"🚨 EMERGENCY LAND: {reason}")
        self.mission_active = False
        self.flight_logger.log_emergency("emergency_land", reason)
        
        try:
            asyncio.create_task(self.controller.emergency_land())
        except Exception as e:
            print(f"❌ Emergency land failed: {e}")

    def set_manual_override(self, override: bool = True):
        """Set manual override flag."""
        self.manual_override = override
        if override:
            print("⚠️ Manual override activated")
            try:
                self.vehicle.mode = VehicleMode("LOITER")
                print("📍 Switched to LOITER mode")
            except Exception as e:
                print(f"❌ Failed to switch to LOITER: {e}")

    async def complete_mission(self) -> bool:
        """Complete mission with RTL and landing."""
        print("\n🏁 Mission complete - Initiating return to launch...")
        
        try:
            # Trigger RTL
            success = await self.controller.rtl()
            
            if success:
                print("✅ Successfully returned to launch")
                
                # Wait for disarm (indicates landing complete)
                print("⏳ Waiting for automatic disarm after landing...")
                timeout = 120  # 2 minutes
                start_time = time.time()
                
                while getattr(self.vehicle, "armed", True):
                    if time.time() - start_time > timeout:
                        print("⏰ Disarm timeout - manually disarming...")
                        await self.controller.disarm()
                        break
                    await asyncio.sleep(1)
                
                print("✅ Landing and disarm complete")
                return True
            else:
                print("❌ RTL failed - attempting emergency landing")
                return await self.controller.emergency_land()
                
        except Exception as e:
            print(f"❌ Mission completion failed: {e}")
            return False

    def log_mission_summary(self):
        """Log mission summary to file."""
        try:
            mission_duration = (datetime.now() - self.mission_start_time).total_seconds() if self.mission_start_time else 0
            
            summary = {
                "mission_date": datetime.now().isoformat(),
                "mission_duration_seconds": mission_duration,
                "waypoints_visited": self.waypoints_visited,
                "min_battery_level": self.min_battery_recorded,
                "telemetry_points": len(self.telemetry_data)
            }
            
            # Log to JSON file
            summary_filename = f"mission_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(summary_filename, 'w') as f:
                json.dump(summary, f, indent=2)
            
            # Log telemetry to CSV
            if self.telemetry_data:
                csv_filename = f"mission_telemetry_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                with open(csv_filename, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=self.telemetry_data[0].keys())
                    writer.writeheader()
                    writer.writerows(self.telemetry_data)
                
                print(f"📊 Telemetry saved to {csv_filename}")
            
            print(f"📝 Mission summary saved to {summary_filename}")
            print(f"📈 Mission Stats:")
            print(f"   Duration: {mission_duration:.1f} seconds")
            print(f"   Waypoints visited: {self.waypoints_visited}")
            print(f"   Minimum battery: {self.min_battery_recorded:.1f}%")
            
        except Exception as e:
            print(f"⚠️ Failed to save mission log: {e}")

    def cleanup(self):
        """Clean up resources and stop monitoring threads."""
        print("\n🧹 Cleaning up...")
        
        self.mission_active = False
        self.stop_monitoring.set()
        
        # Wait for threads to finish
        if self.telemetry_thread and self.telemetry_thread.is_alive():
            self.telemetry_thread.join(timeout=5)
        
        if self.failsafe_thread and self.failsafe_thread.is_alive():
            self.failsafe_thread.join(timeout=5)
        
        # Close connection
        if self.connection:
            try:
                self.connection.close()
                print("✅ Connection closed")
            except Exception as e:
                print(f"⚠️ Error closing connection: {e}")

    async def execute_waypoint_mission(self, waypoints: List[Tuple[float, float, float]]) -> bool:
        """Execute complete autonomous waypoint mission."""
        print("🚁 Starting Autonomous Waypoint Mission")
        print("=" * 50)
        
        self.mission_start_time = datetime.now()
        
        try:
            # Step 1: Initialize connection
            if not await self.initialize_connection():
                return False
            
            # Step 2: Pre-flight safety checks
            if not await self.pre_flight_safety_checks():
                return False
            
            # Step 3: Process waypoints
            processed_waypoints = self.validate_and_process_waypoints(waypoints)
            if not processed_waypoints:
                print("❌ No valid waypoints to navigate")
                return False
            
            # Step 4: Start monitoring threads
            self.start_telemetry_monitoring()
            self.start_failsafe_monitoring()
            
            # Step 5: Arm and takeoff
            if not await self.arm_and_takeoff(self.takeoff_altitude):
                return False
            
            # Step 6: Navigate waypoints
            if not await self.fly_to_waypoints(processed_waypoints):
                print("❌ Waypoint navigation failed")
                return False
            
            # Step 7: Complete mission
            if not await self.complete_mission():
                print("❌ Mission completion failed")
                return False
            
            print("\n🎉 MISSION COMPLETED SUCCESSFULLY! 🎉")
            return True
            
        except KeyboardInterrupt:
            print("\n⚠️ Mission interrupted by user")
            self.set_manual_override(True)
            return False
        except Exception as e:
            print(f"\n❌ Mission failed with exception: {e}")
            return False
        finally:
            # Step 8: Log mission summary and cleanup
            self.log_mission_summary()
            self.cleanup()


# Example usage and test function
async def test_waypoint_mission():
    """Test the autonomous waypoint mission system."""
    
    # Example waypoints (replace with your actual coordinates)
    waypoints = [
        (28.459497, 77.026638, 20),  # Waypoint 1
        (28.459800, 77.027000, 20),  # Waypoint 2
        (28.460000, 77.026800, 20),  # Waypoint 3
    ]
    
    # Create mission instance
    mission = AutonomousWaypointMission()
    
    # Execute mission
    success = await mission.execute_waypoint_mission(waypoints)
    
    if success:
        print("✅ Test mission completed successfully!")
    else:
        print("❌ Test mission failed!")
    
    return success


# Command-line interface
async def main():
    """Main entry point for autonomous waypoint mission."""
    import sys
    
    print("🚁 Autonomous Waypoint Navigation System")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Run test mission
        await test_waypoint_mission()
    else:
        # Interactive mode
        print("📍 Enter waypoints (lat, lon, alt) - press Enter without input to finish:")
        waypoints = []
        
        while True:
            try:
                user_input = input(f"Waypoint {len(waypoints)+1} (lat,lon,alt): ").strip()
                if not user_input:
                    break
                
                parts = user_input.split(',')
                if len(parts) >= 2:
                    lat = float(parts[0].strip())
                    lon = float(parts[1].strip())
                    alt = float(parts[2].strip()) if len(parts) > 2 else 20.0
                    waypoints.append((lat, lon, alt))
                    print(f"✅ Added waypoint: {lat:.6f}, {lon:.6f}, {alt}m")
                else:
                    print("❌ Invalid format. Use: lat,lon,alt")
            
            except ValueError:
                print("❌ Invalid numbers. Use: lat,lon,alt")
            except KeyboardInterrupt:
                print("\n⚠️ Cancelled by user")
                return
        
        if waypoints:
            print(f"\n🗺️ Planning mission with {len(waypoints)} waypoints")
            mission = AutonomousWaypointMission()
            await mission.execute_waypoint_mission(waypoints)
        else:
            print("❌ No waypoints provided")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Fatal error: {e}")