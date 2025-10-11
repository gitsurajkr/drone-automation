"""
Command Handlers for Drone Control Operations
Processes WebSocket commands with comprehensive error handling and logging.
"""

import json
import time
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(level=logging.INFO, 
                  format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('command_handlers')
drone_logger = None

# Global command tracking for conflict detection and safety
_active_commands = {}
_last_command_time = {}
_command_history = []
_command_rate_limits = {
    'arm': 3.0,       # 2 seconds between arm attempts
    'takeoff': 5.0,   # 5 seconds between takeoff attempts  
    'land': 3.0,      # 3 seconds between land attempts
    'rtl': 3.0,       # 3 seconds between RTL attempts
    'emergency': 0.5, # 0.5 seconds for emergency commands
    'waypoint': 1.0,  # 1 second between waypoint commands
    'connect': 0.1    # 0.1 seconds between connect attempts (allow rapid retries)
}
COMMAND_TIMEOUT = 30.0  # seconds
MAX_COMMAND_HISTORY = 100


def _log_command(command: str, payload: Dict[str, Any], result: Dict[str, Any]):
    """Log command execution for audit trail."""
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'command': command,
        'payload': payload,
        'result': result,
        'success': result.get('status') == 'ok'
    }
    
    _command_history.append(log_entry)
    
    # Trim history
    if len(_command_history) > MAX_COMMAND_HISTORY:
        _command_history.pop(0)
    
    # Log to system logger
    if logger:
        if log_entry['success']:
            logger.info(f"Command executed: {command} - {result.get('detail', 'No detail')}")
        else:
            logger.warning(f"Command failed: {command} - {result.get('detail', 'Unknown error')}")
    
    # Log to drone logger if available
    if drone_logger:
        if log_entry['success']:
            drone_logger.log_flight_event('COMMAND_SUCCESS', log_entry)
        else:
            drone_logger.log_safety_event('COMMAND_FAILURE', log_entry, 'WARNING')


def _validate_command_rate_limit(command: str) -> Tuple[bool, str]:
    """Validate command is not being sent too frequently."""
    current_time = time.time()
    
    # Get base command type (remove modifiers)
    base_command = command.split('_')[0] if '_' in command else command
    rate_limit = _command_rate_limits.get(base_command, 1.0)
    
    last_time = _last_command_time.get(command, 0)
    time_since_last = current_time - last_time
    
    if time_since_last < rate_limit:
        remaining = rate_limit - time_since_last
        return False, f"Rate limited: wait {remaining:.1f}s before retry"
    
    _last_command_time[command] = current_time
    return True, "Rate limit ok"


def _validate_command_conflicts(command: str) -> Tuple[bool, str]:
    """Check for conflicting active commands."""
    current_time = time.time()
    
    # Clean up expired active commands
    expired_commands = []
    for cmd, start_time in _active_commands.items():
        if current_time - start_time > COMMAND_TIMEOUT:
            expired_commands.append(cmd)
    
    for cmd in expired_commands:
        del _active_commands[cmd]
        if logger:
            logger.warning(f"Command timeout: {cmd}")
    
    # Define command conflicts
    conflicts = {
        'takeoff': ['land', 'rtl', 'emergency_land'],
        'land': ['takeoff', 'rtl', 'arm'],
        'rtl': ['takeoff', 'land', 'waypoint_mission'],
        'arm': ['disarm', 'emergency_disarm'],
        'disarm': ['arm', 'takeoff'],
        'waypoint_mission': ['rtl', 'land', 'takeoff']
    }
    
    # Check for conflicts
    conflicting_commands = conflicts.get(command, [])
    for active_cmd in _active_commands:
        if active_cmd in conflicting_commands:
            return False, f"Conflict with active command: {active_cmd}"
    
    return True, "No conflicts detected"


