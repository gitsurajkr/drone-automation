# Drone Automation Configuration

WS_HOST = "0.0.0.0"
WS_PORT = 8765
DRONE_ID = "drone_001"
TELEMETRY_INTERVAL = 1

# Connection settings
# For hardware drone, use: "/dev/ttyACM0" or "/dev/ttyUSB0"
# For SITL, use: "tcp:127.0.0.1:5760" or "udp:127.0.0.1:14550"
DEFAULT_CONNECTION_STRING = "udp:127.0.0.1:14550"
DEFAULT_BAUD_RATE = 115200


SITL_PATTERNS = ["127.0.0.1", "localhost", "tcp:", "udp:", ":14550", ":5760"]

# =============================================================================
# WAYPOINT NAVIGATION CONFIGURATION
# =============================================================================

class WaypointConfig:
    """Configuration settings for waypoint navigation system."""
    
    # Mission parameters
    DEFAULT_ALTITUDE = 20.0          # Default altitude if not specified (meters)
    TAKEOFF_ALTITUDE = 15.0          # Standard takeoff altitude (meters)
    MIN_WAYPOINT_DISTANCE = 2.0      # Minimum separation distance (meters)
    ARRIVAL_THRESHOLD = 2.0          # Distance for waypoint completion (meters)
    MAX_WAYPOINT_TIMEOUT = 120.0     # Maximum time per waypoint (seconds)
    
    # Battery emergency thresholds
    CRITICAL_BATTERY_LEVEL = 30.0    # Emergency action trigger (percentage)
    LOW_BATTERY_WARNING = 40.0       # Warning level (percentage)
    EMERGENCY_BATTERY_LEVEL = 20.0   # Immediate land trigger (percentage)
    
    # GPS and navigation
    GPS_RECOVERY_TIMEOUT = 15.0      # GPS recovery wait time (seconds)
    YAW_ALIGNMENT_TIMEOUT = 10.0     # Time to align with home before RTL (seconds)
    LOITER_STABILIZATION_TIME = 5.0  # Stabilization time in LOITER (seconds)
    
    # Emergency response
    EMERGENCY_RESPONSE_TIMEOUT = 30.0  # User response timeout (seconds)
    AUTO_RTL_ON_TIMEOUT = True        # Auto RTL if no user response
    
    # Post-mission behavior
    AUTO_RTL_ON_MISSION_COMPLETE = True  # Automatically RTL after waypoint mission completes
    POST_MISSION_ACTION = "RTL"          # Options: "RTL", "LOITER", "LAND", "NONE"
    
    # Mission retry settings
    MAX_WAYPOINT_FAILURES = 2         # Maximum failed waypoints before abort
    STALL_DETECTION_THRESHOLD = 0.5   # Minimum progress in meters
    MAX_STALL_CHECKS = 10            # Stall checks before retry
    
    # Mission planning
    GRID_MAX_SIZE = 20               # Maximum grid pattern size
    GRID_MAX_SPACING = 1000          # Maximum grid spacing (meters)
    CIRCLE_MAX_RADIUS = 5000         # Maximum circular mission radius (meters)
    CIRCLE_MAX_POINTS = 50           # Maximum points in circular mission
    
    @classmethod
    def get_config_dict(cls):
        """Return configuration as dictionary."""
        return {
            'default_altitude': cls.DEFAULT_ALTITUDE,
            'takeoff_altitude': cls.TAKEOFF_ALTITUDE,
            'min_waypoint_distance': cls.MIN_WAYPOINT_DISTANCE,
            'arrival_threshold': cls.ARRIVAL_THRESHOLD,
            'max_waypoint_timeout': cls.MAX_WAYPOINT_TIMEOUT,
            'critical_battery_level': cls.CRITICAL_BATTERY_LEVEL,
            'low_battery_warning': cls.LOW_BATTERY_WARNING,
            'emergency_battery_level': cls.EMERGENCY_BATTERY_LEVEL,
            'gps_recovery_timeout': cls.GPS_RECOVERY_TIMEOUT,
            'yaw_alignment_timeout': cls.YAW_ALIGNMENT_TIMEOUT,
            'loiter_stabilization_time': cls.LOITER_STABILIZATION_TIME,
            'emergency_response_timeout': cls.EMERGENCY_RESPONSE_TIMEOUT,
            'auto_rtl_on_timeout': cls.AUTO_RTL_ON_TIMEOUT,
            'auto_rtl_on_mission_complete': cls.AUTO_RTL_ON_MISSION_COMPLETE,
            'post_mission_action': cls.POST_MISSION_ACTION,
            'max_waypoint_failures': cls.MAX_WAYPOINT_FAILURES,
            'stall_detection_threshold': cls.STALL_DETECTION_THRESHOLD,
            'max_stall_checks': cls.MAX_STALL_CHECKS
        }


