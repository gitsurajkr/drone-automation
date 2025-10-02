import asyncio
import time
from dronekit import VehicleMode

class Controller:
    def __init__(self, connection):
        self.connection = connection
        self.is_sitl = False  # Track if this is a SITL connection

    def _vehicle_ready(self, require_armable=True):
        
        # check vehicle connectivity
        if not getattr(self.connection, "is_connected", False) or not getattr(self.connection, "vehicle", None):
            print("Vehicle not connected.")
            return False

        vehicle = self.connection.vehicle

        # Check heartbeat freshness
        last_heartbeat = getattr(vehicle, "last_heartbeat", None)
        if last_heartbeat is not None and last_heartbeat > 5.0:
            print(f"Vehicle heartbeat too old: {last_heartbeat}s")
            return False

        if require_armable and not getattr(vehicle, "is_armable", False):
            print("Vehicle is not armable.")
            return False

        # GPS check - more strict for arming
        gps = getattr(vehicle, "gps_0", None)
        if gps is not None:
            fix = getattr(gps, "fix_type", 0) or 0
            if require_armable and fix < 3:  # Only strict for arming
                print(f"GPS fix not sufficient for arming (fix_type={fix}, need ≥3).")
                return False
            elif fix < 2:  # Basic connectivity check
                print(f"GPS fix too poor (fix_type={fix}).")
                return False

        # Battery check
        battery = getattr(vehicle, "battery", None)
        if battery is not None:
            batt_level = getattr(battery, "level", None)
            if batt_level is not None and batt_level < 20:
                print(f"Battery level too low ({batt_level}%, need ≥20%).")
                return False
            
            # Check battery voltage if available
            voltage = getattr(battery, "voltage", None)
            if voltage is not None and voltage < 10.5:  # For 3S LiPo minimum
                print(f"Battery voltage too low ({voltage}V).")
                return False

        # Check system status if available
        if hasattr(vehicle, 'system_status'):
            sys_status = getattr(vehicle.system_status, 'state', 'UNKNOWN')
            if require_armable and sys_status not in ['STANDBY', 'ACTIVE']:
                print(f"Vehicle not in safe state: {sys_status}")
                return False

        return True

    async def setup_sitl_connection(self):
        """Setup SITL-specific configuration after connection."""
        if not self._vehicle_ready(require_armable=False):
            return False
            
        vehicle = self.connection.vehicle
        
        try:
            print("Configuring SITL vehicle...")
            
            # Disable arming checks for SITL
            print("Disabling arming checks (ARMING_CHECK=0)...")
            vehicle.parameters['ARMING_CHECK'] = 0
            
            # Wait for parameter to be set
            await asyncio.sleep(2)
            
            # Verify parameter was set
            arming_check = vehicle.parameters.get('ARMING_CHECK', -1)
            print(f"ARMING_CHECK parameter set to: {arming_check}")
            
            self.is_sitl = True
            print("SITL setup complete.")
            return True
            
        except Exception as e:
            print(f"SITL setup failed: {e}")
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