async def handle_connect(start_telemetry_func, conn) -> Dict[str, Any]:
    """Handle drone connection command."""
    
    # Mark command as active
    _active_commands['connect'] = time.time()
    
    try:
        if logger:
            logger.info("Initiating drone connection")
        
        # Start telemetry
        await start_telemetry_func()
        
        # Validate connection
        controller = getattr(conn, "controller", None)
        if not controller:
            raise Exception("No controller available")
        
        vehicle = getattr(controller, "vehicle", None)
        if not vehicle:
            raise Exception("No vehicle detected after connection")
        
        # Additional connection validation
        heartbeat = getattr(vehicle, "last_heartbeat", None)
        if heartbeat and heartbeat > 5.0:
            logger.warning(f"High heartbeat latency detected: {heartbeat:.1f}s")
        
        # Check basic vehicle state
        is_armable = getattr(vehicle, "is_armable", False)
        mode = getattr(vehicle.mode, "name", "UNKNOWN") if hasattr(vehicle, 'mode') else "UNKNOWN"
        
        result = {
            "status": "ok",
            "detail": "drone connected successfully",
            "drone_connected": True,
            "vehicle_mode": mode,
            "is_armable": is_armable,
            "heartbeat": heartbeat
        }
        
        if logger:
            logger.info(f"Connection successful: mode={mode}, armable={is_armable}")
        
    except asyncio.TimeoutError:
        result = {"status": "error", "detail": "connection timeout", "drone_connected": False}
        if logger:
            logger.error("Connection attempt timed out")

    except Exception as e:
        # On connection failure, attach a safety report if possible
        result = {"status": "error", "detail": f"connection failed: {str(e)}", "drone_connected": False}
        if logger:
            logger.error(f"Connection failed: {e}")
    
    finally:
        # Remove from active commands
        _active_commands.pop('connect', None)
    
    _log_command('connect', {}, result)
    return result


async def handle_disconnect(stop_telemetry_func, conn) -> Dict[str, Any]:
    # Handle disconnect command
    try:
        await stop_telemetry_func()
        return {"status": "ok", "detail": "drone disconnected and telemetry stopped", "drone_connected": False}
    except Exception as e:
        return {"status": "error", "detail": f"disconnect failed: {str(e)}", "drone_connected": False}


async def handle_reconnect(reconnect_telemetry_func) -> Dict[str, Any]:
    # Handle reconnect command
    await reconnect_telemetry_func()
    return {"status": "ok", "detail": "telemetry reconnected"}


async def handle_status(drone_connected: bool) -> Dict[str, Any]:
    # Handle status command
    detail = "drone is connected" if drone_connected else "drone is not connected"
    return {"status": "ok", "detail": detail, "drone_connected": drone_connected}


async def handle_arm(conn) -> Dict[str, Any]:
    # Handle arm command.
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.arm()
        return {"status": "ok" if result else "error", "detail": "armed" if result else "arm failed"}
    except Exception as e:
        return {"status": "error", "detail": f"arm exception: {e}"}


async def handle_disarm(conn) -> Dict[str, Any]:
    # Handle disarm command
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.disarm()
        return {"status": "ok" if result else "error", "detail": "disarmed" if result else "disarm failed"}
    except Exception as e:
        return {"status": "error", "detail": f"disarm exception: {e}"}


async def handle_arm_and_takeoff(conn, altitude: float = 5.0) -> Dict[str, Any]:
    """Handle arm and takeoff command - prevents auto-disarm timeout."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.arm_and_takeoff(altitude)
        return {"status": "ok" if result else "error", 
                "detail": f"arm + takeoff to {altitude}m successful" if result else "arm + takeoff failed"}
    except Exception as e:
        return {"status": "error", "detail": f"arm + takeoff exception: {e}"}


async def handle_message(payload: dict, broadcast_func) -> Dict[str, Any]:
    # Handle message broadcast command
    try:
        msg = payload.get("message", "")
        await broadcast_func(json.dumps({"type": "message", "message": msg}))
        return {"status": "ok", "detail": "message broadcast"}
    except Exception as e:
        return {"status": "error", "detail": f"broadcast failed: {e}"}


async def handle_sitl_setup(conn) -> Dict[str, Any]:
    """Handle SITL setup command - configure vehicle for SITL use."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.setup_sitl_connection()
        return {"status": "ok" if result else "error", 
                "detail": "SITL setup successful" if result else "SITL setup failed"}
    except Exception as e:
        return {"status": "error", "detail": f"SITL setup exception: {e}"}