# ----------------------------------
# FLIGHT SAFETY CONFIGURATION
# ----------------------------------

class FlightSafetyConfig:
    
    # Altitude limits
    MAX_ALTITUDE = 30.0         # meters - conservative limit
    MIN_ALTITUDE = 0.5          # meters - minimum takeoff height
    MAX_FLIGHT_TIME = 300       # seconds - 5 minutes max flight
    MAX_HORIZONTAL_DISTANCE = 100  # meters from home
    
    # Environmental limits
    MAX_WIND_SPEED = 10.0       # m/s - maximum safe wind speed
    MIN_VISIBILITY = 500        # meters - minimum visibility
    
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


# -----------------------------------
# BATTERY SAFETY CONFIGURATION
# -----------------------------------

class BatterySafetyConfig:
    """Battery monitoring and safety thresholds."""
    
    # Battery voltage limits for different configurations
    MIN_BATTERY_VOLTAGE_3S = 11.1   # volts for 3S LiPo (3.7V per cell)
    MIN_BATTERY_VOLTAGE_4S = 14.8   # volts for 4S LiPo (3.7V per cell)
    MIN_BATTERY_VOLTAGE_6S = 22.2   # volts for 6S LiPo (3.7V per cell)
    
    # Battery percentage thresholds
    MIN_BATTERY_LEVEL = 30          # percentage - minimum for operations
    CRITICAL_BATTERY_LEVEL = 25     # percentage - emergency RTL trigger
    EMERGENCY_BATTERY_LEVEL = 20    # percentage - immediate land trigger
    
    # Battery health monitoring
    MAX_VOLTAGE_DROP_UNDER_LOAD = 0.8  # volts - weak battery detection
    MARGINAL_VOLTAGE_DROP = 0.5        # volts - marginal battery warning
    
    @classmethod
    def get_min_voltage_for_cell_count(cls, voltage: float) -> float:
        """Get minimum safe voltage based on detected cell configuration."""
        if voltage > 20:  # 6S battery
            return cls.MIN_BATTERY_VOLTAGE_6S
        elif voltage > 13:  # 4S battery  
            return cls.MIN_BATTERY_VOLTAGE_4S
        else:  # 3S battery (default)
            return cls.MIN_BATTERY_VOLTAGE_3S
    
    @classmethod
    def validate_battery_under_load(cls, voltage_idle: float, voltage_load: float) -> tuple[bool, str]:
        """Detect weak batteries that fail under load."""
        if voltage_idle <= 0 or voltage_load <= 0:
            return True, "Battery load test skipped"
            
        voltage_drop = voltage_idle - voltage_load
        if voltage_drop > cls.MAX_VOLTAGE_DROP_UNDER_LOAD:
            return False, f"Battery weak under load: {voltage_drop:.1f}V drop"
        elif voltage_drop > cls.MARGINAL_VOLTAGE_DROP:
            return False, f"Battery marginal under load: {voltage_drop:.1f}V drop"
        
        return True, f"Battery strong under load: {voltage_drop:.1f}V drop"


# =============================================================================
# GPS SAFETY CONFIGURATION
# =============================================================================

