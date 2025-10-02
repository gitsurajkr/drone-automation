# Command handlers for drone control operations


import json
from typing import Dict, Any, Optional


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


async def handle_land(conn) -> Dict[str, Any]:
    """Handle land command - safely land at current location."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.land()
        return {"status": "ok" if result else "error", 
                "detail": "landing successful" if result else "landing failed"}
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


# Command registry - maps command types to their handlers
COMMAND_HANDLERS = {
    "connect": handle_connect,
    "disconnect": handle_disconnect,
    "reconnect": handle_reconnect,
    "status": handle_status,
    "arm": handle_arm,
    "disarm": handle_disarm,
    "emergency_disarm": handle_emergency_disarm,
    "sitl_setup": handle_sitl_setup,
    "message": handle_message,
    "takeoff": handle_takeoff,
    "land": handle_land,
    "rtl": handle_rtl,  
    "fly_timed": handle_fly_timed,
    "mission_status": handle_mission_status,
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
    # Execute the command based on its type
    handler = COMMAND_HANDLERS.get(command_type)
    if not handler:
        return {"status": "error", "detail": f"unknown command: {command_type}"}
    
    if command_type == "connect":
        return await handler(start_telemetry_func, conn)
    elif command_type == "disconnect":
        return await handler(stop_telemetry_func, conn)
    elif command_type == "reconnect":
        return await handler(reconnect_telemetry_func)
    elif command_type == "status":
        return await handler(drone_connected)
    elif command_type in ["arm", "disarm", "emergency_disarm", "sitl_setup", "land", "rtl", "mission_status"]:
        return await handler(conn)
    elif command_type == "takeoff":
        # Handle takeoff with optional altitude parameter
        altitude = 10.0  # default altitude
        if payload and "altitude" in payload:
            try:
                altitude = float(payload["altitude"])
            except (ValueError, TypeError):
                return {"status": "error", "detail": "invalid altitude parameter"}
        return await handler(conn, altitude)
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
        return await handler(conn, altitude, duration)
    elif command_type == "message":
        return await handler(payload, broadcast_func)
    else:
        return {"status": "error", "detail": f"handler not implemented for: {command_type}"}