async def handle_takeoff(conn, altitude: float = 10.0) -> Dict[str, Any]:
    """Handle takeoff command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Validate altitude
        if altitude <= 0 or altitude > 100:
            return {"status": "error", "detail": f"altitude must be between 0 and 100m (got {altitude}m)"}
            
        result = await controller.takeoff(altitude)
        return {"status": "ok" if result else "error", 
                "detail": f"takeoff to {altitude}m successful" if result else f"takeoff to {altitude}m failed"}
    except Exception as e:
        return {"status": "error", "detail": f"takeoff exception: {e}"}


async def handle_land(conn, payload: dict = None) -> Dict[str, Any]:
    """Handle land command - safely land at current location."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Check if this is an emergency landing request
        emergency_override = False
        if payload and payload.get("emergency", False):
            emergency_override = True
            print("🚨 Emergency landing requested - bypassing safety checks")
        
        # Auto-detect critical battery situation and enable emergency override
        vehicle = getattr(controller.connection, "vehicle", None)
        if vehicle:
            battery = getattr(vehicle, "battery", None)
            battery_level = getattr(battery, "level", None) if battery else None
            if battery_level is not None and battery_level < 25:  # Very critical
                emergency_override = True
                print(f"🚨 Auto-detected critical battery ({battery_level}%) - enabling emergency override")
        
        result = await controller.land(emergency_override=emergency_override)
        detail = "emergency landing successful" if emergency_override else "landing successful"
        if not result:
            detail = "emergency landing failed" if emergency_override else "landing failed"
        
        return {"status": "ok" if result else "error", "detail": detail}
    except Exception as e:
        return {"status": "error", "detail": f"landing exception: {e}"}


async def handle_emergency_disarm(conn) -> Dict[str, Any]:
    """Handle emergency disarm command with mandatory confirmation."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Emergency disarm requires explicit confirmation for safety
        result = await controller.emergency_disarm(confirm_emergency=True)
        return {"status": "ok" if result else "error", "detail": "emergency disarmed" if result else "emergency disarm failed"}
    except Exception as e:
        return {"status": "error", "detail": f"emergency disarm exception: {e}"}


async def handle_rtl(conn, payload: dict = None) -> Dict[str, Any]:
    """Handle return to launch command - return home and land."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Check if this is an emergency RTL request
        emergency_override = False
        if payload and payload.get("emergency", False):
            emergency_override = True
            print("🚨 Emergency RTL requested - bypassing safety checks")
        
        # Auto-detect critical battery situation and enable emergency override
        vehicle = getattr(controller.connection, "vehicle", None)
        if vehicle:
            battery = getattr(vehicle, "battery", None)
            battery_level = getattr(battery, "level", None) if battery else None
            if battery_level is not None and battery_level < 25:  # Very critical
                emergency_override = True
                print(f"🚨 Auto-detected critical battery ({battery_level}%) - enabling emergency RTL override")
        
        result = await controller.rtl(emergency_override=emergency_override)
        detail = "emergency RTL successful" if emergency_override else "return to launch successful"
        if not result:
            detail = "emergency RTL failed" if emergency_override else "return to launch failed"
            
        return {"status": "ok" if result else "error", "detail": detail}
    except Exception as e:
        return {"status": "error", "detail": f"RTL exception: {e}"}


async def handle_fly_timed(conn, altitude: float = 5.0, duration: float = 5.0, broadcast_func=None) -> Dict[str, Any]:
    """Handle timed flight mission - fly at altitude for duration then RTL."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Validate parameters
        if altitude <= 0 or altitude > 30:
            return {"status": "error", "detail": f"altitude must be between 0 and 30m (got {altitude}m)"}
        if duration <= 0 or duration > 300:
            return {"status": "error", "detail": f"duration must be between 0 and 300s (got {duration}s)"}
            
        result = await controller.fly_timed_mission(altitude, duration, broadcast_func)
        return {"status": "ok" if result else "error", 
                "detail": f"timed flight mission ({altitude}m for {duration}s) successful" if result else "timed flight mission failed"}
    except Exception as e:
        return {"status": "error", "detail": f"timed flight exception: {e}"}


async def handle_mission_status(conn) -> Dict[str, Any]:
    """Handle mission status request."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        mission_status = controller.get_mission_status()
        if mission_status:
            return {"status": "ok", "detail": "mission active", "mission": mission_status}
        else:
            return {"status": "ok", "detail": "no active mission", "mission": None}
    except Exception as e:
        return {"status": "error", "detail": f"mission status exception: {e}"}