class GPSSafetyConfig:
    """GPS and navigation safety parameters."""
    
    # GPS quality requirements
    MIN_GPS_FIX = 3                 # GPS fix type (3D fix minimum)
    MIN_GPS_SATELLITES = 6          # minimum satellites
    MAX_GPS_HDOP = 2.0             # horizontal dilution of precision
    MAX_GPS_HDOP_SITL = 200        # more lenient for SITL testing
    
    # GPS integrity monitoring
    MAX_REASONABLE_GROUNDSPEED = 50  # m/s - spoofing detection
    GPS_SPOOFING_SPEED_LIMIT = 50   # m/s - impossible drone speed
    
    @classmethod
    def validate_gps_integrity(cls, gps_data: dict, is_sitl: bool = False) -> tuple[bool, str]:
        """Validate GPS integrity to prevent spoofing/interference crashes."""
        # Check HDOP (GPS accuracy)
        eph = gps_data.get('eph', 999)  # Horizontal accuracy
        
        if is_sitl:
            # SITL GPS is often poor quality but safe for testing
            if eph > cls.MAX_GPS_HDOP_SITL:
                return False, f"GPS accuracy extremely poor even for SITL: HDOP {eph} (need <{cls.MAX_GPS_HDOP_SITL})"
            elif eph > 50:
                print(f"WARN: SITL GPS accuracy poor but acceptable: HDOP {eph}")
        else:
            # Real hardware needs good GPS
            if eph > cls.MAX_GPS_HDOP:
                return False, f"GPS accuracy poor: HDOP {eph} (need <{cls.MAX_GPS_HDOP})"
        
        # Check for impossible speeds (GPS spoofing detection)
        groundspeed = gps_data.get('groundspeed', 0)
        if groundspeed > cls.GPS_SPOOFING_SPEED_LIMIT:
            return False, f"GPS may be spoofed: impossible speed {groundspeed} m/s"
        
        return True, "GPS integrity OK"


# =============================================================================
# COMMUNICATION SAFETY CONFIGURATION
# =============================================================================

class CommunicationSafetyConfig:
    """Communication and connection safety parameters."""
    
    # Connection monitoring
    MAX_HEARTBEAT_AGE = 5.0        # seconds - connection freshness
    MAX_COMMAND_TIMEOUT = 30.0     # seconds - command execution timeout
    CONNECTION_RETRY_INTERVAL = 2.0  # seconds between reconnection attempts
    MAX_CONNECTION_RETRIES = 5     # maximum reconnection attempts
    
    # Message validation
    MAX_MESSAGE_SIZE = 65536       # bytes - maximum message size
    MIN_MESSAGE_INTERVAL = 0.1     # seconds - rate limiting


# =============================================================================
# SYSTEM SAFETY CONFIGURATION  
# =============================================================================

