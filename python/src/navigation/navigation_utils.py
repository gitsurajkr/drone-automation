"""
Navigation Utilities
===================

Centralized navigation calculations and GPS utilities for drone operations.
This module contains all geographic calculations, distance measurements, and
waypoint validation functions to eliminate code duplication.
"""

import math
from typing import List, Tuple, Dict, Any, Optional


class NavigationUtils:
    """Centralized navigation and GPS calculation utilities."""
    
    # Earth radius in meters (WGS84 approximation)
    EARTH_RADIUS_M = 6371000.0
    
    # Coordinate validation ranges
    VALID_LAT_RANGE = (-90.0, 90.0)
    VALID_LON_RANGE = (-180.0, 180.0)
    MAX_REALISTIC_DISTANCE = 20003931.0  # Half Earth's circumference
    
    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> Tuple[bool, str]:
        """Validate GPS coordinates are within valid ranges."""
        try:
            lat = float(lat)
            lon = float(lon)
            
            if not (NavigationUtils.VALID_LAT_RANGE[0] <= lat <= NavigationUtils.VALID_LAT_RANGE[1]):
                return False, f"Invalid latitude: {lat} (must be -90 to 90)"
                
            if not (NavigationUtils.VALID_LON_RANGE[0] <= lon <= NavigationUtils.VALID_LON_RANGE[1]):
                return False, f"Invalid longitude: {lon} (must be -180 to 180)"
                
            return True, "Valid coordinates"
            
        except (ValueError, TypeError) as e:
            return False, f"Invalid coordinate format: {e}"
    
    @staticmethod
    def calculate_distance(wp1: Tuple[float, float], wp2: Tuple[float, float]) -> float:
        """
        Calculate distance between two GPS coordinates using Haversine formula.
        
        Args:
            wp1: First coordinate (lat, lon)
            wp2: Second coordinate (lat, lon)
            
        Returns:
            Distance in meters, or float('inf') if calculation fails
        """
        if not wp1 or not wp2 or len(wp1) < 2 or len(wp2) < 2:
            return float('inf')
        
        try:
            lat1, lon1 = float(wp1[0]), float(wp1[1])
            lat2, lon2 = float(wp2[0]), float(wp2[1])
            
            # Validate coordinates
            valid1, _ = NavigationUtils.validate_coordinates(lat1, lon1)
            valid2, _ = NavigationUtils.validate_coordinates(lat2, lon2)
            
            if not valid1 or not valid2:
                return float('inf')
            
            # Handle identical coordinates
            if lat1 == lat2 and lon1 == lon2:
                return 0.0
            
            # Haversine formula
            lat1_rad = math.radians(lat1)
            lat2_rad = math.radians(lat2)
            delta_lat = math.radians(lat2 - lat1)
            delta_lon = math.radians(lon2 - lon1)
            
            a = (math.sin(delta_lat/2)**2 + 
                 math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2)
            
            # Handle numerical errors
            if a > 1.0:
                a = 1.0
            
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            distance = NavigationUtils.EARTH_RADIUS_M * c
            
            # Sanity check
            if distance < 0 or distance > NavigationUtils.MAX_REALISTIC_DISTANCE:
                return float('inf')
            
            return distance
            
        except (ValueError, TypeError, ZeroDivisionError):
            return float('inf')
    
    @staticmethod
    def calculate_bearing(wp1: Tuple[float, float], wp2: Tuple[float, float]) -> Optional[float]:
        """
        Calculate bearing from wp1 to wp2 in degrees (0-360).
        
        Args:
            wp1: Start coordinate (lat, lon)
            wp2: End coordinate (lat, lon)
            
        Returns:
            Bearing in degrees (0=North, 90=East), or None if calculation fails
        """
        if not wp1 or not wp2 or len(wp1) < 2 or len(wp2) < 2:
            return None
            
        try:
            lat1, lon1 = math.radians(float(wp1[0])), math.radians(float(wp1[1]))
            lat2, lon2 = math.radians(float(wp2[0])), math.radians(float(wp2[1]))
            
            delta_lon = lon2 - lon1
            
            y = math.sin(delta_lon) * math.cos(lat2)
            x = (math.cos(lat1) * math.sin(lat2) - 
                 math.sin(lat1) * math.cos(lat2) * math.cos(delta_lon))
            
            bearing_rad = math.atan2(y, x)
            bearing_deg = math.degrees(bearing_rad)
            
            # Convert to 0-360 degrees
            return (bearing_deg + 360) % 360
            
        except (ValueError, TypeError, ZeroDivisionError):
            return None
    
    @staticmethod
    def calculate_midpoint(wp1: Tuple[float, float], wp2: Tuple[float, float]) -> Optional[Tuple[float, float]]:
        """Calculate midpoint between two GPS coordinates."""
        if not wp1 or not wp2 or len(wp1) < 2 or len(wp2) < 2:
            return None
            
        try:
            lat1, lon1 = math.radians(float(wp1[0])), math.radians(float(wp1[1]))
            lat2, lon2 = math.radians(float(wp2[0])), math.radians(float(wp2[1]))
            
            delta_lon = lon2 - lon1
            
            Bx = math.cos(lat2) * math.cos(delta_lon)
            By = math.cos(lat2) * math.sin(delta_lon)
            
            lat_mid = math.atan2(math.sin(lat1) + math.sin(lat2),
                                math.sqrt((math.cos(lat1) + Bx) * (math.cos(lat1) + Bx) + By * By))
            lon_mid = lon1 + math.atan2(By, math.cos(lat1) + Bx)
            
            return (math.degrees(lat_mid), math.degrees(lon_mid))
            
        except (ValueError, TypeError, ZeroDivisionError):
            return None