async def handle_set_throttle(conn, throttle_percent: float = 0.0) -> Dict[str, Any]:
    """Handle throttle control command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Validate throttle range
        if throttle_percent < 0 or throttle_percent > 100:
            return {"status": "error", "detail": f"throttle must be between 0-100% (got {throttle_percent}%)"}
            
        result = await controller.set_throttle(throttle_percent)
        return {"status": "ok" if result else "error", 
                "detail": f"throttle set to {throttle_percent}%" if result else "throttle control failed"}
    except Exception as e:
        return {"status": "error", "detail": f"throttle control exception: {e}"}


async def handle_release_throttle(conn) -> Dict[str, Any]:
    """Handle release throttle control command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.release_throttle_control()
        return {"status": "ok" if result else "error", 
                "detail": "throttle control released to autopilot" if result else "failed to release throttle control"}
    except Exception as e:
        return {"status": "error", "detail": f"release throttle exception: {e}"}

async def handle_emergency_land(conn) -> Dict[str, Any]:
    """Handle emergency land command - critical safety function."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.emergency_land()
        return {"status": "ok" if result else "error", 
                "detail": "emergency land initiated" if result else "emergency land failed"}
    except Exception as e:
        return {"status": "error", "detail": f"emergency land exception: {e}"}

async def handle_verify_home(conn) -> Dict[str, Any]:
    """Handle home location verification command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        is_valid, message = controller.verify_home_location()
        distance = controller.get_home_distance()
        
        result = {
            "status": "ok" if is_valid else "warning",
            "detail": message,
            "home_valid": is_valid
        }
        
        if distance is not None:
            result["distance_to_home"] = round(distance, 1)
            
        return result
    except Exception as e:
        return {"status": "error", "detail": f"home verification exception: {e}"}

async def handle_force_land_here(conn) -> Dict[str, Any]:
    """Handle force land here command - DANGEROUS, lands at current location."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.force_land_here()
        return {"status": "ok" if result else "error", 
                "detail": "force land initiated" if result else "force land failed"}
    except Exception as e:
        return {"status": "error", "detail": f"force land exception: {e}"}


async def handle_battery_emergency_response(conn, payload: dict) -> Dict[str, Any]:
    """Handle user response to battery emergency prompt."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Extract data from nested payload structure
        nested_payload = payload.get('payload', payload)  # Use nested payload if it exists, otherwise use payload directly
        prompt_id = nested_payload.get("prompt_id", "")
        choice = nested_payload.get("choice", "").upper()
        
        print(f"[EMERGENCY] Received response - prompt_id: {prompt_id}, choice: {choice}")
        
        if not prompt_id:
            print(f"[EMERGENCY] DEBUG - Missing prompt_id. Full payload: {payload}")
            return {"status": "error", "detail": "missing prompt_id"}
        if choice not in ["RTL", "LAND"]:
            print(f"[EMERGENCY] DEBUG - Invalid choice: {choice}")
            return {"status": "error", "detail": "invalid choice - must be RTL or LAND"}
        
        success = controller.handle_battery_emergency_response(prompt_id, choice)
        print(f"[EMERGENCY] Response handled successfully: {success}")
        return {"status": "ok" if success else "error", 
                "detail": f"emergency response '{choice}' recorded" if success else "failed to record emergency response"}
    except Exception as e:
        print(f"[EMERGENCY] Exception handling response: {e}")
        return {"status": "error", "detail": f"battery emergency response exception: {e}"}


def check_command_conflicts(command_type: str) -> tuple[bool, str]:
    """Check for conflicting commands that could cause dangerous situations."""
    current_time = time.time()
    
    # Clean up old commands
    expired_commands = [cmd for cmd, start_time in _last_command_time.items() 
                       if current_time - start_time > COMMAND_TIMEOUT]
    for cmd in expired_commands:
        _active_commands.pop(cmd, None)
        _last_command_time.pop(cmd, None)
    
    # Define conflicting command groups
    flight_commands = ["takeoff", "land", "rtl", "fly_timed"]
    critical_commands = ["emergency_disarm", "emergency_land"]
    
    # Check for conflicts
    if command_type in flight_commands:
        active_flight_cmds = [cmd for cmd in _active_commands if cmd in flight_commands]
        if active_flight_cmds:
            return False, f"Flight command conflict: {active_flight_cmds[0]} already active"
    
    # Emergency commands can interrupt anything
    if command_type in critical_commands:
        _active_commands.clear()  # Clear all active commands
    
    return True, "No conflicts"

