# Command handlers for drone control operations


import json
import time
from typing import Dict, Any, Optional

# Global command tracking for conflict detection
_active_commands = {}
_last_command_time = {}
COMMAND_TIMEOUT = 30.0  # seconds


async def handle_connect(start_telemetry_func, conn) -> Dict[str, Any]:
    # Handle connect command
    try:
        await start_telemetry_func()
        controller = getattr(conn, "controller", None)
        drone_connected = controller is not None and controller.vehicle is not None
        
        if drone_connected:
            return {
                "status": "ok", 
                "detail": "drone connected successfully", 
                "drone_connected": True
            }
        else:
            return {"status": "error", "detail": "drone connection failed - no vehicle detected", "drone_connected": False}
            
    except Exception as e:
        return {"status": "error", "detail": f"connection failed: {str(e)}", "drone_connected": False}


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


async def handle_arm_and_takeoff(conn, altitude: float = 5.0) -> Dict[str, Any]:
    """Handle arm and takeoff command to prevent auto-disarm timeout."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        # Validate altitude
        if altitude <= 0 or altitude > 100:
            return {"status": "error", "detail": f"altitude must be between 0 and 100m (got {altitude}m)"}
        
        result = await controller.arm_and_takeoff(altitude)
        return {
            "status": "ok" if result else "error", 
            "detail": f"arm and takeoff to {altitude}m successful" if result else "arm and takeoff failed"
        }
    except Exception as e:
        return {"status": "error", "detail": f"arm and takeoff exception: {e}"}


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


async def handle_message(payload: dict, broadcast_func) -> Dict[str, Any]:
    # Handle message broadcast command
    try:
        msg = payload.get("message", "")
        await broadcast_func(json.dumps({"type": "message", "message": msg}))
        return {"status": "ok", "detail": "message broadcast"}
    except Exception as e:
        return {"status": "error", "detail": f"broadcast failed: {e}"}


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


async def handle_land(conn) -> Dict[str, Any]:
    """Handle land command - defaults to RTL for safety."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.land()  # Now defaults to RTL for safety
        return {"status": "ok" if result else "error", 
                "detail": "landing/RTL successful" if result else "landing/RTL failed"}
    except Exception as e:
        return {"status": "error", "detail": f"landing exception: {e}"}

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


async def handle_rtl(conn) -> Dict[str, Any]:
    """Handle return to launch command - return home and land."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.rtl()
        return {"status": "ok" if result else "error", 
                "detail": "return to launch successful" if result else "return to launch failed"}
    except Exception as e:
        return {"status": "error", "detail": f"RTL exception: {e}"}


async def handle_fly_timed(conn, altitude: float = 5.0, duration: float = 5.0) -> Dict[str, Any]:
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
            
        result = await controller.fly_timed_mission(altitude, duration)
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
}


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
        if not handler:
            return {"status": "error", "detail": f"unknown command: {command_type}"}
        
        if command_type == "connect":
            result = await handler(start_telemetry_func, conn)
        elif command_type == "disconnect":
            result = await handler(stop_telemetry_func, conn)
        elif command_type == "reconnect":
            result = await handler(reconnect_telemetry_func)
        elif command_type == "status":
            result = await handler(drone_connected)
        elif command_type in ["arm", "disarm", "emergency_disarm", "land", "rtl", "mission_status", "release_throttle", "emergency_land", "verify_home", "force_land_here"]:
            result = await handler(conn)
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
                try:
                    if "altitude" in payload:
                        altitude = float(payload["altitude"])
                    if "duration" in payload:
                        duration = float(payload["duration"])
                except (ValueError, TypeError):
                    return {"status": "error", "detail": "invalid altitude or duration parameter"}
            result = await handler(conn, altitude, duration)
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