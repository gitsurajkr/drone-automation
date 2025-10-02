# Safety configuration and validation for drone operations
from datetime import datetime
from typing import Dict, Any, Optional
import logging

class SafetyConfig:
    """Comprehensive safety configuration for drone operations."""
    
    # Flight limits
    MAX_ALTITUDE = 30.0         # meters - conservative limit
    MIN_ALTITUDE = 0.5          # meters - minimum takeoff height
    MAX_FLIGHT_TIME = 300       # seconds - 5 minutes max flight
    MAX_HORIZONTAL_DISTANCE = 100  # meters from home
    
    # Battery safety - UPDATED FOR REAL DRONE PROTECTION
    MIN_BATTERY_VOLTAGE_3S = 11.1   # volts for 3S LiPo (3.7V per cell - SAFE)
    MIN_BATTERY_VOLTAGE_4S = 14.8   # volts for 4S LiPo (3.7V per cell - SAFE)
    MIN_BATTERY_VOLTAGE_6S = 22.2   # volts for 6S LiPo (3.7V per cell - SAFE)
    MIN_BATTERY_LEVEL = 30          # percentage - INCREASED for safety margin
    
    # GPS and navigation
    MIN_GPS_FIX = 3                 # GPS fix type (3D fix minimum)
    MIN_GPS_SATELLITES = 6          # minimum satellites
    MAX_GPS_HDOP = 2.0             # horizontal dilution of precision
    
    # Communication
    MAX_HEARTBEAT_AGE = 5.0        # seconds - connection freshness
    MAX_COMMAND_TIMEOUT = 30.0     # seconds - command execution timeout
    
    # Environmental
    MAX_WIND_SPEED = 10.0          # m/s - maximum safe wind speed
    MIN_VISIBILITY = 500           # meters - minimum visibility
    
    @classmethod
    def validate_takeoff_conditions(cls, vehicle_data: Dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate all conditions are safe for takeoff."""
        issues = []
        
        # Battery checks
        battery = vehicle_data.get('battery', {})
        if isinstance(battery, dict):
            voltage = battery.get('voltage')
            level = battery.get('level')
            
            if voltage and voltage < cls.MIN_BATTERY_VOLTAGE_3S:
                issues.append(f"Battery voltage too low: {voltage}V (need ≥{cls.MIN_BATTERY_VOLTAGE_3S}V)")
                
            if level and level < cls.MIN_BATTERY_LEVEL:
                issues.append(f"Battery level too low: {level}% (need ≥{cls.MIN_BATTERY_LEVEL}%)")
        
        # GPS checks  
        gps = vehicle_data.get('gps', {})
        if isinstance(gps, dict):
            fix_type = gps.get('fix_type', 0)
            satellites = gps.get('satellites_visible', 0)
            
            if fix_type < cls.MIN_GPS_FIX:
                issues.append(f"GPS fix insufficient: {fix_type} (need ≥{cls.MIN_GPS_FIX})")
                
            if satellites < cls.MIN_GPS_SATELLITES:
                issues.append(f"Not enough GPS satellites: {satellites} (need ≥{cls.MIN_GPS_SATELLITES})")
        
        # System status checks
        armed = vehicle_data.get('armed', False)
        if not armed:
            issues.append("Vehicle must be armed before takeoff")
            
        mode = vehicle_data.get('mode', '').upper()
        if mode != 'GUIDED':
            issues.append(f"Vehicle must be in GUIDED mode (currently: {mode})")
            
        # Heartbeat check
        last_heartbeat = vehicle_data.get('last_heartbeat')
        if last_heartbeat and last_heartbeat > cls.MAX_HEARTBEAT_AGE:
            issues.append(f"Connection too old: {last_heartbeat}s (need <{cls.MAX_HEARTBEAT_AGE}s)")
        
        return len(issues) == 0, issues
    
    @classmethod
    def validate_altitude(cls, altitude: float) -> tuple[bool, str]:
        """Validate requested altitude is safe."""
        if altitude < cls.MIN_ALTITUDE:
            return False, f"Altitude too low: {altitude}m (minimum: {cls.MIN_ALTITUDE}m)"
        if altitude > cls.MAX_ALTITUDE:
            return False, f"Altitude too high: {altitude}m (maximum: {cls.MAX_ALTITUDE}m)"
        return True, "Altitude within safe limits"
    
    @classmethod
    def validate_flight_time(cls, duration: float) -> tuple[bool, str]:
        """Validate requested flight duration is safe."""
        if duration <= 0:
            return False, "Flight duration must be positive"
        if duration > cls.MAX_FLIGHT_TIME:
            return False, f"Flight duration too long: {duration}s (maximum: {cls.MAX_FLIGHT_TIME}s)"
        return True, "Flight duration within safe limits"
    
    @classmethod
    def validate_gps_integrity(cls, gps_data: Dict[str, Any], is_sitl: bool = False) -> tuple[bool, str]:
        """Validate GPS integrity to prevent spoofing/interference crashes.
        
        Args:
            gps_data: GPS telemetry data containing 'eph' and 'groundspeed'
            is_sitl: If True, use relaxed validation for SITL testing
            
        Returns:
            tuple[bool, str]: (is_valid, error_message)
        """
        # Check HDOP (GPS accuracy) with SITL-aware limits
        eph = gps_data.get('eph', 999)  # Horizontal accuracy
        max_hdop = 200.0 if is_sitl else 2.0  # SITL has poor simulated GPS
        
        if eph > max_hdop:
            return False, f"GPS accuracy poor: HDOP {eph} (need <{max_hdop})"
        
        # Check for impossible speeds (GPS spoofing detection)
        groundspeed = gps_data.get('groundspeed', 0)
        max_speed = 100 if is_sitl else 50  # SITL can have quirky speeds
        
        if groundspeed > max_speed:  # Adjusted for SITL vs hardware
            return False, f"GPS may be spoofed: impossible speed {groundspeed} m/s"
        
        gps_type = "SITL simulated" if is_sitl else "hardware"
        return True, f"GPS integrity OK ({gps_type})"

    @classmethod
    def validate_battery_under_load(cls, voltage_idle: float, voltage_load: float) -> tuple[bool, str]:
        """Detect weak batteries that fail under load."""
        if voltage_idle <= 0 or voltage_load <= 0:
            return True, "Battery load test skipped"
            
        voltage_drop = voltage_idle - voltage_load
        if voltage_drop > 0.8:  # 0.8V drop indicates very weak battery
            return False, f"Battery weak under load: {voltage_drop:.1f}V drop"
        elif voltage_drop > 0.5:  # 0.5V drop indicates marginal battery
            return False, f"Battery marginal under load: {voltage_drop:.1f}V drop"
        
        return True, f"Battery strong under load: {voltage_drop:.1f}V drop"

    @classmethod
    def get_emergency_actions(cls) -> list[str]:
        """Get list of available emergency actions."""
        return [
            "emergency_disarm",
            "emergency_land", 
            "emergency_rtl",
            "kill_motors"
        ]

class FlightLogger:
    """Logger for flight operations and safety events."""
    
    def __init__(self):
        self.logger = logging.getLogger('drone_safety')
        self.logger.setLevel(logging.INFO)
        
        # Create file handler
        handler = logging.FileHandler('/tmp/drone_flight.log')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def log_takeoff(self, altitude: float, conditions: Dict[str, Any]):
        """Log takeoff event with conditions."""
        self.logger.info(f"TAKEOFF: altitude={altitude}m, conditions={conditions}")
    
    def log_landing(self, location: Optional[Dict[str, Any]] = None):
        """Log landing event."""
        self.logger.info(f"LANDING: location={location}")
    
    def log_rtl(self, reason: str = "manual"):
        """Log return to launch event.""" 
        self.logger.info(f"RTL: reason={reason}")
    
    def log_emergency(self, action: str, reason: str):
        """Log emergency action."""
        self.logger.error(f"EMERGENCY: action={action}, reason={reason}")
    
    def log_safety_violation(self, violation: str, data: Dict[str, Any]):
        """Log safety violation."""
        self.logger.warning(f"SAFETY_VIOLATION: {violation}, data={data}")