# Command registry - maps command types to their handlers
COMMAND_HANDLERS = {
    "connect": handle_connect,
    "disconnect": handle_disconnect,
    "reconnect": handle_reconnect,
    "status": handle_status,
    "arm": handle_arm,
    "arm_and_takeoff": handle_arm_and_takeoff,
    "disarm": handle_disarm,
    "emergency_disarm": handle_emergency_disarm,
    "sitl_setup": handle_sitl_setup,
    "message": handle_message,
    "takeoff": handle_takeoff,
    "land": handle_land,
    "rtl": handle_rtl,  
    "fly_timed": handle_fly_timed,
    "mission_status": handle_mission_status,
    "set_throttle": handle_set_throttle,
    "release_throttle": handle_release_throttle,
    "emergency_land": handle_emergency_land,
    "verify_home": handle_verify_home,
    "force_land_here": handle_force_land_here,
    "battery_emergency_response": handle_battery_emergency_response,
}


async def execute_command(
    command_type: str,
    payload: Optional[dict],
    conn,
    drone_connected: bool,
    start_telemetry_func,
    stop_telemetry_func,
    reconnect_telemetry_func,
    broadcast_func
) -> Dict[str, Any]:
    # CRITICAL: Check for command conflicts first
    conflict_ok, conflict_msg = check_command_conflicts(command_type)
    if not conflict_ok:
        return {"status": "error", "detail": f"Command conflict: {conflict_msg}"}
    
    # Track active command
    _active_commands[command_type] = True
    _last_command_time[command_type] = time.time()
    
    # Log command execution
    print(f"[COMMAND] Executing: {command_type.upper()}")
    if payload:
        print(f"[COMMAND] Parameters: {payload}")
    
    try:
        # Execute the command based on its type
        handler = COMMAND_HANDLERS.get(command_type)
        if not handler:
            print(f"[COMMAND] ERROR - Unknown command: {command_type}")
            return {"status": "error", "detail": f"unknown command: {command_type}"}
        
        if command_type == "connect":
            result = await handler(start_telemetry_func, conn)
        elif command_type == "disconnect":
            result = await handler(stop_telemetry_func, conn)
        elif command_type == "reconnect":
            result = await handler(reconnect_telemetry_func)
        elif command_type == "status":
            result = await handler(drone_connected)
        elif command_type in ["arm", "disarm", "emergency_disarm", "sitl_setup", "mission_status", "release_throttle", "emergency_land", "verify_home", "force_land_here"]:
            result = await handler(conn)
        elif command_type in ["land", "rtl"]:
            # These commands now support payload for emergency override
            result = await handler(conn, payload)
        elif command_type == "arm_and_takeoff":
            # Handle arm + takeoff with optional altitude parameter
            altitude = 5.0  # default altitude
            if payload and "altitude" in payload:
                try:
                    altitude = float(payload["altitude"])
                except (ValueError, TypeError):
                    return {"status": "error", "detail": "invalid altitude parameter"}
            result = await handler(conn, altitude)
        elif command_type == "takeoff":
            # Handle takeoff with optional altitude parameter
            altitude = 10.0  # default altitude
            if payload and "altitude" in payload:
                try:
                    altitude = float(payload["altitude"])
                except (ValueError, TypeError):
                    return {"status": "error", "detail": "invalid altitude parameter"}
            result = await handler(conn, altitude)
        elif command_type == "fly_timed":
            # Handle timed flight with altitude and duration parameters
            altitude = 5.0  # default altitude
            duration = 5.0  # default duration
            if payload:
          
                # Extract nested payload parameters (fix for parameter extraction bug)
                nested_payload = payload.get('payload', payload)  # Use nested payload if it exists, otherwise use payload directly
           
                try:
                    if "altitude" in nested_payload:
                        altitude = float(nested_payload["altitude"])
                        print(f"[COMMAND] Using altitude: {altitude}m")
                    else:
                        print(f"[COMMAND] DEBUG - 'altitude' not found in nested payload")
                    if "duration" in nested_payload:
                        duration = float(nested_payload["duration"])
                        print(f"[COMMAND] Using duration: {duration}s")
                    else:
                        print(f"[COMMAND] DEBUG - 'duration' not found in nested payload")
                except (ValueError, TypeError) as e:
                    print(f"[COMMAND] ERROR - Invalid parameter conversion: {e}")
                    return {"status": "error", "detail": "invalid altitude or duration parameter"}
            else:
                print("[COMMAND] DEBUG - No payload received, using defaults")
            print(f"[COMMAND] Final parameters - Altitude: {altitude}m, Duration: {duration}s")
            print(f"[COMMAND] DEBUG - About to call handler with: conn={conn}, altitude={altitude}, duration={duration}")
            result = await handler(conn, altitude, duration, broadcast_func)
        elif command_type == "set_throttle":
            # Handle throttle control with throttle percentage parameter
            throttle_percent = 0.0  # default throttle
            if payload and "throttle" in payload:
                try:
                    throttle_percent = float(payload["throttle"])
                except (ValueError, TypeError):
                    return {"status": "error", "detail": "invalid throttle parameter"}
            result = await handler(conn, throttle_percent)
        elif command_type == "message":
            result = await handler(payload, broadcast_func)
        elif command_type == "battery_emergency_response":
            result = await handler(conn, payload)
        elif command_type == "execute_waypoint_mission":
            # Handle waypoint mission execution
            # The waypoints are nested in payload.payload
            inner_payload = payload.get("payload", {}) if payload else {}
            waypoints = inner_payload.get("waypoints", [])
            takeoff_altitude = inner_payload.get("takeoff_altitude")
            result = await handle_execute_waypoint_mission(conn, waypoints, takeoff_altitude, broadcast_func)
        elif command_type in ["waypoint_mission_status", "stop_waypoint_mission"]:
            # Commands that only need conn parameter
            result = await handler(conn)
        elif command_type == "set_waypoint_override":
            override = payload.get("override", True) if payload else True
            result = await handle_set_waypoint_override(conn, override)
        elif command_type == "fly_to_waypoint":
            if not payload:
                result = {"status": "error", "detail": "missing waypoint coordinates"}
            else:
                lat = payload.get("latitude")
                lon = payload.get("longitude") 
                alt = payload.get("altitude", 20.0)
                result = await handle_fly_to_waypoint(conn, lat, lon, alt)
        elif command_type == "validate_waypoints":
            waypoints = payload.get("waypoints", []) if payload else []
            result = await handle_validate_waypoints(conn, waypoints)
        elif command_type == "calculate_mission_stats":
            waypoints = payload.get("waypoints", []) if payload else []
            result = await handle_calculate_mission_stats(conn, waypoints)
        elif command_type == "generate_grid_mission":
            if not payload:
                result = {"status": "error", "detail": "missing grid parameters"}
            else:
                result = await handle_generate_grid_mission(
                    conn, 
                    payload.get("start_lat"), 
                    payload.get("start_lon"),
                    payload.get("grid_size", 5),
                    payload.get("spacing", 50.0),
                    payload.get("altitude", 20.0)
                )
        elif command_type == "generate_circular_mission":
            if not payload:
                result = {"status": "error", "detail": "missing circular parameters"}
            else:
                result = await handle_generate_circular_mission(
                    conn,
                    payload.get("center_lat"),
                    payload.get("center_lon"), 
                    payload.get("radius_meters", 100.0),
                    payload.get("num_points", 8),
                    payload.get("altitude", 20.0)
                )
        elif command_type == "waypoint_emergency_response":
            prompt_id = payload.get("prompt_id", "") if payload else ""
            choice = payload.get("choice", "") if payload else ""
            result = await handle_waypoint_emergency_response(conn, prompt_id, choice)
        else:
            result = {"status": "error", "detail": f"handler not implemented for: {command_type}"}
        
        # Log command result
        status = result.get("status", "unknown")
        if status == "ok":
            print(f"[COMMAND] SUCCESS - {command_type.upper()} completed")
        else:
            detail = result.get("detail", "no details")
            print(f"[COMMAND] FAILED - {command_type.upper()}: {detail}")
        
        return result
        
    finally:
        # Remove command from active tracking when done
        _active_commands.pop(command_type, None)