class WaypointValidator:
    """Waypoint validation and processing utilities."""
    
    @staticmethod
    def validate_altitude(altitude: float, min_alt: float = 0.5, max_alt: float = 100.0) -> Tuple[bool, str]:
        """Validate altitude is within safe ranges."""
        try:
            alt = float(altitude)
            if min_alt <= alt <= max_alt:
                return True, "Valid altitude"
            else:
                return False, f"Altitude {alt}m outside range {min_alt}-{max_alt}m"
        except (ValueError, TypeError):
            return False, "Invalid altitude format"
    
    @staticmethod
    def validate_waypoint(waypoint: Tuple[float, float, float]) -> Tuple[bool, str]:
        """Validate a single waypoint (lat, lon, alt)."""
        if not waypoint or len(waypoint) < 3:
            return False, "Invalid waypoint format - needs (lat, lon, alt)"
        
        lat, lon, alt = waypoint[:3]
        
        # Validate coordinates
        coord_valid, coord_msg = NavigationUtils.validate_coordinates(lat, lon)
        if not coord_valid:
            return False, coord_msg
        
        # Validate altitude
        alt_valid, alt_msg = WaypointValidator.validate_altitude(alt)
        if not alt_valid:
            return False, alt_msg
        
        return True, "Valid waypoint"
    
    @staticmethod
    def validate_waypoint_list(waypoints: List[Tuple[float, float, float]]) -> Tuple[bool, List[str]]:
        """Validate a list of waypoints."""
        if not waypoints:
            return False, ["No waypoints provided"]
        
        if len(waypoints) > 50:  # Reasonable limit
            return False, [f"Too many waypoints: {len(waypoints)} (max 50)"]
        
        issues = []
        
        for i, wp in enumerate(waypoints):
            valid, msg = WaypointValidator.validate_waypoint(wp)
            if not valid:
                issues.append(f"Waypoint {i+1}: {msg}")
        
        # Check for duplicate waypoints
        for i in range(len(waypoints)):
            for j in range(i+1, len(waypoints)):
                distance = NavigationUtils.calculate_distance(waypoints[i][:2], waypoints[j][:2])
                if distance < 1.0:  # Less than 1 meter apart
                    issues.append(f"Waypoints {i+1} and {j+1} are too close ({distance:.2f}m)")
        
        return len(issues) == 0, issues
    
    @staticmethod
    def process_waypoints(waypoints: List[Tuple[float, float, float]]) -> Tuple[List[Tuple[float, float, float]], List[str]]:
        """Process and clean waypoint list."""
        if not waypoints:
            return [], ["No waypoints to process"]
        
        processed = []
        warnings = []
        
        for i, wp in enumerate(waypoints):
            if len(wp) >= 3:
                try:
                    lat = float(wp[0])
                    lon = float(wp[1]) 
                    alt = float(wp[2])
                    
                    # Round to reasonable precision (6 decimal places ~0.1m accuracy)
                    lat = round(lat, 6)
                    lon = round(lon, 6)
                    alt = round(alt, 1)
                    
                    processed.append((lat, lon, alt))
                    
                except (ValueError, TypeError):
                    warnings.append(f"Skipped invalid waypoint {i+1}: {wp}")
            else:
                warnings.append(f"Skipped incomplete waypoint {i+1}: {wp}")
        
        return processed, warnings


