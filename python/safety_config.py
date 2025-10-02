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
    
    # Battery safety
    MIN_BATTERY_VOLTAGE_3S = 10.5   # volts for 3S LiPo
    MIN_BATTERY_VOLTAGE_4S = 14.0   # volts for 4S LiPo  
    MIN_BATTERY_VOLTAGE_6S = 21.0   # volts for 6S LiPo
    MIN_BATTERY_LEVEL = 20          # percentage
    
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