class SystemSafetyConfig:
    """Overall system safety configuration and validation."""
    
    # Emergency actions
    EMERGENCY_ACTIONS = [
        "emergency_disarm",
        "emergency_land", 
        "emergency_rtl",
        "kill_motors"
    ]
    
    # System health monitoring
    MAX_CPU_USAGE = 90.0           # percentage
    MIN_FREE_MEMORY = 512          # MB
    MAX_TEMPERATURE = 85.0         # Celsius for system components
    
    @classmethod
    def validate_takeoff_conditions(cls, vehicle_data: dict) -> tuple[bool, list[str]]:
        """Comprehensive takeoff condition validation."""
        issues = []
        
        # Battery checks
        battery = vehicle_data.get('battery', {})
        if isinstance(battery, dict):
            voltage = battery.get('voltage')
            level = battery.get('level')
            
            if voltage:
                min_voltage = BatterySafetyConfig.get_min_voltage_for_cell_count(voltage)
                if voltage < min_voltage:
                    issues.append(f"Battery voltage too low: {voltage}V (need ≥{min_voltage}V)")
            
            if level and level < BatterySafetyConfig.MIN_BATTERY_LEVEL:
                issues.append(f"Battery level too low: {level}% (need ≥{BatterySafetyConfig.MIN_BATTERY_LEVEL}%)")
        
        # GPS checks  
        gps = vehicle_data.get('gps', {})
        if isinstance(gps, dict):
            fix_type = gps.get('fix_type', 0)
            satellites = gps.get('satellites_visible', 0)
            
            if fix_type < GPSSafetyConfig.MIN_GPS_FIX:
                issues.append(f"GPS fix insufficient: {fix_type} (need ≥{GPSSafetyConfig.MIN_GPS_FIX})")
            
            if satellites < GPSSafetyConfig.MIN_GPS_SATELLITES:
                issues.append(f"Not enough GPS satellites: {satellites} (need ≥{GPSSafetyConfig.MIN_GPS_SATELLITES})")
        
        # System status checks
        armed = vehicle_data.get('armed', False)
        if not armed:
            issues.append("Vehicle must be armed before takeoff")
        
        mode = vehicle_data.get('mode', '').upper()
        if mode != 'GUIDED':
            issues.append(f"Vehicle must be in GUIDED mode (currently: {mode})")
        
        # Heartbeat check
        last_heartbeat = vehicle_data.get('last_heartbeat')
        if last_heartbeat and last_heartbeat > CommunicationSafetyConfig.MAX_HEARTBEAT_AGE:
            issues.append(f"Connection too old: {last_heartbeat}s (need <{CommunicationSafetyConfig.MAX_HEARTBEAT_AGE}s)")
        
        return len(issues) == 0, issues
    
    @classmethod
    def get_emergency_actions(cls) -> list[str]:
        """Get list of available emergency actions."""
        return cls.EMERGENCY_ACTIONS.copy()


# =============================================================================
# FLIGHT LOGGING CONFIGURATION
# =============================================================================

class FlightLoggingConfig:
    """Flight logging and telemetry configuration."""
    
    # Logging settings
    LOG_LEVEL = "INFO"
    LOG_FILE_PATH = "/tmp/drone_flight.log"
    LOG_ROTATION_SIZE = 10485760   # 10MB
    LOG_RETENTION_DAYS = 30
    
    # Telemetry logging
    TELEMETRY_LOG_INTERVAL = 1.0   # seconds
    HIGH_FREQUENCY_LOG_PARAMS = [
        'battery_voltage', 'battery_level', 'gps_fix', 'mode'
    ]
    
    # Event types for structured logging
    LOG_EVENT_TYPES = [
        'takeoff', 'landing', 'rtl', 'emergency', 'safety_violation', 
        'waypoint_reached', 'mission_start', 'mission_complete', 'mode_change'
    ]


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

