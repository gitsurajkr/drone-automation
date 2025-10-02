import asyncio
import json
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

    def _vehicle_ready(self, require_armable=True, emergency_override=False):
        
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

        # Battery check with configurable limits (skip during emergency override)
        if not emergency_override:
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
        else:
            # Log emergency override usage
            battery = getattr(vehicle, "battery", None)
            if battery is not None:
                batt_level = getattr(battery, "level", None)
                if batt_level is not None:
                    print(f"⚠️ EMERGENCY OVERRIDE: Bypassing battery safety check ({batt_level}%)")

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

    def _detect_sitl_connection(self) -> bool:
        """Auto-detect if this is a SITL connection based on various indicators."""
        # First check if explicitly set
        if self.is_sitl:
            return True
            
        # Check vehicle parameters that indicate SITL
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            # SITL typically has ARMING_CHECK disabled (set to 0)
            arming_check = vehicle.parameters.get('ARMING_CHECK', None)
            if arming_check == 0:
                print("🔍 SITL detected: ARMING_CHECK=0")
                return True
                
            # SITL often has very poor GPS accuracy but still works
            gps = getattr(vehicle, "gps_0", None)
            if gps:
                eph = getattr(gps, 'eph', 999)
                if eph > 50:  # Very poor GPS accuracy typical of SITL
                    print(f"🔍 SITL suspected: Poor GPS accuracy (HDOP {eph})")
                    return True
                    
        except Exception as e:
            print(f"SITL detection error: {e}")
            
        return False

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
            print("[ARM] Starting arm sequence")
            
            # Ensure vehicle is in GUIDED mode before arming
            current_mode = getattr(vehicle.mode, "name", "UNKNOWN")
            if current_mode != "GUIDED":
                print(f"[ARM] Mode: {current_mode} -> GUIDED")
                vehicle.mode = VehicleMode("GUIDED")
                if not await self._wait_for_condition(lambda: getattr(vehicle.mode, "name", None) == "GUIDED", wait_mode_timeout, desc="GUIDED mode"):
                    print("[ARM] FAILED - Could not set GUIDED mode")
                    return False
                print("[ARM] Mode set to GUIDED")
            else:
                print("[ARM] Mode: Already in GUIDED")

            # Check if already armed
            if getattr(vehicle, "armed", False):
                print("[ARM] Already armed")
                return True

            # Perform pre-arm throttle safety check
            if not await self.pre_arm_throttle_check():
                print("[ARM] FAILED - Throttle safety check failed")
                return False

            print("[ARM] Sending arm command")
            vehicle.armed = True
            
            # Wait until the vehicle confirms it is armed
            if not await self._wait_for_condition(lambda: getattr(vehicle, "armed", False),
                                                  wait_arm_timeout, desc="arming confirmation"):
                print("[ARM] FAILED - No arm confirmation from vehicle")
                return False

            print("[ARM] SUCCESS - Vehicle armed and ready")
            print("[ARM] WARNING - Auto-disarm in 10 seconds without flight command")
            return True
        except Exception as e:
            print(f"[ARM] FAILED - Exception: {e}")
            return False

    async def arm_and_takeoff(self, altitude: float = 5.0, *, wait_mode_timeout=10.0, wait_arm_timeout=20.0) -> bool:
        """Arm vehicle and immediately takeoff - prevents auto-disarm timeout."""
        print(f"[ARM+TAKEOFF] Starting sequence to {altitude}m")
        
        # Step 1: Arm the vehicle
        if not await self.arm(wait_mode_timeout=wait_mode_timeout, wait_arm_timeout=wait_arm_timeout):
            print("[ARM+TAKEOFF] FAILED - Arming unsuccessful")
            return False
        
        # Step 2: Immediate takeoff to prevent auto-disarm
        print("[ARM+TAKEOFF] Proceeding to takeoff (preventing auto-disarm)")
        await asyncio.sleep(0.5)  # Brief pause to ensure arming is stable
        
        if not await self.takeoff(altitude):
            print("[ARM+TAKEOFF] FAILED - Takeoff unsuccessful")
            # Try to disarm safely
            await self.disarm()
            return False
        
        print(f"[ARM+TAKEOFF] SUCCESS - Now at {altitude}m altitude")
        return True

    async def disarm(self, *, wait_disarm_timeout=15.0):
        if not self._vehicle_ready(require_armable=False):
            return False

        vehicle = self.connection.vehicle

        if not getattr(vehicle, "armed", False):
            print("[DISARM] Already disarmed")
            return True

        try:
            # Check altitude before disarming for safety
            current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
            print(f"[DISARM] Current altitude: {current_alt:.1f}m")
            
            if current_alt > 2.0:
                print(f"[DISARM] WARNING - Disarming at {current_alt:.1f}m altitude")
            
            print("[DISARM] Sending disarm command")
            vehicle.armed = False
            if not await self._wait_for_condition(lambda: not getattr(vehicle, "armed", True),wait_disarm_timeout, desc="disarming"):
                print("[DISARM] FAILED - No disarm confirmation")
                return False
            print("[DISARM] SUCCESS - Vehicle disarmed safely")
            return True
        except Exception as e:
            print(f"[DISARM] FAILED - Exception: {e}")
            return False

    async def emergency_disarm(self, *, confirm_emergency=False):
        """Emergency disarm - SMART emergency that considers altitude to prevent crashes with mandatory confirmation."""
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
            
            # CHECK ALTITUDE FIRST - Don't kill drone in mid-air!
            current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
            print(f"[EMERGENCY] Current altitude: {current_alt:.1f}m")
            
            if current_alt > 2.0:  # If above 2m, emergency land instead!
                print(f"[EMERGENCY] HIGH ALTITUDE - Emergency landing instead of disarm")
                self.flight_logger.log_emergency("emergency_land_high_altitude", f"altitude_{current_alt:.1f}m")
                return await self.emergency_land()
            else:
                print("[EMERGENCY] LOW ALTITUDE - Safe to disarm")
                # Cut throttle first for safety
                await self.set_throttle(0)
                print("[EMERGENCY] Cutting power")
                vehicle.armed = False
                # Shorter timeout for emergency (increased from 5s to 8s for better reliability)
                if not await self._wait_for_condition(lambda: not getattr(vehicle, "armed", True), 8.0, desc="emergency disarming"):
                    print("❌ Emergency disarm timeout - vehicle may still be armed!")
                    return False
                print("✅ Emergency disarm successful.")
                return True
        except Exception as e:
            print(f"❌ Emergency disarm failed: {e}")
            self.flight_logger.log_emergency("emergency_disarm_failed", str(e))
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
                # Auto-detect SITL for GPS validation
                is_sitl_connection = self._detect_sitl_connection()
                gps_ok, gps_msg = SafetyConfig.validate_gps_integrity(gps_data, is_sitl_connection)
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
            print(f"[TAKEOFF] Target altitude: {altitude}m")
            print("[TAKEOFF] Sending takeoff command")
            
            # Command takeoff
            vehicle.simple_takeoff(altitude)
            
            # Real-time altitude tracking with progress updates
            print(f"[TAKEOFF] Climbing to {altitude}m...")
            start_time = time.time()
            last_logged_meter = -1
            
            while True:
                current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
                
                # Log each meter milestone
                current_meter = int(current_alt)
                if current_meter > last_logged_meter and current_meter > 0:
                    progress_percent = min(100, int((current_alt / altitude) * 100))
                    print(f"[TAKEOFF] Altitude: {current_alt:.1f}m ({progress_percent}%)")
                    last_logged_meter = current_meter
                
                # Check if target reached (within 95% of target)
                if current_alt >= altitude * 0.95:
                    print(f"[TAKEOFF] SUCCESS - Reached {current_alt:.1f}m (target: {altitude}m)")
                    return True
                
                # Check timeout
                if time.time() - start_time > wait_timeout:
                    print(f"[TAKEOFF] TIMEOUT - Current: {current_alt:.1f}m, Target: {altitude}m")
                    return False
                
                await asyncio.sleep(0.5)  # Update every 500ms
            
        except Exception as e:
            print(f"Takeoff failed: {e}")
            return False

    async def land(self, *, wait_timeout=60.0, force_land_here=False, emergency_override=False):
        """Safely land the vehicle - defaults to RTL for safety unless forced.
        
        Args:
            wait_timeout: Maximum time to wait for landing completion
            force_land_here: If True, land at current location instead of RTL (DANGEROUS!)
            emergency_override: If True, bypass battery safety checks for emergency landing
        """
        if not self._vehicle_ready(require_armable=False, emergency_override=emergency_override):
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
            return await self.rtl(wait_timeout=wait_timeout, emergency_override=emergency_override)
        else:
            print("⚠️ FORCED LAND HERE - Landing at current location (potentially dangerous!)")
            self.flight_logger.log_emergency("forced_land_here", f"altitude_{current_alt:.1f}m")
            
        try:
            print(f"[LAND] Starting descent from {current_alt:.1f}m")
            self.flight_logger.log_landing({"altitude": current_alt, "forced": force_land_here})
            
            # Set mode to LAND
            print("[LAND] Setting LAND mode")
            vehicle.mode = VehicleMode("LAND")
            
            # Wait for LAND mode confirmation
            if not await self._wait_for_condition(
                lambda: getattr(vehicle.mode, "name", None) == "LAND", 
                10.0, desc="LAND mode"
            ):
                print("[LAND] FAILED - Could not set LAND mode")
                return False
                
            print("[LAND] Descending...")
            
            # Real-time descent tracking
            start_time = time.time()
            last_logged_alt = current_alt
            
            while True:
                current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
                armed = getattr(vehicle, "armed", False)
                
                # Log significant altitude changes (every 2m or so)
                if abs(current_alt - last_logged_alt) >= 2.0 or current_alt < 5.0:
                    print(f"[LAND] Altitude: {current_alt:.1f}m")
                    last_logged_alt = current_alt
                
                # Check if landed (altitude < 0.5m and disarmed)
                if current_alt < 0.5 and not armed:
                    print("[LAND] SUCCESS - Touchdown complete")
                    return True
                
                # Check timeout
                if time.time() - start_time > wait_timeout:
                    print(f"[LAND] TIMEOUT - Still at {current_alt:.1f}m")
                    return False
                
                await asyncio.sleep(1.0)  # Update every second
            
        except Exception as e:
            print(f"Landing failed: {e}")
            return False

    async def rtl(self, *, wait_timeout=120.0, emergency_override=False):
        """Return to Launch (RTL) - return to home position and land."""
        if not self._vehicle_ready(require_armable=False, emergency_override=emergency_override):
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            # CRITICAL: Validate home position is set before RTL
            home = getattr(vehicle, "home_location", None)
            if not home or (home.lat == 0.0 and home.lon == 0.0):
                print("❌ HOME POSITION NOT SET! RTL would fail - using emergency land instead")
                self.flight_logger.log_emergency("rtl_no_home", "home_position_invalid")
                return await self.emergency_land()
            
            print(f"[RTL] Home position: {home.lat:.6f}, {home.lon:.6f}")
            self.flight_logger.log_rtl("manual_command")
            
            # Set mode to RTL
            print("[RTL] Setting RTL mode")
            vehicle.mode = VehicleMode("RTL")
            
            # Wait for RTL mode confirmation
            if not await self._wait_for_condition(
                lambda: getattr(vehicle.mode, "name", None) == "RTL", 
                10.0, desc="RTL mode"
            ):
                print("[RTL] FAILED - Could not set RTL mode")
                return False
                
            print("[RTL] Returning to launch point...")
            
            # Track RTL progress with periodic updates
            start_time = time.time()
            last_update = 0
            
            while True:
                current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
                armed = getattr(vehicle, "armed", False)
                elapsed = time.time() - start_time
                
                # Log progress every 10 seconds
                if elapsed - last_update >= 10:
                    print(f"[RTL] Returning... Altitude: {current_alt:.1f}m (elapsed: {elapsed:.0f}s)")
                    last_update = elapsed
                
                # Check if RTL completed (vehicle disarmed)
                if not armed:
                    print(f"[RTL] SUCCESS - Returned to launch (elapsed: {elapsed:.0f}s)")
                    return True
                
                # Check timeout
                if elapsed > wait_timeout:
                    print(f"[RTL] TIMEOUT - Still returning after {elapsed:.0f}s")
                    return False
                
                await asyncio.sleep(2.0)  # Update every 2 seconds
            
        except Exception as e:
            print(f"RTL failed: {e}")
            return False

    async def fly_timed_mission(self, altitude: float, duration: float, broadcast_func=None) -> bool:
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
            print(f"[MISSION] Timed flight: {altitude}m for {duration}s")
            self.current_mission = {
                "type": "timed_flight",
                "altitude": altitude,
                "duration": duration,
                "start_time": datetime.now(),
                "end_time": datetime.now() + timedelta(seconds=duration)
            }
            
            # Step 1: Takeoff to target altitude
            if not await self.takeoff(altitude):
                print("[MISSION] FAILED - Takeoff unsuccessful")
                return False
                
            # Step 2: Hold position for specified duration with battery monitoring
            print(f"[MISSION] Holding position for {duration} seconds")
            mission_start = datetime.now()
            last_log_time = 0
            battery_emergency_triggered = False
            
            while (datetime.now() - mission_start).total_seconds() < duration:
                # Monitor vehicle status during mission
                if not getattr(vehicle, "armed", False):
                    print("[MISSION] INTERRUPTED - Vehicle disarmed")
                    break
                    
                # Critical battery monitoring during mission
                battery = getattr(vehicle, "battery", None)
                battery_level = getattr(battery, "level", None) if battery else None
                
                if (battery_level is not None and battery_level <= 30 and 
                    not battery_emergency_triggered and broadcast_func):
                    print(f"🚨 CRITICAL BATTERY DETECTED: {battery_level}% - Triggering emergency handling")
                    battery_emergency_triggered = True
                    
                    # Handle battery emergency with user choice
                    emergency_result = await self.handle_battery_emergency(broadcast_func)
                    print(f"🚨 Emergency action completed: {emergency_result}")
                    
                    # Mission ends here regardless of choice
                    print("[MISSION] TERMINATED - Battery emergency handled")
                    self.current_mission = None
                    return emergency_result.startswith(('rtl', 'land', 'timeout_rtl'))
                    
                current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
                elapsed = (datetime.now() - mission_start).total_seconds()
                remaining_time = duration - elapsed
                
                # Log every 10 seconds
                if elapsed - last_log_time >= 10:
                    progress_percent = int((elapsed / duration) * 100)
                    battery_info = f" | Battery: {battery_level}%" if battery_level is not None else ""
                    print(f"[MISSION] Progress: {progress_percent}% | Altitude: {current_alt:.1f}m | Remaining: {remaining_time:.0f}s{battery_info}")
                    last_log_time = elapsed
                
                await asyncio.sleep(1)
            
            print("[MISSION] Flight duration complete - returning to launch")
            
            # Step 3: Return to Launch with enhanced battery safety handling
            print("[MISSION] Flight duration complete - returning to launch")
            battery = getattr(vehicle, "battery", None)
            battery_level = getattr(battery, "level", None) if battery else None
            
            # Check if we need emergency handling before RTL
            if (battery_level is not None and battery_level <= 30 and 
                not battery_emergency_triggered and broadcast_func):
                print(f"🚨 CRITICAL BATTERY BEFORE RTL: {battery_level}% - Triggering emergency handling")
                emergency_result = await self.handle_battery_emergency(broadcast_func)
                print(f"🚨 Emergency action completed: {emergency_result}")
                self.current_mission = None
                return emergency_result.startswith(('rtl', 'land', 'timeout_rtl'))
            
            # Normal RTL with fallback
            if not await self.rtl():
                print("[MISSION] RTL failed - attempting emergency landing")
                if battery_level is not None and battery_level < SafetyConfig.MIN_BATTERY_LEVEL:
                    print(f"🚨 BATTERY EMERGENCY: {battery_level}% - Using emergency override for landing")
                    if not await self.land(force_land_here=True, emergency_override=True):
                        print("❌ Emergency landing failed - critical battery situation!")
                        return False
                else:
                    if not await self.land():
                        return False
                
            print("[MISSION] SUCCESS - Timed mission completed")
            self.current_mission = None
            return True
            
        except Exception as e:
            print(f"❌ Timed mission failed: {e}")
            self.current_mission = None
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
                return await self.rtl(wait_timeout=60.0, emergency_override=True)
            else:
                print("⚠️ No valid home - forced to land at current location")
                return await self.land(force_land_here=True, wait_timeout=30.0, emergency_override=True)
            
        except Exception as e:
            print(f"❌ Emergency land failed: {e}")
            self.flight_logger.log_emergency("emergency_land_failed", str(e))
            return False

    async def force_land_here(self, *, wait_timeout=30.0):
        """Force immediate landing at current location - USE ONLY IN EMERGENCIES!"""
        # Skip vehicle_ready check entirely for emergency force landing
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

    async def handle_battery_emergency(self, broadcast_func) -> str:
        """
        Handle critical battery emergency with user choice prompting.
        
        Args:
            broadcast_func: Function to broadcast messages to frontend
            
        Returns:
            str: Action taken ('rtl', 'land', or 'timeout_rtl')
        """
        if not self._vehicle_ready(require_armable=False):
            return 'error'
            
        vehicle = self.connection.vehicle
        battery = getattr(vehicle, "battery", None)
        battery_level = getattr(battery, "level", None) if battery else None
        
        if battery_level is None:
            print("❌ Cannot determine battery level for emergency handling")
            return 'error'
            
        # Get context information for recommendation
        distance_to_home = self.get_home_distance()
        current_alt = getattr(vehicle.location.global_relative_frame, "alt", 0) if vehicle.location.global_relative_frame else 0
        gps_fix = getattr(getattr(vehicle, "gps_0", None), "fix_type", 0) if hasattr(vehicle, "gps_0") else 0
        
        # Determine smart recommendation based on context
        recommendation = "RTL"  # Default safe choice
        reason = "Safe return to launch point"
        
        if distance_to_home is not None:
            if distance_to_home < 10:  # Very close to home
                recommendation = "LAND"
                reason = f"Close to home ({distance_to_home:.1f}m) - landing here is safe"
            elif distance_to_home > 100 and battery_level < 20:  # Far from home with very low battery
                recommendation = "LAND"
                reason = f"Far from home ({distance_to_home:.1f}m) with critical battery - immediate landing safer"
                
        if current_alt > 50 and battery_level < 15:  # High altitude with extremely low battery
            recommendation = "LAND"
            reason = f"High altitude ({current_alt:.1f}m) with extremely low battery - immediate landing required"
            
        if gps_fix < 3:  # Poor GPS
            recommendation = "LAND"
            reason = "Poor GPS fix - landing immediately is safer than RTL navigation"
        
        print(f"🚨 BATTERY EMERGENCY: {battery_level}% - Prompting user for action")
        print(f"💡 Recommendation: {recommendation} ({reason})")
        
        # Send emergency prompt to frontend
        prompt_id = f"battery_emergency_{int(time.time() * 1000)}"  # Use milliseconds for uniqueness
        emergency_data = {
            "type": "battery_emergency",
            "prompt_id": prompt_id,
            "battery_level": battery_level,
            "distance_to_home": distance_to_home,
            "altitude": current_alt,
            "gps_fix": gps_fix,
            "recommendation": recommendation,
            "reason": reason,
            "timeout_seconds": 10
        }
        
        print(f"🚨 Broadcasting emergency prompt with ID: {prompt_id}")
        await broadcast_func(json.dumps(emergency_data))
        
        # Wait for user response with 10-second timeout
        import asyncio
        from datetime import datetime, timedelta
        
        start_time = datetime.now()
        timeout_seconds = 10
        user_choice = None
        
        # Store the emergency state for response handling
        if not hasattr(self, '_emergency_prompts'):
            self._emergency_prompts = {}
        self._emergency_prompts[prompt_id] = {
            "start_time": start_time,
            "timeout": timeout_seconds,
            "response": None
        }
        
        print(f"🚨 Waiting for user response to prompt {prompt_id} (timeout: {timeout_seconds}s)")
        
        # Countdown and wait for response
        while (datetime.now() - start_time).total_seconds() < timeout_seconds:
            # Check if user responded
            if prompt_id in self._emergency_prompts and self._emergency_prompts[prompt_id]["response"]:
                user_choice = self._emergency_prompts[prompt_id]["response"]
                print(f"✅ User responded with: {user_choice}")
                break
                
            # Send countdown update
            remaining = timeout_seconds - (datetime.now() - start_time).total_seconds()
            countdown_data = {
                "type": "battery_emergency_countdown",
                "prompt_id": prompt_id,
                "remaining_seconds": max(0, remaining)
            }
            await broadcast_func(json.dumps(countdown_data))
            
            await asyncio.sleep(0.5)  # Check every 500ms
        
        # Execute chosen action
        if user_choice == "LAND":
            print("🚨 User chose EMERGENCY LAND - executing immediate landing")
            await broadcast_func(json.dumps({"type": "battery_emergency_action", "action": "LAND"}))
            success = await self.land(force_land_here=True, emergency_override=True)
            return "land" if success else "land_failed"
        elif user_choice == "RTL":
            print("🚨 User chose RTL - executing return to launch")
            await broadcast_func(json.dumps({"type": "battery_emergency_action", "action": "RTL"}))
            success = await self.rtl(emergency_override=True)
            return "rtl" if success else "rtl_failed"
        else:
            # Timeout - use default RTL
            print(f"⏰ No user response in {timeout_seconds}s - defaulting to RTL")
            await broadcast_func(json.dumps({"type": "battery_emergency_action", "action": "RTL_TIMEOUT"}))
            success = await self.rtl(emergency_override=True)
            return "timeout_rtl" if success else "timeout_rtl_failed"
    
    def handle_battery_emergency_response(self, prompt_id: str, choice: str) -> bool:
        """Handle user response to battery emergency prompt."""
        print(f"🚨 Attempting to handle emergency response: prompt_id={prompt_id}, choice={choice}")
        
        if not hasattr(self, '_emergency_prompts'):
            print(f"❌ No emergency prompts tracking available")
            return False
            
        if prompt_id not in self._emergency_prompts:
            print(f"❌ Prompt ID {prompt_id} not found. Available prompts: {list(self._emergency_prompts.keys())}")
            # Don't return False immediately - the user might have responded after timeout
            # but we should still log their choice for future reference
            print(f"⚠️ User choice '{choice}' noted but prompt already expired/processed")
            return False
            
        if choice not in ["RTL", "LAND"]:
            print(f"❌ Invalid choice: {choice}")
            return False
        
        # Check if prompt has already been responded to
        if self._emergency_prompts[prompt_id]["response"]:
            print(f"⚠️ Prompt {prompt_id} already has response: {self._emergency_prompts[prompt_id]['response']}")
            return False
            
        self._emergency_prompts[prompt_id]["response"] = choice
        print(f"✅ Emergency response received and recorded: {choice}")
        
        # Clean up the prompt after successful response (delayed cleanup)
        import asyncio
        async def cleanup_prompt():
            await asyncio.sleep(2)  
            if prompt_id in self._emergency_prompts:
                del self._emergency_prompts[prompt_id]
                print(f"🧹 Cleaned up prompt {prompt_id}")
        
        # Schedule cleanup but don't wait for it
        asyncio.create_task(cleanup_prompt())
        
        return True
