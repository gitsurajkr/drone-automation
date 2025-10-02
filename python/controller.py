import asyncio
import time
from datetime import datetime, timedelta
from dronekit import VehicleMode, LocationGlobalRelative
from sitl_config import SITLConfig
from safety_config import SafetyConfig, FlightLogger
from typing import Optional, Dict, Any, Tuple

class Controller:
    def __init__(self, connection):
        self.connection = connection
        self.is_sitl = False  # Track if this is a SITL connection
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

    async def setup_sitl_connection(self, connection_string: str):
        """Setup SITL-specific configuration after connection with enhanced safety."""
        # CRITICAL SAFETY CHECK - verify this is actually SITL
        is_safe, reason = SITLConfig.validate_sitl_safety(connection_string)
        if not is_safe:
            print(f"❌ SITL setup rejected: {reason}")
            self.flight_logger.log_safety_violation("SITL_SETUP_REJECTED", {"connection": connection_string, "reason": reason})
            return False
        
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            print(f"✅ SITL connection validated: {connection_string}")
            print("Configuring SITL vehicle with safety parameters...")
            
            # Apply SITL-specific parameters safely
            sitl_params = SITLConfig.get_sitl_parameters()
            for param_name, param_value in sitl_params.items():
                original_value = vehicle.parameters.get(param_name, "unknown")
                print(f"Setting {param_name}: {original_value} → {param_value}")
                vehicle.parameters[param_name] = param_value
            
            # Wait for parameters to be set
            await asyncio.sleep(3)
            
            # Verify critical parameters were set
            arming_check = vehicle.parameters.get('ARMING_CHECK', -1)
            if arming_check != 0:
                raise Exception(f"Failed to set ARMING_CHECK (got {arming_check}, expected 0)")
                
            print(f"✅ SITL parameters applied successfully")
            self.is_sitl = True
            self.flight_logger.log_safety_violation("SITL_CONFIGURED", {"connection": connection_string, "parameters": sitl_params})
            return True
            
        except Exception as e:
            print(f"❌ SITL setup failed: {e}")
            self.flight_logger.log_safety_violation("SITL_SETUP_FAILED", {"connection": connection_string, "error": str(e)})
            return False

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
        """Emergency disarm - bypasses most safety checks for critical situations."""
        if not getattr(self.connection, "is_connected", False) or not getattr(self.connection, "vehicle", None):
            print("Vehicle not connected - cannot emergency disarm.")
            return False
            
        vehicle = self.connection.vehicle
        
        if not getattr(vehicle, "armed", False):
            print("Vehicle already disarmed.")
            return True

        try:
            print("EMERGENCY DISARM - Forcing disarm...")
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

    async def land(self, *, wait_timeout=60.0):
        """Safely land the vehicle at current location."""
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        # Check if vehicle is already on ground
        current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
        if current_alt < 1.0:  # Already on ground
            print("Vehicle already on ground.")
            return True
            
        try:
            print("Landing vehicle...")
            self.flight_logger.log_landing({"altitude": current_alt})
            
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
            print("Returning to launch (RTL)...")
            self.flight_logger.log_rtl("manual_command")
            
            # Set mode to RTL
            vehicle.mode = VehicleMode("RTL")
            
            # Wait for RTL mode confirmation
            if not await self._wait_for_condition(
                lambda: getattr(vehicle.mode, "name", None) == "RTL", 
                10.0, desc="RTL mode"
            ):
                print("Failed to set RTL mode.")
                return False
                
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