# =============================================================================
# WAYPOINT COMMAND HANDLERS
# =============================================================================

async def handle_execute_waypoint_mission(conn, waypoints: list, takeoff_altitude: float = None, broadcast_func=None) -> Dict[str, Any]:
    """Handle waypoint mission execution command with emergency response capability."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Validate waypoints format
        if not waypoints or not isinstance(waypoints, list):
            return {"status": "error", "detail": "waypoints must be a non-empty list"}
        
        # Convert and validate each waypoint (support both object and array formats)
        converted_waypoints = []
        for i, wp in enumerate(waypoints):
            try:
                # Handle object format: {latitude: x, longitude: y, altitude: z}
                if isinstance(wp, dict):
                    lat = float(wp.get('latitude', 0))
                    lon = float(wp.get('longitude', 0)) 
                    alt = float(wp.get('altitude', 20))
                # Handle array/tuple format: [lat, lon, alt]
                elif isinstance(wp, (list, tuple)) and len(wp) >= 2:
                    lat = float(wp[0])
                    lon = float(wp[1])
                    alt = float(wp[2]) if len(wp) > 2 else 20.0
                else:
                    return {"status": "error", "detail": f"waypoint {i+1} must be object or array with lat,lon"}
                
                # Validate coordinates
                if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                    return {"status": "error", "detail": f"waypoint {i+1} has invalid coordinates"}
                    
                converted_waypoints.append((lat, lon, alt))
                
            except (ValueError, TypeError, KeyError):
                return {"status": "error", "detail": f"waypoint {i+1} has invalid coordinate format"}
        
        print(f"INFO: Executing waypoint mission with {len(converted_waypoints)} waypoints")
        print(f"INFO: Emergency broadcast function {'available' if broadcast_func else 'not available'}")
        
        # Execute mission with emergency broadcast capability
        result = await controller.execute_waypoint_mission(converted_waypoints, takeoff_altitude, broadcast_func)
        
        return {
            "status": "ok" if result else "error", 
            "detail": f"waypoint mission {'completed successfully' if result else 'failed'}",
            "waypoints_count": len(converted_waypoints)
        }
    except Exception as e:
        return {"status": "error", "detail": f"waypoint mission exception: {e}"}


async def handle_waypoint_mission_status(conn) -> Dict[str, Any]:
    """Handle waypoint mission status query."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        mission_status = controller.get_waypoint_mission_status()
        return {"status": "ok", "detail": "waypoint mission status", "mission_status": mission_status}
    except Exception as e:
        return {"status": "error", "detail": f"waypoint status exception: {e}"}


