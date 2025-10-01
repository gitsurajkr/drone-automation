import asyncio
import time
from dronekit import VehicleMode

class Controller:
    def __init__(self, connection):
        self.connection = connection

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

    async def _wait_for_condition(self, check_fn, timeout, interval=0.5, desc="condition"):
        start = time.time()
        while not check_fn():
            if time.time() - start > timeout:
                print(f"Timed out waiting for {desc}.")
                return False
            await asyncio.sleep(interval)
        return True

    async def arm(self, *, wait_mode_timeout=5.0, wait_arm_timeout=15.0):
        if not self._vehicle_ready(require_armable=True):
            return False

        vehicle = self.connection.vehicle

        try:
            print("Setting mode to GUIDED...")
            vehicle.mode = VehicleMode("GUIDED")
            if not await self._wait_for_condition(lambda: getattr(vehicle.mode, "name", None) == "GUIDED", wait_mode_timeout, desc="GUIDED mode"):
                return False

            print("Arming vehicle...")
            vehicle.armed = True
            if not await self._wait_for_condition(lambda: getattr(vehicle, "armed", False),
                                                  wait_arm_timeout, desc="arming"):
                return False

            print("Vehicle is armed.")
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