class MissionCalculator:
    """Mission statistics and planning calculations."""
    
    @staticmethod
    def calculate_total_distance(waypoints: List[Tuple[float, float, float]]) -> float:
        """Calculate total mission distance."""
        if len(waypoints) < 2:
            return 0.0
        
        total = 0.0
        for i in range(len(waypoints) - 1):
            distance = NavigationUtils.calculate_distance(waypoints[i][:2], waypoints[i+1][:2])
            if distance != float('inf'):
                total += distance
        
        return total
    
    @staticmethod
    def estimate_flight_time(waypoints: List[Tuple[float, float, float]], 
                           speed_ms: float = 5.0) -> float:
        """Estimate mission flight time in seconds."""
        distance = MissionCalculator.calculate_total_distance(waypoints)
        if distance == 0:
            return 0.0
        
        # Add time for altitude changes (assume 2 m/s climb rate)
        altitude_changes = 0.0
        for i in range(len(waypoints) - 1):
            alt_diff = abs(waypoints[i+1][2] - waypoints[i][2])
            altitude_changes += alt_diff / 2.0  # 2 m/s climb rate
        
        travel_time = distance / speed_ms
        total_time = travel_time + altitude_changes
        
        return total_time
    
    @staticmethod
    def get_altitude_range(waypoints: List[Tuple[float, float, float]]) -> Tuple[float, float]:
        """Get minimum and maximum altitudes in mission."""
        if not waypoints:
            return (0.0, 0.0)
        
        altitudes = [wp[2] for wp in waypoints]
        return (min(altitudes), max(altitudes))
    
    @staticmethod
    def get_bounding_box(waypoints: List[Tuple[float, float, float]]) -> Optional[Dict[str, float]]:
        """Get geographic bounding box of mission."""
        if not waypoints:
            return None
        
        lats = [wp[0] for wp in waypoints]
        lons = [wp[1] for wp in waypoints]
        
        return {
            'min_lat': min(lats),
            'max_lat': max(lats),
            'min_lon': min(lons),
            'max_lon': max(lons),
            'center_lat': (min(lats) + max(lats)) / 2,
            'center_lon': (min(lons) + max(lons)) / 2
        }
    
    @staticmethod
    def calculate_mission_stats(waypoints: List[Tuple[float, float, float]]) -> Dict[str, Any]:
        """Calculate comprehensive mission statistics."""
        return {
            "total_waypoints": len(waypoints),
            "total_distance_m": MissionCalculator.calculate_total_distance(waypoints),
            "estimated_flight_time_s": MissionCalculator.estimate_flight_time(waypoints),
            "altitude_range_m": MissionCalculator.get_altitude_range(waypoints),
            "bounding_box": MissionCalculator.get_bounding_box(waypoints),
            "is_valid": len(WaypointValidator.validate_waypoint_list(waypoints)[1]) == 0
        }


# Convenience functions for backward compatibility
def calculate_distance(wp1: Tuple[float, float], wp2: Tuple[float, float]) -> float:
    """Calculate distance between two waypoints (backward compatibility)."""
    return NavigationUtils.calculate_distance(wp1, wp2)


def validate_waypoints(waypoints: List[Tuple[float, float, float]]) -> Tuple[bool, List[str]]:
    """Validate waypoint list (backward compatibility)."""
    return WaypointValidator.validate_waypoint_list(waypoints)


def process_waypoints(waypoints: List[Tuple[float, float, float]]) -> Tuple[List[Tuple[float, float, float]], List[str]]:
    """Process waypoint list (backward compatibility)."""
    return WaypointValidator.process_waypoints(waypoints)