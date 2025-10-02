import asyncio
import time
from datetime import datetime, timedelta
from dronekit import VehicleMode, LocationGlobalRelative
from safety_config import SafetyConfig, FlightLogger
from typing import Optional, Dict, Any, Tuple

class Controller:
    def __init__(self, connection):
        self.connection = connection
        self.flight_logger = FlightLogger()
        self.flight_start_time = None
        self.home_location = None
        self.current_mission = None

    def _vehicle_ready(self, require_armable=True):
        
        # check vehicle connectivity
        if not getattr(self.connection, "is_connected", False) or not getattr(self.connection, "vehicle", None):
            print("Vehicle not connected.")
            return False

        vehicle = self.connection.vehicle

        # Check heartbeat freshness with configurable timeout
        last_heartbeat = getattr(vehicle, "last_heartbeat", None)
        if last_heartbeat is not None and last_heartbeat > SafetyConfig.MAX_HEARTBEAT_AGE:
            print(f"Vehicle heartbeat too old: {last_heartbeat}s (need <{SafetyConfig.MAX_HEARTBEAT_AGE}s)")
            return False

        if require_armable and not getattr(vehicle, "is_armable", False):
            print("Vehicle is not armable.")
            return False

        # GPS check with enhanced validation
        gps = getattr(vehicle, "gps_0", None)
        if gps is not None:
            fix = getattr(gps, "fix_type", 0) or 0
            satellites = getattr(gps, "satellites_visible", 0) or 0
            
            if require_armable and fix < SafetyConfig.MIN_GPS_FIX:
                print(f"GPS fix not sufficient for arming (fix_type={fix}, need ≥{SafetyConfig.MIN_GPS_FIX}).")
                return False
            elif fix < 2:  # Basic connectivity check
                print(f"GPS fix too poor (fix_type={fix}).")
                return False
                
            if require_armable and satellites < SafetyConfig.MIN_GPS_SATELLITES:
                print(f"Not enough GPS satellites ({satellites}, need ≥{SafetyConfig.MIN_GPS_SATELLITES}).")
                return False

        # Battery check with configurable limits
        battery = getattr(vehicle, "battery", None)
        if battery is not None:
            batt_level = getattr(battery, "level", None)
            if batt_level is not None and batt_level < SafetyConfig.MIN_BATTERY_LEVEL:
                print(f"Battery level too low ({batt_level}%, need ≥{SafetyConfig.MIN_BATTERY_LEVEL}%).")
                return False
            
            # Check battery voltage with better detection
            voltage = getattr(battery, "voltage", None)
            if voltage is not None:
                min_voltage = self._get_min_battery_voltage(voltage)
                if voltage < min_voltage:
                    print(f"Battery voltage too low ({voltage}V, need ≥{min_voltage}V).")
                    return False

        # Check system status if available
        if hasattr(vehicle, 'system_status'):
            sys_status = getattr(vehicle.system_status, 'state', 'UNKNOWN')
            if require_armable and sys_status not in ['STANDBY', 'ACTIVE']:
                print(f"Vehicle not in safe state: {sys_status}")
                return False

        return True

    def _get_min_battery_voltage(self, current_voltage: float) -> float:
        """Determine minimum safe voltage based on current voltage (auto-detect battery type)."""
        if current_voltage > 20:  # 6S battery
            return SafetyConfig.MIN_BATTERY_VOLTAGE_6S
        elif current_voltage > 13:  # 4S battery  
            return SafetyConfig.MIN_BATTERY_VOLTAGE_4S
        else:  # 3S battery (default)
            return SafetyConfig.MIN_BATTERY_VOLTAGE_3S

    async def _wait_for_condition(self, check_fn, timeout, interval=0.5, desc="condition"):
        start = time.time()
        while not check_fn():
            if time.time() - start > timeout:
                print(f"Timed out waiting for {desc}.")
                return False
            await asyncio.sleep(interval)
        return True

    async def arm(self, *, wait_mode_timeout=10.0, wait_arm_timeout=20.0):
        if not self._vehicle_ready(require_armable=True):
            return False

        vehicle = self.connection.vehicle

        try:
            # Ensure vehicle is in GUIDED mode before arming
            current_mode = getattr(vehicle.mode, "name", "UNKNOWN")
            if current_mode != "GUIDED":
                print(f"Current mode: {current_mode}. Setting mode to GUIDED...")
                vehicle.mode = VehicleMode("GUIDED")
                if not await self._wait_for_condition(lambda: getattr(vehicle.mode, "name", None) == "GUIDED", wait_mode_timeout, desc="GUIDED mode"):
                    print("Failed to set GUIDED mode.")
                    return False
                print("Vehicle is now in GUIDED mode.")
            else:
                print("Vehicle already in GUIDED mode.")

            # Check if already armed
            if getattr(vehicle, "armed", False):
                print("Vehicle is already armed.")
                return True

            # Perform pre-arm throttle safety check
            if not await self.pre_arm_throttle_check():
                print("❌ Pre-arm throttle check failed - ensure throttle is at minimum")
                return False

            print("Arming vehicle...")
            vehicle.armed = True
            
            # Wait until the vehicle confirms it is armed
            if not await self._wait_for_condition(lambda: getattr(vehicle, "armed", False),
                                                  wait_arm_timeout, desc="arming confirmation"):
                print("Arming failed - vehicle did not confirm armed state.")
                return False

            print("✅ Vehicle is armed and ready.")
            return True
        except Exception as e:
            print(f"Arming failed: {e}")
            return False

    async def disarm(self, *, wait_disarm_timeout=15.0):
        if not self._vehicle_ready(require_armable=False):
            return False

        vehicle = self.connection.vehicle

        if not getattr(vehicle, "armed", False):
            print("Vehicle already disarmed.")
            return True

        try:
            print("Disarming vehicle...")
            vehicle.armed = False
            if not await self._wait_for_condition(lambda: not getattr(vehicle, "armed", True),wait_disarm_timeout, desc="disarming"):
                return False
            print("Vehicle is disarmed.")
            return True
        except Exception as e:
            print(f"Disarming failed: {e}")
            return False

    async def emergency_disarm(self):
        """Emergency disarm - SMART emergency that considers altitude to prevent crashes."""
        if not getattr(self.connection, "is_connected", False) or not getattr(self.connection, "vehicle", None):
            print("Vehicle not connected - cannot emergency disarm.")
            return False
            
        vehicle = self.connection.vehicle
        
        if not getattr(vehicle, "armed", False):
            print("Vehicle already disarmed.")
            return True

        try:
            # CHECK ALTITUDE FIRST - Don't kill drone in mid-air!
            current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
            
            if current_alt > 2.0:  # If above 2m, emergency land instead!
                print(f"🚨 HIGH ALTITUDE EMERGENCY ({current_alt:.1f}m) - EMERGENCY LANDING INSTEAD OF DISARM")
                self.flight_logger.log_emergency("emergency_land_high_altitude", f"altitude_{current_alt:.1f}m")
                return await self.emergency_land()
            else:
                print("🚨 LOW ALTITUDE EMERGENCY - Safe to disarm")
                # Cut throttle first for safety
                await self.set_throttle(0)
                vehicle.armed = False
                # Shorter timeout for emergency
                if not await self._wait_for_condition(lambda: not getattr(vehicle, "armed", True), 5.0, desc="emergency disarming"):
                    print("Emergency disarm timeout - vehicle may still be armed!")
                    return False
                print("Emergency disarm successful.")
                return True
        except Exception as e:
            print(f"Emergency disarm failed: {e}")
            return False

    async def set_throttle(self, throttle_percent: float):
        """
        Set throttle percentage for manual control during arming/flight.
        Args:
            throttle_percent: Throttle percentage (0-100)
        """
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            # Clamp throttle to safe range
            throttle_percent = max(0, min(100, throttle_percent))
            
            # Convert percentage to PWM value (1000-2000 range)
            throttle_pwm = int(1000 + (throttle_percent / 100.0) * 1000)
            
            print(f"Setting throttle to {throttle_percent}% (PWM: {throttle_pwm})")
            
            # Override throttle channel (channel 3 is typically throttle)
            vehicle.channels.overrides = {'3': throttle_pwm}
            
            # Small delay to let the command take effect
            await asyncio.sleep(0.1)
            
            # CRITICAL: Verify the override was actually set
            current_overrides = getattr(vehicle.channels, 'overrides', {})
            if '3' not in current_overrides or current_overrides['3'] != throttle_pwm:
                print(f"⚠️ WARNING: Throttle override verification failed! Expected: {throttle_pwm}, Got: {current_overrides}")
                return False
            
            print(f"✅ Throttle override confirmed: {throttle_percent}% (PWM: {throttle_pwm})")
            return True
        except Exception as e:
            print(f"Failed to set throttle: {e}")
            return False

    async def release_throttle_control(self):
        """Release manual throttle control back to autopilot."""
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            print("Releasing throttle control to autopilot...")
            # Clear channel overrides
            vehicle.channels.overrides = {}
            await asyncio.sleep(0.1)
            
            # CRITICAL: Verify overrides were actually cleared
            current_overrides = getattr(vehicle.channels, 'overrides', {})
            if '3' in current_overrides:
                print(f"⚠️ WARNING: Throttle override NOT cleared! Still shows: {current_overrides}")
                # Try again more aggressively
                vehicle.channels.overrides = {'3': None}
                await asyncio.sleep(0.1)
                vehicle.channels.overrides = {}
                await asyncio.sleep(0.1)
                
                # Final check
                current_overrides = getattr(vehicle.channels, 'overrides', {})
                if '3' in current_overrides:
                    print(f"❌ CRITICAL: Could not clear throttle override! Manual control stuck!")
                    return False
            
            print("✅ Throttle control released to autopilot")
            return True
        except Exception as e:
            print(f"Failed to release throttle control: {e}")
            return False

    async def pre_arm_throttle_check(self):
        """Perform throttle safety check before arming."""
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            # Check if throttle is at safe level (should be low)
            rc_channels = getattr(vehicle, "rc_channels", None)
            if rc_channels:
                throttle_channel = getattr(rc_channels, "throttle", None)
                if throttle_channel is not None:
                    # Throttle should be below 1100 PWM for safe arming
                    if throttle_channel > 1100:
                        print(f"⚠️ Throttle too high for arming: {throttle_channel} PWM (should be < 1100)")
                        return False
                    else:
                        print(f"✅ Throttle at safe level: {throttle_channel} PWM")
            
            return True
        except Exception as e:
            print(f"Throttle check failed: {e}")
            return False

    async def takeoff(self, altitude, *, wait_timeout=30.0):
        """Safely take off to specified altitude.
        
        Args:
            altitude: Target altitude in meters (relative to home)
            wait_timeout: Maximum time to wait for takeoff completion
            
        Returns:
            bool: True if takeoff successful, False otherwise
        """
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        # Check if vehicle is armed
        if not getattr(vehicle, "armed", False):
            print("Vehicle must be armed before takeoff. Call arm() first.")
            return False
            
        # Check if vehicle is in GUIDED mode
        if getattr(vehicle.mode, "name", None) != "GUIDED":
            print("Vehicle must be in GUIDED mode for takeoff.")
            return False
        
        # CRITICAL: Enhanced pre-flight safety checks
        try:
            # Check GPS integrity
            gps = getattr(vehicle, "gps_0", None)
            if gps:
                gps_data = {
                    'eph': getattr(gps, 'eph', 999),
                    'groundspeed': getattr(vehicle, 'groundspeed', 0)
                }
                gps_ok, gps_msg = SafetyConfig.validate_gps_integrity(gps_data)
                if not gps_ok:
                    print(f"❌ GPS integrity check failed: {gps_msg}")
                    return False
            
            # Check battery under load (if possible)
            battery = getattr(vehicle, "battery", None)
            if battery and hasattr(battery, 'voltage'):
                voltage = battery.voltage
                # Simple under-load test - check voltage doesn't drop too much during arming
                if voltage < self._get_min_battery_voltage(voltage) + 0.3:  # Extra 0.3V margin
                    print(f"❌ Battery voltage too close to minimum for safe takeoff: {voltage}V")
                    return False
            
            # Verify home position is set
            home = getattr(vehicle, "home_location", None)
            if not home or (home.lat == 0.0 and home.lon == 0.0):
                print("⚠️ Warning: Home position not set - RTL may not work properly")
            
            print("✅ Pre-flight safety checks passed")
            
        except Exception as e:
            print(f"⚠️ Pre-flight safety check error: {e}")
            # Continue with takeoff but log the issue
            
        try:
            print(f"Taking off to {altitude}m altitude...")
            
            # Command takeoff
            vehicle.simple_takeoff(altitude)
            
            # Wait until vehicle reaches target altitude (within 95% of target)
            target_reached = lambda: (
                getattr(vehicle.location, "global_relative_frame", None) and
                getattr(vehicle.location.global_relative_frame, "alt", 0) >= altitude * 0.95
            )
            
            if not await self._wait_for_condition(target_reached, wait_timeout, 
                                                desc=f"reaching {altitude}m altitude"):
                current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
                print(f"Takeoff timeout. Current altitude: {current_alt:.1f}m, Target: {altitude}m")
                return False
                
            current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
            print(f"✅ Takeoff complete! Current altitude: {current_alt:.1f}m")
            return True
            
        except Exception as e:
            print(f"Takeoff failed: {e}")
            return False

    async def land(self, *, wait_timeout=60.0, force_land_here=False):
        """Safely land the vehicle - defaults to RTL for safety unless forced.
        
        Args:
            wait_timeout: Maximum time to wait for landing completion
            force_land_here: If True, land at current location instead of RTL (DANGEROUS!)
        """
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        # Check if vehicle is already on ground
        current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
        if current_alt < 1.0:  # Already on ground
            print("Vehicle already on ground.")
            return True
        
        # SAFETY DECISION: RTL is safer than landing at unknown location
        if not force_land_here:
            print("🏠 SAFETY MODE: Using RTL instead of landing here (safer return to launch)")
            return await self.rtl(wait_timeout=wait_timeout)
        else:
            print("⚠️ FORCED LAND HERE - Landing at current location (potentially dangerous!)")
            self.flight_logger.log_emergency("forced_land_here", f"altitude_{current_alt:.1f}m")
            
        try:
            print("Landing vehicle at current location...")
            self.flight_logger.log_landing({"altitude": current_alt, "forced": force_land_here})
            
            # Set mode to LAND
            vehicle.mode = VehicleMode("LAND")
            
            # Wait for LAND mode confirmation
            if not await self._wait_for_condition(
                lambda: getattr(vehicle.mode, "name", None) == "LAND", 
                10.0, desc="LAND mode"
            ):
                print("Failed to set LAND mode.")
                return False
                
            print("Landing mode engaged.")
            
            # Wait until vehicle lands (altitude < 0.5m and disarmed)
            landed_condition = lambda: (
                getattr(vehicle.location.global_relative_frame, "alt", 999) < 0.5 and
                not getattr(vehicle, "armed", True)
            )
            
            if not await self._wait_for_condition(landed_condition, wait_timeout, desc="landing completion"):
                current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
                print(f"Landing timeout. Current altitude: {current_alt:.1f}m")
                return False
                
            print("✅ Landing complete!")
            return True
            
        except Exception as e:
            print(f"Landing failed: {e}")
            return False

    async def rtl(self, *, wait_timeout=120.0):
        """Return to Launch (RTL) - return to home position and land."""
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            # CRITICAL: Validate home position is set before RTL
            home = getattr(vehicle, "home_location", None)
            if not home or (home.lat == 0.0 and home.lon == 0.0):
                print("❌ HOME POSITION NOT SET! RTL would fail - using emergency land instead")
                self.flight_logger.log_emergency("rtl_no_home", "home_position_invalid")
                return await self.emergency_land()
            
            print(f"Returning to launch (RTL) - Home: {home.lat:.6f}, {home.lon:.6f}")
            self.flight_logger.log_rtl("manual_command")
            
            # Set mode to RTL
            vehicle.mode = VehicleMode("RTL")
            
            # Wait for RTL mode confirmation
            if not await self._wait_for_condition(
                lambda: getattr(vehicle.mode, "name", None) == "RTL", 
                10.0, desc="RTL mode"
            ):
                print("Failed to set RTL mode - trying emergency land")
                return await self.emergency_land()
                
            print("RTL mode engaged - returning to launch point...")
                
            # Wait until RTL completes (vehicle disarmed and near home)
            rtl_complete = lambda: not getattr(vehicle, "armed", True)
            
            if not await self._wait_for_condition(rtl_complete, wait_timeout, desc="RTL completion"):
                print("RTL timeout - vehicle may still be returning")
                return False
                
            print("✅ Return to Launch complete!")
            return True
            
        except Exception as e:
            print(f"RTL failed: {e}")
            return False

    async def fly_timed_mission(self, altitude: float, duration: float) -> bool:
        """
        Fly at specified altitude for specified duration then RTL.
        
        Args:
            altitude: Target altitude in meters
            duration: Flight duration in seconds
            
        Returns:
            bool: True if mission completed successfully
        """
        # Validate inputs
        alt_valid, alt_msg = SafetyConfig.validate_altitude(altitude)
        if not alt_valid:
            print(f"❌ Invalid altitude: {alt_msg}")
            return False
            
        time_valid, time_msg = SafetyConfig.validate_flight_time(duration)
        if not time_valid:
            print(f"❌ Invalid flight time: {time_msg}")
            return False
        
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        # Check if armed
        if not getattr(vehicle, "armed", False):
            print("❌ Vehicle must be armed for timed mission")
            return False
            
        try:
            print(f"🚁 Starting timed mission: {altitude}m altitude for {duration}s")
            self.current_mission = {
                "type": "timed_flight",
                "altitude": altitude,
                "duration": duration,
                "start_time": datetime.now(),
                "end_time": datetime.now() + timedelta(seconds=duration)
            }
            
            # Step 1: Takeoff to target altitude
            print(f"📈 Taking off to {altitude}m...")
            if not await self.takeoff(altitude):
                print("❌ Takeoff failed - aborting mission")
                return False
                
            # Step 2: Hold position for specified duration
            print(f"⏱️  Holding altitude {altitude}m for {duration} seconds...")
            mission_start = datetime.now()
            
            while (datetime.now() - mission_start).total_seconds() < duration:
                # Monitor vehicle status during mission
                if not getattr(vehicle, "armed", False):
                    print("⚠️  Vehicle disarmed during mission - mission interrupted")
                    break
                    
                current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
                remaining_time = duration - (datetime.now() - mission_start).total_seconds()
                
                if remaining_time % 10 < 1:  # Log every ~10 seconds
                    print(f"   Mission status: altitude={current_alt:.1f}m, remaining={remaining_time:.0f}s")
                
                await asyncio.sleep(1)
            
            print(f"✅ Timed flight completed - returning to launch")
            
            # Step 3: Return to Launch
            if not await self.rtl():
                print("⚠️  RTL failed - attempting emergency land")
                await self.land()
                return False
                
            print("🎯 Timed mission completed successfully!")
            self.current_mission = None
            return True
            
        except Exception as e:
            print(f"❌ Timed mission failed: {e}")
            self.current_mission = None
            return False

    async def emergency_disarm(self, *, confirm_emergency=False):
        """Emergency disarm with mandatory confirmation and logging."""
        if not confirm_emergency:
            raise Exception("❌ Emergency disarm requires explicit confirmation (confirm_emergency=True)")
            
        if not getattr(self.connection, "is_connected", False) or not getattr(self.connection, "vehicle", None):
            print("❌ Vehicle not connected - cannot emergency disarm.")
            return False
            
        vehicle = self.connection.vehicle
        
        if not getattr(vehicle, "armed", False):
            print("✅ Vehicle already disarmed.")
            return True

        try:
            print("🚨 EMERGENCY DISARM INITIATED 🚨")
            self.flight_logger.log_emergency("emergency_disarm", "manual_command")
            
            vehicle.armed = False
            # Shorter timeout for emergency
            if not await self._wait_for_condition(lambda: not getattr(vehicle, "armed", True), 8.0, desc="emergency disarming"):
                print("❌ Emergency disarm timeout - vehicle may still be armed!")
                return False
                
            print("✅ Emergency disarm successful.")
            return True
        except Exception as e:
            print(f"❌ Emergency disarm failed: {e}")
            self.flight_logger.log_emergency("emergency_disarm_failed", str(e))
            return False

    async def emergency_land(self):
        """Emergency land - SMART emergency that tries RTL first if possible."""
        if not getattr(self.connection, "is_connected", False) or not getattr(self.connection, "vehicle", None):
            print("❌ Vehicle not connected - cannot emergency land.")
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            print("🚨 EMERGENCY LAND INITIATED 🚨")
            self.flight_logger.log_emergency("emergency_land", "critical_situation")
            
            # SMART EMERGENCY: Try RTL first if home is valid (safer)
            home = getattr(vehicle, "home_location", None)
            if home and not (home.lat == 0.0 and home.lon == 0.0):
                print("🏠 Emergency RTL - returning to safe launch location")
                return await self.rtl(wait_timeout=60.0)
            else:
                print("⚠️ No valid home - forced to land at current location")
                return await self.land(force_land_here=True, wait_timeout=30.0)
            
        except Exception as e:
            print(f"❌ Emergency land failed: {e}")
            self.flight_logger.log_emergency("emergency_land_failed", str(e))
            return False

    async def force_land_here(self, *, wait_timeout=30.0):
        """Force immediate landing at current location - USE ONLY IN EMERGENCIES!"""
        if not getattr(self.connection, "is_connected", False) or not getattr(self.connection, "vehicle", None):
            print("❌ Vehicle not connected - cannot force land.")
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
            print(f"🚨 FORCE LAND HERE - EMERGENCY LANDING AT CURRENT LOCATION ({current_alt:.1f}m)")
            self.flight_logger.log_emergency("force_land_here", f"altitude_{current_alt:.1f}m")
            
            # Force LAND mode immediately
            vehicle.mode = VehicleMode("LAND")
            
            # Don't wait long for mode change in emergency
            if not await self._wait_for_condition(
                lambda: getattr(vehicle.mode, "name", None) == "LAND", 
                5.0, desc="emergency LAND mode"
            ):
                print("⚠️ Failed to set LAND mode - trying throttle cut")
                await self.set_throttle(0)  # Cut throttle as backup
                return False
                
            print("🚨 Emergency landing in progress...")
            return True
            
        except Exception as e:
            print(f"❌ Force land failed: {e}")
            self.flight_logger.log_emergency("force_land_failed", str(e))
            return False

    def verify_home_location(self) -> tuple[bool, str]:
        """Verify home location is valid and accurately set."""
        if not self._vehicle_ready(require_armable=False):
            return False, "Vehicle not ready"
            
        vehicle = self.connection.vehicle
        home = getattr(vehicle, "home_location", None)
        
        if not home:
            return False, "Home location not set - arm drone first to set home"
        
        if home.lat == 0.0 and home.lon == 0.0:
            return False, "Home location invalid (0,0) - ensure GPS lock before arming"
        
        # Check if home is within reasonable bounds
        if abs(home.lat) > 90 or abs(home.lon) > 180:
            return False, f"Home location out of bounds: {home.lat:.6f}, {home.lon:.6f}"
        
        # Check GPS accuracy when home was set
        gps = getattr(vehicle, "gps_0", None)
        if gps:
            eph = getattr(gps, 'eph', 999)
            if eph > 5.0:  # More than 5m accuracy error
                return False, f"Home location may be inaccurate - GPS accuracy: {eph}m"
        
        return True, f"Home location valid: {home.lat:.6f}, {home.lon:.6f}"

    def get_home_distance(self) -> Optional[float]:
        """Calculate distance from current position to home (in meters)."""
        if not self._vehicle_ready(require_armable=False):
            return None
            
        vehicle = self.connection.vehicle
        home = getattr(vehicle, "home_location", None)
        current_loc = getattr(vehicle.location, "global_frame", None)
        
        if not home or not current_loc:
            return None
            
        # Simple distance calculation (approximate for small distances)
        import math
        lat_diff = math.radians(current_loc.lat - home.lat)
        lon_diff = math.radians(current_loc.lon - home.lon)
        
        a = (math.sin(lat_diff/2)**2 + 
             math.cos(math.radians(home.lat)) * math.cos(math.radians(current_loc.lat)) * 
             math.sin(lon_diff/2)**2)
        
        distance = 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))  # Earth radius in meters
        return distance

    def get_mission_status(self) -> Optional[Dict[str, Any]]:
        """Get current mission status if any mission is active."""
        if not self.current_mission:
            return None
            
        now = datetime.now()
        elapsed = (now - self.current_mission["start_time"]).total_seconds()
        remaining = max(0, (self.current_mission["end_time"] - now).total_seconds())
        
        return {
            **self.current_mission,
            "elapsed_time": elapsed,
            "remaining_time": remaining,
            "progress": min(1.0, elapsed / self.current_mission["duration"])
        }