async def handle_stop_waypoint_mission(conn) -> Dict[str, Any]:
    """Handle stop waypoint mission command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = controller.stop_waypoint_mission()
        return {
            "status": "ok" if result else "error", 
            "detail": "waypoint mission stopped" if result else "no active waypoint mission to stop"
        }
    except Exception as e:
        return {"status": "error", "detail": f"stop waypoint mission exception: {e}"}


async def handle_cancel_takeoff(conn) -> Dict[str, Any]:
    """Handle request to cancel an in-progress takeoff safely."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}

    try:
        result = controller.cancel_takeoff()
        return {"status": "ok" if result else "error", "detail": "cancel takeoff executed" if result else "no takeoff to cancel"}
    except Exception as e:
        return {"status": "error", "detail": f"cancel takeoff exception: {e}"}


async def handle_set_waypoint_override(conn, override: bool = True) -> Dict[str, Any]:
    """Handle set waypoint manual override command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        controller.set_waypoint_manual_override(override)
        action = "activated" if override else "deactivated"
        return {"status": "ok", "detail": f"waypoint manual override {action}"}
    except Exception as e:
        return {"status": "error", "detail": f"waypoint override exception: {e}"}


async def handle_fly_to_waypoint(conn, latitude: float, longitude: float, altitude: float = 20.0) -> Dict[str, Any]:
    """Handle fly to single waypoint command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Validate coordinates
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return {"status": "error", "detail": "invalid coordinates"}
        
        if altitude <= 0 or altitude > 100:
            return {"status": "error", "detail": "altitude must be between 0 and 100 meters"}
        
        # Initialize waypoint system if needed
        if not hasattr(controller, 'waypoint_mission'):
            controller._Controller__init_waypoint_system()
        
        print(f"INFO: Flying to waypoint: {latitude:.6f}, {longitude:.6f}, {altitude}m")
        success = await controller.fly_to_waypoint((latitude, longitude, altitude), 1, 1)
        
        return {
            "status": "ok" if success else "error", 
            "detail": f"waypoint {'reached successfully' if success else 'navigation failed'}",
            "coordinates": {"lat": latitude, "lon": longitude, "alt": altitude}
        }
    except Exception as e:
        return {"status": "error", "detail": f"fly to waypoint exception: {e}"}


