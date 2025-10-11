"""
Waypoint Mission Manager
=======================

Dedicated waypoint mission execution and management for autonomous drone navigation.
This module handles waypoint mission planning, execution, monitoring, and emergency
handling during waypoint navigation.
"""

import asyncio
import time
from typing import List, Tuple, Dict, Any, Optional, Callable
from datetime import datetime
from dronekit import VehicleMode, LocationGlobalRelative
from config.config import WaypointConfig, FlightLogger
from .navigation_utils import NavigationUtils, WaypointValidator, MissionCalculator
from ..safety.flight_safety import FlightSafetyManager


class WaypointMission:
    """Represents a waypoint mission with metadata."""
    
    def __init__(self, waypoints: List[Tuple[float, float, float]], mission_id: str = None):
        self.mission_id = mission_id or f"mission_{int(time.time())}"
        self.waypoints = waypoints
        self.created_at = datetime.now()
        self.status = "CREATED"  # CREATED, VALIDATED, ACTIVE, COMPLETED, ABORTED
        self.current_waypoint_index = 0
        self.stats = MissionCalculator.calculate_mission_stats(waypoints)
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert mission to dictionary representation."""
        return {
            'mission_id': self.mission_id,
            'waypoints': self.waypoints,
            'created_at': self.created_at.isoformat(),
            'status': self.status,
            'current_waypoint': self.current_waypoint_index,
            'stats': self.stats
        }


class WaypointMissionManager:
    """Manages waypoint mission execution and monitoring."""
    
    def __init__(self, connection):
        self.connection = connection
        self.safety_manager = FlightSafetyManager()
        self.flight_logger = FlightLogger()
        
        # Mission state
        self.current_mission: Optional[WaypointMission] = None
        self.mission_start_time: Optional[datetime] = None
        self.emergency_prompts = {}  # Track active emergency prompts
        
        # Mission settings
        self.waypoint_tolerance = 2.0  # meters
        self.max_waypoint_time = 120.0  # seconds per waypoint
        
    def _get_current_position_log(self) -> Dict[str, Any]:
        """Get detailed current position and status for logging."""
        try:
            vehicle = self.connection.vehicle
            location = vehicle.location.global_relative_frame
            return {
                'lat': getattr(location, 'lat', 0),
                'lon': getattr(location, 'lon', 0),
                'alt': getattr(location, 'alt', 0),
                'speed': getattr(vehicle, 'groundspeed', 0),
                'mode': getattr(vehicle.mode, 'name', 'UNKNOWN') if hasattr(vehicle, 'mode') else 'UNKNOWN',
                'armed': getattr(vehicle, 'armed', False),
                'battery': getattr(vehicle.battery, 'level', 0) if hasattr(vehicle, 'battery') else 0,
                'satellites': getattr(vehicle.gps_0, 'satellites_visible', 0) if hasattr(vehicle, 'gps_0') else 0,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'lat': 0, 'lon': 0, 'alt': 0, 'speed': 0, 'mode': 'ERROR', 
                'armed': False, 'battery': 0, 'satellites': 0,
                'error': str(e), 'timestamp': datetime.now().isoformat()
            }
        
    async def execute_mission(self, waypoints: List[Tuple[float, float, float]], 
                            takeoff_altitude: Optional[float] = None,
                            broadcast_func: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Execute a waypoint mission with full safety monitoring.
        
        Args:
            waypoints: List of (lat, lon, alt) waypoints
            broadcast_func: Optional function to broadcast updates
            
        Returns:
            Mission execution result dictionary
        """
        # Validate waypoints
        processed_waypoints, warnings = WaypointValidator.process_waypoints(waypoints)
        if not processed_waypoints:
            return {
                'success': False,
                'error': 'No valid waypoints to execute',
                'warnings': warnings
            }
        
        valid, issues = WaypointValidator.validate_waypoint_list(processed_waypoints)
        if not valid:
            return {
                'success': False,
                'error': 'Waypoint validation failed',
                'issues': issues
            }
        
        # Create mission
        mission = WaypointMission(processed_waypoints)
        self.current_mission = mission
        self.mission_start_time = datetime.now()
        
        self.flight_logger.log_event('mission_started', {
            'mission_id': mission.mission_id,
            'waypoint_count': len(processed_waypoints),
            'total_distance': mission.stats['total_distance_m'],
            'estimated_time': mission.stats['estimated_flight_time_s']
        })
        
        try:
            # Pre-flight safety check
            if not self.safety_manager.validate_vehicle_ready(self.connection):
                return {
                    'success': False,
                    'error': 'Vehicle not ready for mission',
                    'mission_id': mission.mission_id
                }

            # Battery and GPS validation checks
            vehicle = self.connection.vehicle
            try:
                battery_level = getattr(vehicle.battery, 'level', 0) if hasattr(vehicle, 'battery') and vehicle.battery else 0
                satellites = getattr(vehicle.gps_0, 'satellites_visible', 0) if hasattr(vehicle, 'gps_0') and vehicle.gps_0 else 0
                
                # Battery check - minimum 25%
                if battery_level < 25:
                    error_msg = f"❌ Battery too low: {battery_level}% - Cannot set waypoints (minimum 25% required)"
                    print(f"[MISSION] {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'mission_id': mission.mission_id,
                        'battery_level': battery_level
                    }
                
                # GPS check - minimum 6 satellites
                if satellites < 6:
                    error_msg = f"❌ GPS insufficient: {satellites} satellites - Cannot set waypoints (minimum 6 satellites required)"
                    print(f"[MISSION] {error_msg}")
                    return {
                        'success': False,
                        'error': error_msg,
                        'mission_id': mission.mission_id,
                        'satellites': satellites
                    }
                
                print(f"[MISSION] ✅ Pre-flight validation passed - Battery: {battery_level}%, GPS: {satellites} satellites")
                
            except Exception as e:
                error_msg = f"❌ Failed to check battery/GPS status: {str(e)}"
                print(f"[MISSION] {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'mission_id': mission.mission_id
                }

            # If a takeoff_altitude is provided and vehicle is not already armed/airborne,
            # perform an automatic arm-and-takeoff to the requested altitude.
            vehicle = self.connection.vehicle
            try:
                is_armed = getattr(vehicle, 'armed', False)
                current_alt = getattr(vehicle.location.global_relative_frame, 'alt', 0) if vehicle.location and getattr(vehicle, 'location', None) else 0
            except Exception:
                is_armed = False
                current_alt = 0

            if takeoff_altitude is not None:
                # Only attempt arm-and-takeoff if vehicle is not already armed or not above a small altitude
                if not is_armed or current_alt < 1.5:
                    # Use controller's arm_and_takeoff if available on connection.controller
                    controller = getattr(self.connection, 'controller', None)
                    if controller and hasattr(controller, 'arm_and_takeoff'):
                        self.flight_logger.log_event('auto_takeoff_initiated', {'altitude': takeoff_altitude, 'mission_id': mission.mission_id})
                        # Broadcast takeoff started
                        if broadcast_func:
                            await broadcast_func({'type': 'takeoff_progress', 'status': 'started', 'target_altitude': takeoff_altitude, 'mission_id': mission.mission_id})

                        # Await controller arm and takeoff while sending periodic progress updates
                        async def _progress_cb(current_alt, target_alt):
                            try:
                                if broadcast_func:
                                    percent = min(100, int((current_alt / target_alt) * 100)) if target_alt and target_alt > 0 else 0
                                    await broadcast_func({
                                        'type': 'takeoff_progress',
                                        'status': 'progress',
                                        'current_altitude': current_alt,
                                        'target_altitude': target_alt,
                                        'percent': percent,
                                        'mission_id': mission.mission_id
                                    })
                            except Exception as e:
                                # Don't fail takeoff due to progress broadcast issues
                                print(f"[WAYPOINT_MANAGER] Takeoff progress broadcast error: {e}")

                        ok = await controller.arm_and_takeoff(takeoff_altitude, progress_callback=_progress_cb)

                        # Broadcast completion or failure
                        if ok:
                            if broadcast_func:
                                await broadcast_func({'type': 'takeoff_progress', 'status': 'completed', 'target_altitude': takeoff_altitude, 'mission_id': mission.mission_id})
                        else:
                            if broadcast_func:
                                await broadcast_func({'type': 'takeoff_progress', 'status': 'failed', 'target_altitude': takeoff_altitude, 'mission_id': mission.mission_id})
                            return {
                                'success': False,
                                'error': 'Auto takeoff failed',
                                'mission_id': mission.mission_id
                            }
                    else:
                        try:
                            vehicle.simple_takeoff(takeoff_altitude)
                            # Wait until altitude reached or timeout
                            start = time.time()
                            timeout = 30
                            while True:
                                alt = getattr(vehicle.location.global_relative_frame, 'alt', 0)
                                if alt >= takeoff_altitude * 0.95:
                                    break
                                if time.time() - start > timeout:
                                    return {
                                        'success': False,
                                        'error': 'Auto takeoff timeout',
                                        'mission_id': mission.mission_id
                                    }
                                await asyncio.sleep(0.5)
                        except Exception as e:
                            return {
                                'success': False,
                                'error': f'Auto takeoff failed: {e}',
                                'mission_id': mission.mission_id
                            }
            
            # Execute waypoints
            mission.status = "ACTIVE"
            # print(f"[MISSION] Starting waypoint navigation - {len(processed_waypoints)} waypoints total")
            self.flight_logger.log_event('waypoint_navigation_started', {
                'mission_id': mission.mission_id,
                'total_waypoints': len(processed_waypoints),
                'initial_position': self._get_current_position_log()
            })
            
            for i, waypoint in enumerate(processed_waypoints):
                mission.current_waypoint_index = i
                lat, lon, alt = waypoint
                
                # Log detailed waypoint start info
                current_pos = self._get_current_position_log()
                distance_to_wp = NavigationUtils.calculate_distance(
                    (current_pos['lat'], current_pos['lon']), (lat, lon)
                ) if current_pos['lat'] != 0 else 0
                
                print(f"[MISSION] ═══ WAYPOINT {i+1}/{len(processed_waypoints)} ═══")
                print(f"[MISSION] Current Position: {current_pos['lat']:.6f}, {current_pos['lon']:.6f}")
                print(f"[MISSION] Current Altitude: {current_pos['alt']:.1f}m")
                print(f"[MISSION] Target Position: {lat:.6f}, {lon:.6f}")
                print(f"[MISSION] Target Altitude: {alt:.1f}m")
                print(f"[MISSION] Distance to Waypoint: {distance_to_wp:.1f}m")
                print(f"[MISSION] Drone Speed: {current_pos['speed']:.1f}m/s")
                print(f"[MISSION] Drone Mode: {current_pos['mode']}")
                
                self.flight_logger.log_event('waypoint_navigation_start', {
                    'mission_id': mission.mission_id,
                    'waypoint_number': i + 1,
                    'total_waypoints': len(processed_waypoints),
                    'target_coordinates': {'lat': lat, 'lon': lon, 'alt': alt},
                    'current_position': current_pos,
                    'distance_to_target': distance_to_wp
                })
                
                # Broadcast current waypoint
                if broadcast_func:
                    await broadcast_func({
                        'type': 'waypoint_progress',
                        'mission_id': mission.mission_id,
                        'current_waypoint': i + 1,
                        'total_waypoints': len(processed_waypoints),
                        'waypoint': waypoint,
                        'current_position': current_pos,
                        'distance_to_target': distance_to_wp
                    })
                
                # Execute single waypoint
                result = await self._execute_waypoint(waypoint, i + 1, len(processed_waypoints), broadcast_func)
                
                if not result['success']:
                    mission.status = "ABORTED"
                    return {
                        'success': False,
                        'error': f'Waypoint {i+1} failed: {result["error"]}',
                        'mission_id': mission.mission_id,
                        'completed_waypoints': i
                    }
            
            # Mission completed successfully - comprehensive logging
            mission.status = "COMPLETED"
            total_mission_time = (datetime.now() - self.mission_start_time).total_seconds()
            final_position = self._get_current_position_log()
            
            print(f"[MISSION] ═══════════════════════════════════════")
            print(f"[MISSION] 🎉 MISSION COMPLETED SUCCESSFULLY! 🎉")
            print(f"[MISSION] ═══════════════════════════════════════")
            print(f"[MISSION] Mission ID: {mission.mission_id}")
            print(f"[MISSION] Waypoints Completed: {len(processed_waypoints)}/{len(processed_waypoints)}")
            print(f"[MISSION] Total Mission Time: {total_mission_time:.1f} seconds ({total_mission_time/60:.1f} minutes)")
            print(f"[MISSION] Final Position: {final_position['lat']:.6f}, {final_position['lon']:.6f}")
            print(f"[MISSION] Final Altitude: {final_position['alt']:.1f}m")
            print(f"[MISSION] Final Battery Level: {final_position['battery']}%")
            print(f"[MISSION] Final Drone Mode: {final_position['mode']}")
            print(f"[MISSION] Average Mission Speed: {mission.stats.get('total_distance_m', 0) / total_mission_time:.1f}m/s")
            print(f"[MISSION] ═══════════════════════════════════════")
            
            self.flight_logger.log_event('mission_completed', {
                'mission_id': mission.mission_id,
                'waypoints_completed': len(processed_waypoints),
                'total_time': total_mission_time,
                'final_position': final_position,
                'mission_stats': mission.stats,
                'success_summary': {
                    'all_waypoints_reached': True,
                    'average_speed': mission.stats.get('total_distance_m', 0) / total_mission_time if total_mission_time > 0 else 0,
                    'battery_efficiency': final_position['battery']
                }
            })
            
            # Post-mission action based on configuration
            if WaypointConfig.AUTO_RTL_ON_MISSION_COMPLETE:
                try:
                    controller = getattr(self.connection, 'controller', None)
                    action = WaypointConfig.POST_MISSION_ACTION.upper()
                    
                    if controller and action != "NONE":
                        self.flight_logger.log_event('post_mission_action', {
                            'mission_id': mission.mission_id, 
                            'action': action,
                            'reason': 'mission_complete'
                        })
                        print(f"[POST-MISSION] 🏠 Initiating {action} - All waypoints completed")
                        print(f"[POST-MISSION] Current Position: {final_position['lat']:.6f}, {final_position['lon']:.6f}, {final_position['alt']:.1f}m")
                        
                        if broadcast_func:
                            await broadcast_func({
                                'type': 'mission_complete',
                                'mission_id': mission.mission_id,
                                'action': action,
                                'message': f'All waypoints completed - performing {action}',
                                'final_position': final_position
                            })
                        
                        # Perform the configured action with detailed logging
                        if action == "RTL" and hasattr(controller, 'rtl'):
                            print(f"[POST-MISSION] Executing RTL - Returning to launch point")
                            await controller.rtl()
                            print(f"[POST-MISSION] RTL command sent - Drone returning home")
                        elif action == "LAND" and hasattr(controller, 'land'):
                            print(f"[POST-MISSION] Executing LAND - Landing at current position")
                            await controller.land()
                            print(f"[POST-MISSION] LAND command sent - Drone descending")
                        elif action == "LOITER" :
                            print(f"[POST-MISSION] Executing LOITER - Hovering at final waypoint")
                            vehicle = getattr(self.connection, 'vehicle', None)
                            if vehicle:
                                vehicle.mode = VehicleMode("LOITER")
                                print(f"[POST-MISSION] Mode switched to LOITER - Drone hovering at {final_position['alt']:.1f}m altitude")
                        else:
                            print(f"[MISSION] WARNING: Action {action} not available - drone will remain at final waypoint")
                    else:
                        print("[MISSION] No post-mission action configured - drone will remain at final waypoint")
                except Exception as e:
                    print(f"[MISSION] WARNING: Post-mission action failed: {e} - drone will remain at final waypoint")
            
            return {
                'success': True,
                'mission_id': mission.mission_id,
                'waypoints_completed': len(processed_waypoints),
                'warnings': warnings
            }
            
        except Exception as e:
            if mission:
                mission.status = "ABORTED"
            
            self.flight_logger.log_event('mission_error', {
                'mission_id': mission.mission_id if mission else 'unknown',
                'error': str(e)
            })
            
            return {
                'success': False,
                'error': f'Mission execution error: {str(e)}',
                'mission_id': mission.mission_id if mission else None
            }
    
    async def _execute_waypoint(self, waypoint: Tuple[float, float, float], 
                               wp_num: int, total_wp: int,
                               broadcast_func: Optional[Callable] = None) -> Dict[str, Any]:
        """Execute a single waypoint with safety monitoring."""
        lat, lon, alt = waypoint
        
        print(f"[WAYPOINT-{wp_num}] Starting execution to {lat:.6f}, {lon:.6f}, {alt:.1f}m")
        
        self.flight_logger.log_event('waypoint_started', {
            'waypoint_number': wp_num,
            'coordinates': waypoint,
            'detailed_status': self._get_current_position_log()
        })
        
        try:
            vehicle = self.connection.vehicle
            start_pos = self._get_current_position_log()
            
            # Pre-waypoint safety checks
            print(f"[WAYPOINT-{wp_num}] Pre-flight safety check - Battery: {start_pos['battery']}%, GPS: {start_pos['satellites']} sats")
            
            emergencies = self.safety_manager.check_emergency_conditions(vehicle)
            if emergencies:
                print(f"[WAYPOINT-{wp_num}] ⚠️ EMERGENCY DETECTED: {emergencies}")
                # Handle battery emergency during waypoint navigation
                battery_emergencies = [e for e in emergencies if 'BATTERY' in e]
                if battery_emergencies:
                    print(f"[WAYPOINT-{wp_num}] 🚨 BATTERY EMERGENCY: Initiating emergency protocol")
                    action = await self._handle_waypoint_battery_emergency(
                        vehicle.battery.level, broadcast_func
                    )
                    if action in ['RTL', 'LAND']:
                        return {
                            'success': False,
                            'error': f'Emergency action taken: {action}',
                            'emergency': battery_emergencies[0]
                        }
            
            # Log mode switch to GUIDED if needed
            current_mode = getattr(vehicle.mode, 'name', 'UNKNOWN') if hasattr(vehicle, 'mode') else 'UNKNOWN'
            if current_mode != 'GUIDED':
                print(f"[WAYPOINT-{wp_num}] Mode switch: {current_mode} → GUIDED")
                self.flight_logger.log_event('mode_change', {
                    'from_mode': current_mode,
                    'to_mode': 'GUIDED',
                    'reason': f'waypoint_{wp_num}_navigation'
                })
            
            # Navigate to waypoint
            target_location = LocationGlobalRelative(lat, lon, alt)
            print(f"[WAYPOINT-{wp_num}] Sending navigation command to drone")
            print(f"[WAYPOINT-{wp_num}] From: {start_pos['lat']:.6f}, {start_pos['lon']:.6f}, {start_pos['alt']:.1f}m")
            print(f"[WAYPOINT-{wp_num}] To: {lat:.6f}, {lon:.6f}, {alt:.1f}m")
            
            vehicle.simple_goto(target_location)
            
            self.flight_logger.log_event('navigation_command_sent', {
                'waypoint_number': wp_num,
                'from_position': start_pos,
                'to_position': {'lat': lat, 'lon': lon, 'alt': alt},
                'command': 'simple_goto'
            })
            
            # Monitor waypoint approach with detailed logging
            start_time = time.time()
            last_log_time = 0
            last_distance = None
            last_altitude = None
            
            print(f"[WAYPOINT-{wp_num}] 🚁 Monitoring navigation progress...")
            
            while True:
                current_time = time.time()
                elapsed = current_time - start_time
                
                # Get detailed current status
                current_status = self._get_current_position_log()
                current_pos = (current_status['lat'], current_status['lon'])
                target_pos = (lat, lon)
                distance = NavigationUtils.calculate_distance(current_pos, target_pos)
                
                # Log progress every 2 seconds or significant changes
                should_log = (
                    elapsed - last_log_time >= 2.0 or
                    (last_distance and abs(distance - last_distance) > 1.0) or
                    (last_altitude and abs(current_status['alt'] - last_altitude) > 1.0)
                )
                
                if should_log:
                    # print(f"[WAYPOINT-{wp_num}] Progress: {distance:.1f}m to target | "
                    #       f"Alt: {current_status['alt']:.1f}m | "
                    #       f"Speed: {current_status['speed']:.1f}m/s | "
                    #       f"Mode: {current_status['mode']} | "
                    #       f"Time: {elapsed:.1f}s")
                    
                    self.flight_logger.log_event('waypoint_progress_update', {
                        'waypoint_number': wp_num,
                        'distance_remaining': distance,
                        'current_status': current_status,
                        'elapsed_time': elapsed,
                        'progress_percent': max(0, min(100, (1 - distance/100) * 100)) 
                    })
                    
                    last_log_time = elapsed
                    last_distance = distance
                    last_altitude = current_status['alt']
                
                # Check timeout
                if elapsed > self.max_waypoint_time:
                    print(f"[WAYPOINT-{wp_num}] ❌ TIMEOUT after {self.max_waypoint_time}s - Distance remaining: {distance:.1f}m")
                    return {
                        'success': False,
                        'error': f'Waypoint timeout after {self.max_waypoint_time}s'
                    }
                
                # Check if waypoint reached
                if distance <= self.waypoint_tolerance:
                    # Waypoint reached - detailed completion logging
                    final_status = self._get_current_position_log()
                    completion_time = current_time - start_time
                    
                    print(f"[WAYPOINT-{wp_num}] ✅ WAYPOINT REACHED!")
                    print(f"[WAYPOINT-{wp_num}] Final Position: {final_status['lat']:.6f}, {final_status['lon']:.6f}")
                    print(f"[WAYPOINT-{wp_num}] Final Altitude: {final_status['alt']:.1f}m")
                    print(f"[WAYPOINT-{wp_num}] Final Distance to Target: {distance:.1f}m")
                    print(f"[WAYPOINT-{wp_num}] Time Taken: {completion_time:.1f}s")
                    print(f"[WAYPOINT-{wp_num}] Average Speed: {NavigationUtils.calculate_distance((start_pos['lat'], start_pos['lon']), current_pos) / completion_time:.1f}m/s")
                    print(f"[WAYPOINT-{wp_num}] Battery Used: {start_pos['battery'] - final_status['battery']:.1f}%")
                    
                    self.flight_logger.log_waypoint_reached(
                        wp_num, total_wp, waypoint, completion_time
                    )
                    
                    # Enhanced waypoint completion logging
                    self.flight_logger.log_event('waypoint_completed_detailed', {
                        'waypoint_number': wp_num,
                        'total_waypoints': total_wp,
                        'target_coordinates': waypoint,
                        'start_status': start_pos,
                        'final_status': final_status,
                        'completion_time': completion_time,
                        'final_distance': distance,
                        'battery_used': start_pos['battery'] - final_status['battery']
                    })
                    
                    if broadcast_func:
                        await broadcast_func({
                            'type': 'waypoint_reached',
                            'waypoint_number': wp_num,
                            'total_waypoints': total_wp,
                            'coordinates': waypoint,
                            'time_taken': completion_time,
                            'final_status': final_status
                        })
                    
                    # Brief pause before next waypoint
                    if wp_num < total_wp:
                        print(f"[WAYPOINT-{wp_num}] Pausing 2 seconds before next waypoint...")
                        await asyncio.sleep(2.0)
                    
                    return {
                        'success': True,
                        'distance_to_target': distance,
                        'time_taken': completion_time,
                        'final_status': final_status
                    }
                
                # Continuous safety monitoring during waypoint navigation
                emergencies = self.safety_manager.check_emergency_conditions(vehicle)
                if emergencies:
                    critical_emergencies = [e for e in emergencies if 'CRITICAL' in e]
                    if critical_emergencies:
                        # Critical emergency - immediate action
                        await self.safety_manager.handle_emergency_landing(vehicle, critical_emergencies[0])
                        return {
                            'success': False,
                            'error': f'Critical emergency: {critical_emergencies[0]}',
                            'emergency_action': 'EMERGENCY_LAND'
                        }
                
                # Brief pause before next check
                await asyncio.sleep(0.5)
                
        except Exception as e:
            self.flight_logger.log_event('waypoint_error', {
                'waypoint_number': wp_num,
                'coordinates': waypoint,
                'error': str(e)
            })
            
            return {
                'success': False,
                'error': f'Waypoint execution error: {str(e)}'
            }
    
    async def _handle_waypoint_battery_emergency(self, battery_level: float, 
                                               broadcast_func: Optional[Callable] = None) -> str:
        """Handle battery emergency during waypoint mission."""
        vehicle = self.connection.vehicle
        
        self.flight_logger.log_event('battery_emergency_waypoint', {
            'battery_level': battery_level,
            'mission_id': self.current_mission.mission_id if self.current_mission else 'unknown'
        })
        
        try:
            # Switch to LOITER mode
            vehicle.mode = VehicleMode("LOITER")
            
            # Wait for mode change
            timeout = time.time() + 5.0
            while str(vehicle.mode) != "LOITER" and time.time() < timeout:
                await asyncio.sleep(0.1)
            
            # Align yaw to home position
            await self._align_yaw_to_home()
            
            # Prompt user for choice
            return await self._prompt_battery_emergency_choice(battery_level, broadcast_func)
            
        except Exception as e:
            self.flight_logger.log_event('battery_emergency_error', {
                'error': str(e),
                'battery_level': battery_level
            })
            
            # Default to RTL on error
            await self.safety_manager.handle_emergency_rtl(vehicle, f"Battery emergency handling failed: {e}")
            return "RTL"
    
    async def _align_yaw_to_home(self):
        """Align drone yaw to face home position."""
        vehicle = self.connection.vehicle
        
        try:
            current_pos = (vehicle.location.global_relative_frame.lat,
                          vehicle.location.global_relative_frame.lon)
            
            home_location = vehicle.home_location
            if home_location:
                home_pos = (home_location.lat, home_location.lon)
                
                # Calculate bearing to home
                bearing = NavigationUtils.calculate_bearing(current_pos, home_pos)
                
                if bearing is not None:
                    # Simple approach: Just log the bearing - RTL will handle orientation automatically
                    print(f"[YAW] Calculated bearing to home: {bearing:.1f}°")
                    
                    self.flight_logger.log_event('yaw_calculated_to_home', {
                        'bearing': bearing,
                        'current_position': current_pos,
                        'home_position': home_pos,
                        'note': 'RTL will auto-orient drone'
                    })
                else:
                    print("[YAW] Could not calculate bearing to home")
                    
        except Exception as e:
            self.flight_logger.log_event('yaw_alignment_error', {'error': str(e)})
            print(f"[YAW] Alignment calculation failed: {e}")
    
    async def _prompt_battery_emergency_choice(self, battery_level: float, 
                                             broadcast_func: Optional[Callable] = None) -> str:
        """Prompt user for emergency action choice."""
        prompt_id = f"battery_emergency_{int(time.time())}"
        
        self.emergency_prompts[prompt_id] = {
            'type': 'battery_emergency',
            'battery_level': battery_level,
            'timestamp': time.time(),
            'response': None
        }
        
        if broadcast_func:
            await broadcast_func({
                'type': 'emergency_prompt',
                'prompt_id': prompt_id,
                'message': f'BATTERY EMERGENCY: {battery_level}% remaining. Choose action:',
                'options': ['RTL', 'LAND'],
                'timeout': WaypointConfig.EMERGENCY_RESPONSE_TIMEOUT
            })
        
        # Wait for user response with timeout
        timeout = time.time() + WaypointConfig.EMERGENCY_RESPONSE_TIMEOUT
        
        while time.time() < timeout:
            if (prompt_id in self.emergency_prompts and 
                self.emergency_prompts[prompt_id]['response']):
                
                choice = self.emergency_prompts[prompt_id]['response']
                del self.emergency_prompts[prompt_id]
                
                # Execute chosen action
                vehicle = self.connection.vehicle
                if choice.upper() == 'RTL':
                    await self.safety_manager.handle_emergency_rtl(vehicle, f"User choice: battery {battery_level}%")
                elif choice.upper() == 'LAND':
                    await self.safety_manager.handle_emergency_landing(vehicle, f"User choice: battery {battery_level}%")
                
                return choice.upper()
            
            await asyncio.sleep(0.1)
        
        # Timeout - default action
        del self.emergency_prompts[prompt_id]
        
        vehicle = self.connection.vehicle
        default_action = "RTL" if battery_level > WaypointConfig.EMERGENCY_BATTERY_LEVEL else "LAND"
        
        if default_action == "RTL":
            await self.safety_manager.handle_emergency_rtl(vehicle, f"Timeout: battery {battery_level}%")
        else:
            await self.safety_manager.handle_emergency_landing(vehicle, f"Timeout: battery {battery_level}%")
        
        self.flight_logger.log_event('emergency_timeout_action', {
            'battery_level': battery_level,
            'action': default_action,
            'timeout': WaypointConfig.EMERGENCY_RESPONSE_TIMEOUT
        })
        
        return default_action
    
    def handle_emergency_response(self, prompt_id: str, choice: str) -> bool:
        """Handle user response to emergency prompt."""
        if prompt_id in self.emergency_prompts:
            self.emergency_prompts[prompt_id]['response'] = choice
            
            self.flight_logger.log_event('emergency_response_received', {
                'prompt_id': prompt_id,
                'choice': choice,
                'response_time': time.time() - self.emergency_prompts[prompt_id]['timestamp']
            })
            
            return True
        
        return False
    
    def get_mission_status(self) -> Optional[Dict[str, Any]]:
        """Get current mission status."""
        if not self.current_mission:
            return None
        
        status = self.current_mission.to_dict()
        
        if self.mission_start_time:
            status['runtime_seconds'] = (datetime.now() - self.mission_start_time).total_seconds()
        
        return status
    
    def abort_mission(self, reason: str = "User requested") -> bool:
        """Abort current mission."""
        if not self.current_mission:
            return False
        
        self.current_mission.status = "ABORTED"
        
        self.flight_logger.log_event('mission_aborted', {
            'mission_id': self.current_mission.mission_id,
            'reason': reason,
            'waypoints_completed': self.current_mission.current_waypoint_index
        })
        
        return True