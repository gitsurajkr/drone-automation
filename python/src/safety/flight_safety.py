
"""
Flight Safety Manager
Centralized safety validation with essential monitoring and logging.
"""

import time
import asyncio
import logging
import math
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from config.config import (
    FlightSafetyConfig, BatterySafetyConfig, GPSSafetyConfig,
    CommunicationSafetyConfig, SystemSafetyConfig, FlightLogger
)
from dronekit import VehicleMode

class FlightSafetyManager:
    """Centralized flight safety validation and monitoring."""
    
    def __init__(self):
        # Setup logging
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger('flight_safety')
        
        # Legacy logger for compatibility
        self.flight_logger = FlightLogger()
        
        self.emergency_prompts = {}  # Track active emergency prompts
        
        # Safety state tracking
        self.safety_violations = []
        self.last_safety_check = None
        
        # Environmental monitoring
        self.wind_speed_limit = 15.0  # m/s
        self.weather_safe = True
        
        # Connection monitoring
        self.connection_quality_history = []
        
        self.logger.info("Enhanced Flight Safety Manager initialized")
        
    def validate_vehicle_ready(self, connection, require_armable: bool = True, 
                              emergency_override: bool = False) -> bool:
        # Validate if the vehicle is ready for flight
        if not connection or not getattr(connection, "is_connected", False):
            self.flight_logger.log_event('safety_check_failed', {'reason': 'not_connected'})
            return False

        vehicle = getattr(connection, "vehicle", None)
        if not vehicle:
            self.flight_logger.log_event('safety_check_failed', {'reason': 'no_vehicle'})
            return False

        # Check heartbeat freshness
        last_heartbeat = getattr(vehicle, "last_heartbeat", None)
        if (not emergency_override and last_heartbeat is not None and 
            last_heartbeat > CommunicationSafetyConfig.MAX_HEARTBEAT_AGE):
            self.flight_logger.log_event('safety_check_failed', {
                'reason': 'stale_heartbeat',
                'heartbeat_age': last_heartbeat
            })
            return False

        # Check armable status
        if require_armable and not getattr(vehicle, "is_armable", False):
            self.flight_logger.log_event('safety_check_failed', {'reason': 'not_armable'})
            return False

        # GPS validation
        if not self._validate_gps_safety(vehicle, emergency_override):
            return False

        # Battery validation  
        if not self._validate_battery_safety(vehicle, emergency_override):
            return False

        self.flight_logger.log_event('safety_check_passed', {
            'require_armable': require_armable,
            'emergency_override': emergency_override
        })
        return True
    
    def _validate_gps_safety(self, vehicle, emergency_override: bool = False) -> bool:
        """Validate GPS safety requirements."""
        gps = getattr(vehicle, "gps_0", None)
        if not gps:
            self.flight_logger.log_event('gps_check_failed', {'reason': 'no_gps_data'})
            return False

        fix = getattr(gps, "fix_type", 0) or 0
        satellites = getattr(gps, "satellites_visible", 0) or 0

        # Check GPS fix quality
        if fix < GPSSafetyConfig.MIN_GPS_FIX:
            if not emergency_override:
                self.flight_logger.log_event('gps_check_failed', {
                    'reason': 'poor_fix',
                    'fix_type': fix,
                    'required': GPSSafetyConfig.MIN_GPS_FIX
                })
                return False

        # Check satellite count
        if satellites < GPSSafetyConfig.MIN_GPS_SATELLITES:
            if not emergency_override:
                self.flight_logger.log_event('gps_check_failed', {
                    'reason': 'insufficient_satellites',
                    'satellites': satellites,
                    'required': GPSSafetyConfig.MIN_GPS_SATELLITES
                })
                return False

        return True
    
    def _validate_battery_safety(self, vehicle, emergency_override: bool = False) -> bool:
        """Validate battery safety requirements."""
        battery = getattr(vehicle, "battery", None)
        # If battery object is missing or reports zero-values, treat as missing telemetry
        if not battery:
            self.flight_logger.log_event('battery_check_failed', {'reason': 'no_battery_data'})
            return emergency_override

        # Extract values safely
        try:
            voltage = getattr(battery, "voltage", None)
            current = getattr(battery, "current", None)
            level = getattr(battery, "level", None)
        except Exception:
            voltage = None
            current = None
            level = None

        # Consider None or zero as missing telemetry
        missing_voltage = (voltage is None) or (isinstance(voltage, (int, float)) and float(voltage) <= 0.0)
        missing_level = (level is None) or (isinstance(level, (int, float)) and float(level) <= 0.0)

        if missing_voltage and missing_level:
            # No useful battery telemetry available
            self.flight_logger.log_event('battery_check_failed', {
                'reason': 'battery_telemetry_missing',
                'voltage': voltage,
                'level': level,
                'current': current
            })
            return emergency_override

        # If level provided, check against threshold
        if level is not None:
            try:
                lvl = float(level)
            except Exception:
                lvl = None
            if lvl is not None and lvl < BatterySafetyConfig.MIN_BATTERY_LEVEL:
                if not emergency_override:
                    self.flight_logger.log_event('battery_check_failed', {
                        'reason': 'low_battery_level',
                        'level': lvl,
                        'required': BatterySafetyConfig.MIN_BATTERY_LEVEL
                    })
                    return False

        # If voltage provided, verify against minimum
        if voltage is not None:
            try:
                volt = float(voltage)
            except Exception:
                volt = None
            if volt is not None:
                min_voltage = BatterySafetyConfig.get_min_voltage_for_cell_count(volt)
                if volt < min_voltage:
                    if not emergency_override:
                        self.flight_logger.log_event('battery_check_failed', {
                            'reason': 'low_battery_voltage',
                            'voltage': volt,
                            'min_required': min_voltage
                        })
                        return False

        return True
    
    def validate_altitude_safety(self, altitude: float, is_takeoff: bool = False) -> Tuple[bool, str]:
        """Validate altitude is within safe limits."""
        try:
            alt = float(altitude)
            
            if is_takeoff:
                # More restrictive for takeoff
                max_alt = min(FlightSafetyConfig.MAX_ALTITUDE, 30.0)
                min_alt = max(FlightSafetyConfig.MIN_ALTITUDE, 2.0)   
            else:
                max_alt = FlightSafetyConfig.MAX_ALTITUDE
                min_alt = FlightSafetyConfig.MIN_ALTITUDE
            
            if min_alt <= alt <= max_alt:
                return True, "Altitude within safe limits"
            else:
                return False, f"Altitude {alt}m outside safe range {min_alt}-{max_alt}m"
                
        except (ValueError, TypeError):
            return False, "Invalid altitude format"
    
    def validate_distance_from_home(self, current_position: Tuple[float, float], 
                                   home_position: Tuple[float, float]) -> Tuple[bool, str]:
        """Validate drone is within safe distance from home."""
        from ..navigation.navigation_utils import NavigationUtils
        
        distance = NavigationUtils.calculate_distance(current_position, home_position)
        if distance == float('inf'):
            return False, "Cannot calculate distance from home"
        
        if distance > FlightSafetyConfig.MAX_HORIZONTAL_DISTANCE:
            return False, f"Distance from home {distance:.1f}m exceeds limit {FlightSafetyConfig.MAX_HORIZONTAL_DISTANCE}m"
        
        return True, f"Distance from home: {distance:.1f}m"
    
    def validate_flight_time_limit(self, flight_start_time: Optional[datetime]) -> Tuple[bool, str]:
        """Validate flight time is within limits."""
        if not flight_start_time:
            return True, "Flight time tracking not started"
        
        flight_duration = (datetime.now() - flight_start_time).total_seconds()
        
        if flight_duration > FlightSafetyConfig.MAX_FLIGHT_TIME:
            return False, f"Flight time {flight_duration:.0f}s exceeds limit {FlightSafetyConfig.MAX_FLIGHT_TIME}s"
        
        return True, f"Flight time: {flight_duration:.0f}s"
    
    def check_emergency_conditions(self, vehicle) -> List[str]:
        """Check for emergency conditions that require immediate action."""
        emergencies = []
        
        # Battery emergencies
        battery = getattr(vehicle, "battery", None)
        if battery:
            level = getattr(battery, "level", 0) or 0
            voltage = getattr(battery, "voltage", 0) or 0
            
            if level <= 10:  
                emergencies.append(f"CRITICAL_BATTERY_LEVEL_{level}%")
            elif level <= 20: 
                emergencies.append(f"LOW_BATTERY_LEVEL_{level}%")
            
            min_voltage = BatterySafetyConfig.get_min_voltage_for_cell_count(voltage)
            if voltage < min_voltage * 0.9:  # 90% of minimum voltage
                emergencies.append(f"CRITICAL_BATTERY_VOLTAGE_{voltage:.1f}V")
        
        # GPS emergencies
        gps = getattr(vehicle, "gps_0", None)
        if gps:
            fix = getattr(gps, "fix_type", 0) or 0
            satellites = getattr(gps, "satellites_visible", 0) or 0
            
            if fix < 2:  # Lost GPS fix
                emergencies.append(f"GPS_FIX_LOST_{fix}")
            elif satellites < 6:  # Very low satellite count
                emergencies.append(f"GPS_SATELLITES_LOW_{satellites}")
        
        # Communication emergencies
        last_heartbeat = getattr(vehicle, "last_heartbeat", None)
        if last_heartbeat and last_heartbeat > 10.0:  # 10 seconds without heartbeat
            emergencies.append(f"COMMUNICATION_LOST_{last_heartbeat:.1f}s")
        
        return emergencies
    
    async def handle_emergency_landing(self, vehicle, reason: str) -> bool:
        """Execute emergency landing procedure."""
        self.flight_logger.log_event('emergency_landing_initiated', {'reason': reason})
        
        try:
            # Switch to LAND mode
            vehicle.mode = VehicleMode("LAND")
            
            # Wait for mode change
            timeout = time.time() + 10.0
            while str(vehicle.mode) != "LAND" and time.time() < timeout:
                await asyncio.sleep(0.1)
            
            if str(vehicle.mode) == "LAND":
                self.flight_logger.log_event('emergency_landing_success', {'mode': str(vehicle.mode)})
                return True
            else:
                self.flight_logger.log_event('emergency_landing_failed', {'mode': str(vehicle.mode)})
                return False
                
        except Exception as e:
            self.flight_logger.log_event('emergency_landing_error', {'error': str(e)})
            return False
    
    async def handle_emergency_rtl(self, vehicle, reason: str) -> bool:
        """Execute return-to-launch procedure."""
        self.flight_logger.log_event('emergency_rtl_initiated', {'reason': reason})
        
        try:
            # Switch to RTL mode
            vehicle.mode = VehicleMode("RTL")
            
            # Wait for mode change
            timeout = time.time() + 10.0
            while str(vehicle.mode) != "RTL" and time.time() < timeout:
                await asyncio.sleep(0.1)
            
            if str(vehicle.mode) == "RTL":
                self.flight_logger.log_event('emergency_rtl_success', {'mode': str(vehicle.mode)})
                return True
            else:
                self.flight_logger.log_event('emergency_rtl_failed', {'mode': str(vehicle.mode)})
                return False
                
        except Exception as e:
            self.flight_logger.log_event('emergency_rtl_error', {'error': str(e)})
            return False
    
    def validate_takeoff_conditions(self, vehicle) -> Tuple[bool, List[str]]:
        """Comprehensive pre-takeoff safety validation."""
        issues = []
        
        # Basic vehicle readiness
        if not self.validate_vehicle_ready(vehicle, require_armable=True):
            issues.append("Vehicle not ready for flight")
        
        # Check armed status
        if not getattr(vehicle, "armed", False):
            issues.append("Vehicle not armed")
        
        # Check mode
        mode = str(getattr(vehicle, "mode", "UNKNOWN"))
        if mode not in ["GUIDED", "AUTO", "STABILIZE"]:
            issues.append(f"Unsafe mode for takeoff: {mode}")
        
        # Check home location set
        home = getattr(vehicle, "home_location", None)
        if not home:
            issues.append("Home location not set")
        
        # Check EKF status (if available)
        ekf = getattr(vehicle, "ekf_ok", None)
        if ekf is not None and not ekf:
            issues.append("EKF not ready")
        
        return len(issues) == 0, issues
    
    def generate_safety_report(self, vehicle) -> Dict[str, Any]:
        """Generate comprehensive safety status report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'vehicle_ready': False,
            'battery': {},
            'gps': {},
            'communication': {},
            'emergencies': [],
            'recommendations': []
        }
        
        # Vehicle readiness
        report['vehicle_ready'] = self.validate_vehicle_ready(vehicle, require_armable=False, 
                                                             emergency_override=True)
        
        # Battery status
        battery = getattr(vehicle, "battery", None)
        if battery:
            # Include raw battery object for diagnostics
            try:
                level = getattr(battery, "level", None)
                voltage = getattr(battery, "voltage", None)
                current = getattr(battery, "current", None)
            except Exception:
                level = None
                voltage = None
                current = None

            # Determine status more permissively when telemetry is missing
            if (level is None or (isinstance(level, (int, float)) and float(level) <= 0)) and \
               (voltage is None or (isinstance(voltage, (int, float)) and float(voltage) <= 0)):
                status = 'UNKNOWN'
            else:
                level_val = (int(level) if level is not None else 0)
                if level_val > 50:
                    status = 'GOOD'
                elif level_val > 20:
                    status = 'LOW'
                else:
                    status = 'CRITICAL'

            report['battery'] = {
                'level_percent': level,
                'voltage': voltage,
                'current': current,
                'min_voltage': BatterySafetyConfig.get_min_voltage_for_cell_count(voltage or 0),
                'status': status,
                'raw': repr(battery)
            }

            # If telemetry missing, add recommendation to check power module / telemetry wiring
            if report['battery']['status'] == 'UNKNOWN':
                report.setdefault('recommendations', [])
                report['recommendations'].append(
                    'Battery telemetry missing (voltage/level=0 or null). Check power module, telemetry wiring, and FC parameter BATT_MONITOR/BATT_CAPACITY.'
                )
                # Attempt to include parameter diagnostics if available
                try:
                    params = {}
                    if hasattr(vehicle, 'parameters'):
                        for p in ('BATT_MONITOR', 'BATT_CAPACITY', 'BATT_ARM_VOLTAGE'):
                            try:
                                val = vehicle.parameters.get(p, None)
                                params[p] = val
                            except Exception:
                                params[p] = None
                    if params:
                        report['battery']['params'] = params
                except Exception:
                    pass
        
        # GPS status
        gps = getattr(vehicle, "gps_0", None)
        if gps:
            fix = getattr(gps, "fix_type", 0) or 0
            satellites = getattr(gps, "satellites_visible", 0) or 0
            report['gps'] = {
                'fix_type': fix,
                'satellites': satellites,
                'status': 'GOOD' if fix >= 3 and satellites >= 8 else 'POOR'
            }
        
        # Communication status
        last_heartbeat = getattr(vehicle, "last_heartbeat", None)
        report['communication'] = {
            'last_heartbeat_s': last_heartbeat,
            'status': 'GOOD' if (last_heartbeat or 0) < 2.0 else 'POOR'
        }
        
        # Emergency conditions
        report['emergencies'] = self.check_emergency_conditions(vehicle)
        
        # Generate recommendations
        if report['battery'].get('level_percent', 0) < 30:
            report['recommendations'].append("Consider landing soon - low battery")
        
        if report['gps'].get('satellites', 0) < 6:
            report['recommendations'].append("Wait for better GPS before flying")
        
        if len(report['emergencies']) > 0:
            report['recommendations'].append("Address emergency conditions before flight")
        
        return report
    
    # =============================================================================
    # ESSENTIAL EDGE CASE HANDLING
    # =============================================================================
    
    def detect_critical_anomalies(self, vehicle) -> List[Dict[str, Any]]:
        """Detect critical flight anomalies that need immediate attention."""
        anomalies = []
        
        try:
            # Check for rapid altitude changes
            if hasattr(vehicle, 'location') and vehicle.location.global_frame:
                current_alt = vehicle.location.global_frame.alt
                if hasattr(self, 'last_altitude') and self.last_altitude:
                    alt_change = abs(current_alt - self.last_altitude)
                    if alt_change > 10:  # >10m sudden change
                        anomalies.append({
                            'type': 'rapid_altitude_change',
                            'change': alt_change,
                            'severity': 'critical'
                        })
                        self.logger.error(f"Rapid altitude change detected: {alt_change}m")
                
                self.last_altitude = current_alt
            
            # Check for GPS jumps
            if hasattr(vehicle, 'location') and vehicle.location.global_frame:
                current_pos = (vehicle.location.global_frame.lat, vehicle.location.global_frame.lon)
                if hasattr(self, 'last_position') and self.last_position:
                    distance = self._calculate_distance(self.last_position, current_pos)
                    if distance > 100:  # >100m sudden jump
                        anomalies.append({
                            'type': 'position_jump',
                            'distance': distance,
                            'severity': 'critical'
                        })
                        self.logger.error(f"GPS position jump detected: {distance}m")
                
                self.last_position = current_pos
            
            # Check for voltage drops
            if hasattr(vehicle, 'battery'):
                voltage = getattr(vehicle.battery, 'voltage', None)
                if voltage and hasattr(self, 'last_voltage') and self.last_voltage:
                    voltage_drop = self.last_voltage - voltage
                    if voltage_drop > 2.0:  # >2V sudden drop
                        anomalies.append({
                            'type': 'voltage_drop',
                            'drop': voltage_drop,
                            'severity': 'critical'
                        })
                        self.logger.critical(f"Critical voltage drop: {voltage_drop}V")
                
                if voltage:
                    self.last_voltage = voltage
        
        except Exception as e:
            self.logger.error(f"Anomaly detection error: {e}")
        
        return anomalies
    
    def _calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate distance between two GPS coordinates using Haversine formula."""
        try:
            lat1, lon1 = pos1
            lat2, lon2 = pos2
            
            R = 6371000  # Earth's radius in meters
            
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            delta_lat = math.radians(lat2 - lat1)
            delta_lon = math.radians(lon2 - lon1)
            
            a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) + 
                 math.cos(lat1_rad) * math.cos(lat2_rad) * 
                 math.sin(delta_lon/2) * math.sin(delta_lon/2))
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            
            return R * c
        except:
            return 0.0
    
    def monitor_connection_health(self, vehicle) -> float:
        """Monitor connection health and return quality score (0.0-1.0)."""
        if not vehicle:
            return 0.0
        
        quality_score = 1.0
        
        # Check heartbeat
        heartbeat = getattr(vehicle, 'last_heartbeat', None)
        if heartbeat:
            if heartbeat > 5.0:
                quality_score = 0.1  # Very poor
                self.logger.warning(f"Poor connection: {heartbeat}s heartbeat")
            elif heartbeat > 3.0:
                quality_score = 0.5  # Poor
            elif heartbeat > 1.0:
                quality_score = 0.8  # Fair
        
        return quality_score
    
    def validate_environmental_conditions(self, vehicle) -> Tuple[bool, List[str]]:
        """Validate environmental flight conditions."""
        issues = []
        
        try:
            # Check wind conditions (if available)
            wind_speed = getattr(vehicle, 'wind_speed', None)
            if wind_speed and wind_speed > self.wind_speed_limit:
                issues.append(f"Wind speed too high: {wind_speed:.1f} m/s (limit: {self.wind_speed_limit} m/s)")
                self.logger.warning(f"High wind speed detected: {wind_speed:.1f} m/s")
            
            # Check temperature extremes (if available)
            temperature = getattr(vehicle, 'temperature', None)
            if temperature:
                if temperature < -20 or temperature > 60:  # Celsius
                    issues.append(f"Temperature extreme: {temperature}°C")
                    self.logger.warning(f"Extreme temperature: {temperature}°C")
            
            # Check pressure altitude consistency
            pressure_alt = getattr(vehicle, 'pressure_alt', None)
            gps_alt = getattr(vehicle.location.global_frame, 'alt', None) if hasattr(vehicle, 'location') else None
            
            if pressure_alt and gps_alt and abs(pressure_alt - gps_alt) > 50:
                issues.append(f"Altitude mismatch: Pressure={pressure_alt}m, GPS={gps_alt}m")
                self.logger.warning(f"Altitude sensor mismatch detected")
            
        except Exception as e:
            self.logger.error(f"Environmental validation error: {e}")
            issues.append("Environmental sensor error")
        
        return len(issues) == 0, issues
    
    def validate_flight_envelope(self, vehicle, target_altitude: float = None, 
                               target_speed: float = None) -> Tuple[bool, List[str]]:
        """Validate flight is within safe envelope parameters."""
        issues = []
        
        try:
            # Check altitude limits
            if target_altitude:
                if target_altitude > FlightSafetyConfig.MAX_ALTITUDE:
                    issues.append(f"Target altitude too high: {target_altitude}m (max: {FlightSafetyConfig.MAX_ALTITUDE}m)")
                if target_altitude < FlightSafetyConfig.MIN_ALTITUDE:
                    issues.append(f"Target altitude too low: {target_altitude}m (min: {FlightSafetyConfig.MIN_ALTITUDE}m)")
            
            # Check speed limits
            if target_speed:
                max_speed = getattr(FlightSafetyConfig, 'MAX_HORIZONTAL_SPEED', 20.0)  # m/s default
                if target_speed > max_speed:
                    issues.append(f"Target speed too high: {target_speed:.1f}m/s (max: {max_speed}m/s)")
            
            # Check current flight parameters
            if hasattr(vehicle, 'airspeed') and vehicle.airspeed:
                if vehicle.airspeed > 25.0:  # 25 m/s = ~90 km/h
                    issues.append(f"Current airspeed excessive: {vehicle.airspeed:.1f}m/s")
            
            # Check attitude limits
            if hasattr(vehicle, 'attitude'):
                attitude = vehicle.attitude
                max_roll = 45.0  # degrees
                max_pitch = 45.0  # degrees
                
                if abs(attitude.roll) > max_roll:
                    issues.append(f"Roll angle excessive: {attitude.roll:.1f}° (limit: ±{max_roll}°)")
                if abs(attitude.pitch) > max_pitch:
                    issues.append(f"Pitch angle excessive: {attitude.pitch:.1f}° (limit: ±{max_pitch}°)")
        
        except Exception as e:
            self.logger.error(f"Flight envelope validation error: {e}")
            issues.append("Flight envelope check error")
        
        return len(issues) == 0, issues
    
    def handle_gps_degradation(self, vehicle) -> Dict[str, Any]:
        """Handle GPS signal degradation scenarios."""
        try:
            gps = getattr(vehicle, 'gps_0', None)
            if not gps:
                self.logger.critical("Complete GPS failure detected")
                self.drone_logger.log_emergency("GPS_FAILURE", {"type": "complete_loss"})
                return {"action": "emergency_land", "reason": "GPS complete failure"}
            
            satellites = getattr(gps, 'satellites_visible', 0)
            eph = getattr(gps, 'eph', 999)
            fix_type = getattr(gps, 'fix_type', 0)
            
            # Critical GPS degradation
            if fix_type < 2 or satellites < 6:
                self.logger.critical(f"Critical GPS degradation: fix_type={fix_type}, satellites={satellites}")
                self.drone_logger.log_emergency("GPS_DEGRADATION", {
                    "fix_type": fix_type,
                    "satellites": satellites,
                    "hdop": eph
                })
                return {"action": "immediate_rtl", "reason": "GPS critical degradation"}
            
            # Moderate GPS issues
            if satellites < 6 or eph > 200:
                self.logger.warning(f"GPS degradation: satellites={satellites}, HDOP={eph}")
                return {"action": "reduce_speed", "reason": "GPS degraded accuracy"}
            
            return {"action": "continue", "reason": "GPS acceptable"}
            
        except Exception as e:
            self.logger.error(f"GPS degradation handler error: {e}")
            return {"action": "emergency_land", "reason": "GPS handler failure"}
    
    def handle_sensor_failure(self, vehicle, sensor_type: str) -> Dict[str, Any]:
        """Handle specific sensor failure scenarios."""
        try:
            self.logger.critical(f"Sensor failure detected: {sensor_type}")
            
            failure_handlers = {
                'compass': self._handle_compass_failure,
                'accelerometer': self._handle_accelerometer_failure,
                'barometer': self._handle_barometer_failure,
                'gyroscope': self._handle_gyroscope_failure
            }
            
            if sensor_type in failure_handlers:
                return failure_handlers[sensor_type](vehicle)
            else:
                self.logger.error(f"Unknown sensor type: {sensor_type}")
                return {"action": "emergency_land", "reason": f"Unknown sensor failure: {sensor_type}"}
        
        except Exception as e:
            self.logger.error(f"Sensor failure handler error: {e}")
            return {"action": "emergency_land", "reason": "Sensor failure handler error"}
    
    def _handle_compass_failure(self, vehicle) -> Dict[str, Any]:
        """Handle compass/magnetometer failure."""
        self.drone_logger.log_emergency("COMPASS_FAILURE", {"timestamp": datetime.now().isoformat()})
        
        # Check if we have GPS heading as backup
        gps = getattr(vehicle, 'gps_0', None)
        if gps and getattr(gps, 'fix_type', 0) >= 3:
            self.logger.warning("Compass failed - using GPS heading backup")
            return {"action": "gps_heading_mode", "reason": "Compass failure - GPS backup active"}
        else:
            self.logger.critical("Compass failed and no GPS backup available")
            return {"action": "emergency_land", "reason": "Compass failure - no backup heading"}
    
    def _handle_accelerometer_failure(self, vehicle) -> Dict[str, Any]:
        """Handle accelerometer failure."""
        self.drone_logger.log_emergency("ACCELEROMETER_FAILURE", {"timestamp": datetime.now().isoformat()})
        return {"action": "gentle_rtl", "reason": "Accelerometer failure - reduced maneuvering"}
    
    def _handle_barometer_failure(self, vehicle) -> Dict[str, Any]:
        """Handle barometer failure."""
        self.drone_logger.log_emergency("BAROMETER_FAILURE", {"timestamp": datetime.now().isoformat()})
        
        # Check if GPS altitude is available
        gps_alt = getattr(vehicle.location.global_frame, 'alt', None) if hasattr(vehicle, 'location') else None
        if gps_alt:
            self.logger.warning("Barometer failed - using GPS altitude")
            return {"action": "gps_altitude_mode", "reason": "Barometer failure - GPS altitude backup"}
        else:
            return {"action": "emergency_land", "reason": "Barometer failure - no altitude reference"}
    
    def _handle_gyroscope_failure(self, vehicle) -> Dict[str, Any]:
        """Handle gyroscope failure."""
        self.drone_logger.log_emergency("GYROSCOPE_FAILURE", {"timestamp": datetime.now().isoformat()})
        return {"action": "emergency_land", "reason": "Gyroscope failure - critical for stability"}
    
    def assess_emergency_landing_feasibility(self, vehicle, target_location=None) -> Dict[str, Any]:
        """Assess if emergency landing is feasible at current or target location."""
        try:
            current_alt = getattr(vehicle.location.global_frame, 'alt', 0) if hasattr(vehicle, 'location') else 0
            
            # Check altitude for safe landing
            if current_alt < 5:
                return {"feasible": False, "reason": "Already too low for safe landing approach"}
            
            # Check battery for landing procedure
            battery = getattr(vehicle, 'battery', None)
            battery_level = getattr(battery, 'level', 0) if battery else 0
            
            if battery_level < 5:
                return {"feasible": False, "reason": "Insufficient battery for controlled landing"}
            
            # Check GPS for position reference
            gps = getattr(vehicle, 'gps_0', None)
            if gps and getattr(gps, 'fix_type', 0) < 2:
                return {"feasible": False, "reason": "Insufficient GPS for position hold during landing"}
            
            # Estimate landing time requirement
            descent_rate = 2.0  # m/s safe descent rate
            landing_time = current_alt / descent_rate
            
            return {
                "feasible": True,
                "estimated_time": landing_time,
                "altitude": current_alt,
                "battery_level": battery_level,
                "gps_fix": getattr(gps, 'fix_type', 0) if gps else 0
            }
            
        except Exception as e:
            self.logger.error(f"Landing feasibility assessment error: {e}")
            return {"feasible": False, "reason": f"Assessment error: {e}"}
    
    def calculate_emergency_return_feasibility(self, vehicle, home_location) -> Dict[str, Any]:
        """Calculate if emergency return to home is feasible."""
        try:
            if not home_location:
                return {"feasible": False, "reason": "No home location set"}
            
            # Get current position
            current_location = getattr(vehicle.location, 'global_frame', None) if hasattr(vehicle, 'location') else None
            if not current_location:
                return {"feasible": False, "reason": "No current position available"}
            
            # Calculate distance to home
            from ..navigation.navigation_utils import NavigationUtils
            nav_utils = NavigationUtils()
            
            distance = nav_utils.calculate_distance(
                (current_location.lat, current_location.lon),
                (home_location.lat, home_location.lon)
            )
            
            # Estimate flight time (assuming 10 m/s average speed)
            flight_time = distance / 10.0  # seconds
            
            # Check battery capacity
            battery = getattr(vehicle, 'battery', None)
            battery_level = getattr(battery, 'level', 0) if battery else 0
            
            # Conservative estimate: need 2% battery per minute of flight
            required_battery = (flight_time / 60.0) * 2.0
            
            if battery_level < required_battery + 10:  # 10% safety margin
                return {
                    "feasible": False,
                    "reason": f"Insufficient battery: need {required_battery:.1f}%, have {battery_level}%",
                    "distance": distance,
                    "flight_time": flight_time
                }
            
            return {
                "feasible": True,
                "distance": distance,
                "flight_time": flight_time,
                "battery_required": required_battery,
                "battery_available": battery_level
            }
            
        except Exception as e:
            self.logger.error(f"RTL feasibility calculation error: {e}")
            return {"feasible": False, "reason": f"Calculation error: {e}"}