async def handle_validate_waypoints(conn, waypoints: list) -> Dict[str, Any]:
    """Handle waypoint validation command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Validate waypoints format
        if not waypoints or not isinstance(waypoints, list):
            return {"status": "error", "detail": "waypoints must be a non-empty list"}
        
        # Initialize waypoint system if needed
        if not hasattr(controller, 'waypoint_mission'):
            controller._Controller__init_waypoint_system()
        
        processed_waypoints = controller.validate_and_process_waypoints(waypoints)
        
        validation_result = {
            "original_count": len(waypoints),
            "processed_count": len(processed_waypoints),
            "waypoints_valid": len(processed_waypoints) > 0,
            "processed_waypoints": processed_waypoints
        }
        
        return {
            "status": "ok", 
            "detail": f"validated {len(waypoints)} waypoints, {len(processed_waypoints)} are valid",
            "validation": validation_result
        }
    except Exception as e:
        return {"status": "error", "detail": f"waypoint validation exception: {e}"}


async def handle_calculate_mission_stats(conn, waypoints: list) -> Dict[str, Any]:
    """Handle mission statistics calculation command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        if not waypoints or not isinstance(waypoints, list):
            return {"status": "error", "detail": "waypoints must be a non-empty list"}
        
        stats = controller.calculate_mission_stats(waypoints)
        return {
            "status": "ok", 
            "detail": "mission statistics calculated",
            "mission_stats": stats
        }
    except Exception as e:
        return {"status": "error", "detail": f"mission stats exception: {e}"}


async def handle_generate_grid_mission(conn, start_lat: float, start_lon: float, 
                                     grid_size: int, spacing: float, altitude: float = 20.0) -> Dict[str, Any]:
    """Handle grid mission generation command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Validate parameters
        if not (-90 <= start_lat <= 90) or not (-180 <= start_lon <= 180):
            return {"status": "error", "detail": "invalid start coordinates"}
        
        if grid_size <= 0 or grid_size > 20:
            return {"status": "error", "detail": "grid_size must be between 1 and 20"}
        
        if spacing <= 0 or spacing > 1000:
            return {"status": "error", "detail": "spacing must be between 0 and 1000 meters"}
        
        waypoints = controller.generate_grid_mission(start_lat, start_lon, grid_size, spacing, altitude)
        
        return {
            "status": "ok", 
            "detail": f"generated grid mission with {len(waypoints)} waypoints",
            "waypoints": waypoints,
            "mission_type": "grid"
        }
    except Exception as e:
        return {"status": "error", "detail": f"grid mission generation exception: {e}"}


async def handle_generate_circular_mission(conn, center_lat: float, center_lon: float, 
                                         radius_meters: float, num_points: int, altitude: float = 20.0) -> Dict[str, Any]:
    """Handle circular mission generation command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Validate parameters
        if not (-90 <= center_lat <= 90) or not (-180 <= center_lon <= 180):
            return {"status": "error", "detail": "invalid center coordinates"}
        
        if radius_meters <= 0 or radius_meters > 5000:
            return {"status": "error", "detail": "radius must be between 0 and 5000 meters"}
        
        if num_points < 3 or num_points > 50:
            return {"status": "error", "detail": "num_points must be between 3 and 50"}
        
        waypoints = controller.generate_circular_mission(center_lat, center_lon, radius_meters, num_points, altitude)
        
        return {
            "status": "ok", 
            "detail": f"generated circular mission with {len(waypoints)} waypoints",
            "waypoints": waypoints,
            "mission_type": "circular"
        }
    except Exception as e:
        return {"status": "error", "detail": f"circular mission generation exception: {e}"}


async def handle_waypoint_emergency_response(conn, prompt_id: str, choice: str) -> Dict[str, Any]:
    """Handle user response to waypoint battery emergency prompt."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        success = controller.handle_waypoint_emergency_response(prompt_id, choice)
        return {
            "status": "ok" if success else "error",
            "detail": f"emergency response {'recorded' if success else 'failed'}",
            "prompt_id": prompt_id,
            "choice": choice
        }
    except Exception as e:
        return {"status": "error", "detail": f"emergency response exception: {e}"}


# Add waypoint handlers to the command registry after all functions are defined
COMMAND_HANDLERS.update({
    "execute_waypoint_mission": handle_execute_waypoint_mission,
    "waypoint_mission_status": handle_waypoint_mission_status,
    "stop_waypoint_mission": handle_stop_waypoint_mission,
    "set_waypoint_override": handle_set_waypoint_override,
    "fly_to_waypoint": handle_fly_to_waypoint,
    "validate_waypoints": handle_validate_waypoints,
    "calculate_mission_stats": handle_calculate_mission_stats,
    "generate_grid_mission": handle_generate_grid_mission,
    "generate_circular_mission": handle_generate_circular_mission,
    "waypoint_emergency_response": handle_waypoint_emergency_response,
    "cancel_takeoff": handle_cancel_takeoff,
})