class SafetyConfig:
    """Legacy compatibility class - redirects to new config classes."""
    
    # Flight limits - redirect to FlightSafetyConfig
    MAX_ALTITUDE = FlightSafetyConfig.MAX_ALTITUDE
    MIN_ALTITUDE = FlightSafetyConfig.MIN_ALTITUDE
    MAX_FLIGHT_TIME = FlightSafetyConfig.MAX_FLIGHT_TIME
    MAX_HORIZONTAL_DISTANCE = FlightSafetyConfig.MAX_HORIZONTAL_DISTANCE
    
    # Battery safety - redirect to BatterySafetyConfig
    MIN_BATTERY_VOLTAGE_3S = BatterySafetyConfig.MIN_BATTERY_VOLTAGE_3S
    MIN_BATTERY_VOLTAGE_4S = BatterySafetyConfig.MIN_BATTERY_VOLTAGE_4S
    MIN_BATTERY_VOLTAGE_6S = BatterySafetyConfig.MIN_BATTERY_VOLTAGE_6S
    MIN_BATTERY_LEVEL = BatterySafetyConfig.MIN_BATTERY_LEVEL
    
    # GPS and navigation - redirect to GPSSafetyConfig
    MIN_GPS_FIX = GPSSafetyConfig.MIN_GPS_FIX
    MIN_GPS_SATELLITES = GPSSafetyConfig.MIN_GPS_SATELLITES
    MAX_GPS_HDOP = GPSSafetyConfig.MAX_GPS_HDOP
    
    # Communication - redirect to CommunicationSafetyConfig
    MAX_HEARTBEAT_AGE = CommunicationSafetyConfig.MAX_HEARTBEAT_AGE
    MAX_COMMAND_TIMEOUT = CommunicationSafetyConfig.MAX_COMMAND_TIMEOUT
    
    # Environmental - redirect to FlightSafetyConfig
    MAX_WIND_SPEED = FlightSafetyConfig.MAX_WIND_SPEED
    MIN_VISIBILITY = FlightSafetyConfig.MIN_VISIBILITY
    
    @classmethod
    def validate_takeoff_conditions(cls, vehicle_data: dict) -> tuple[bool, list[str]]:
        """Legacy method - redirects to SystemSafetyConfig."""
        return SystemSafetyConfig.validate_takeoff_conditions(vehicle_data)
    
    @classmethod
    def validate_altitude(cls, altitude: float) -> tuple[bool, str]:
        """Legacy method - redirects to FlightSafetyConfig."""
        return FlightSafetyConfig.validate_altitude(altitude)
    
    @classmethod
    def validate_flight_time(cls, duration: float) -> tuple[bool, str]:
        """Legacy method - redirects to FlightSafetyConfig."""
        return FlightSafetyConfig.validate_flight_time(duration)
    
    @classmethod
    def validate_gps_integrity(cls, gps_data: dict, is_sitl: bool = False) -> tuple[bool, str]:
        """Legacy method - redirects to GPSSafetyConfig."""
        return GPSSafetyConfig.validate_gps_integrity(gps_data, is_sitl)
    
    @classmethod
    def validate_battery_under_load(cls, voltage_idle: float, voltage_load: float) -> tuple[bool, str]:
        """Legacy method - redirects to BatterySafetyConfig."""
        return BatterySafetyConfig.validate_battery_under_load(voltage_idle, voltage_load)
    
    @classmethod
    def get_emergency_actions(cls) -> list[str]:
        """Legacy method - redirects to SystemSafetyConfig."""
        return SystemSafetyConfig.get_emergency_actions()


# =============================================================================
# FLIGHT LOGGER CLASS
# =============================================================================

import logging
from datetime import datetime
from typing import Dict, Any, Optional

class FlightLogger:
    """Enhanced flight operations logger with structured logging."""
    
    def __init__(self, log_file_path: str = None):
        self.log_file_path = log_file_path or FlightLoggingConfig.LOG_FILE_PATH
        self.logger = logging.getLogger('drone_flight')
        self.logger.setLevel(getattr(logging, FlightLoggingConfig.LOG_LEVEL))
        
        # Avoid duplicate handlers
        if not self.logger.handlers:
            # Create file handler
            handler = logging.FileHandler(self.log_file_path)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            
            # Create console handler for important events
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
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
    
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log generic flight event with structured data."""
        if event_type in FlightLoggingConfig.LOG_EVENT_TYPES:
            level = logging.ERROR if 'emergency' in event_type.lower() else logging.INFO
            self.logger.log(level, f"EVENT: type={event_type}, data={data}")
        else:
            self.logger.warning(f"UNKNOWN_EVENT: type={event_type}, data={data}")
    
    def log_waypoint_reached(self, waypoint_number: int, total_waypoints: int, coordinates: tuple, time_taken: float = 0.0):
        """Log waypoint reached event."""
        self.log_event('waypoint_reached', {
            'waypoint_number': waypoint_number,
            'total_waypoints': total_waypoints,
            'coordinates': coordinates,
            'time_taken_seconds': time_taken,
            'timestamp': datetime.now().isoformat()
        })
    
    def log_mission_start(self, mission_type: str, waypoint_count: int):
        """Log mission start event."""
        self.log_event('mission_start', {
            'mission_type': mission_type,
            'waypoint_count': waypoint_count,
            'timestamp': datetime.now().isoformat()
        })
    
    def log_mission_complete(self, success: bool, summary: Dict[str, Any]):
        """Log mission completion event."""
        self.log_event('mission_complete', {
            'success': success,
            'summary': summary,
            'timestamp': datetime.now().isoformat()
        })
