"""
Command handlers for drone control operations.
"""
import json
from typing import Dict, Any, Optional


async def handle_connect(start_telemetry_func) -> Dict[str, Any]:
    # Handle connect command
    await start_telemetry_func()
    return {"status": "ok", "detail": "telemetry started"}


async def handle_disconnect(stop_telemetry_func) -> Dict[str, Any]:
    # Handle disconnect command
    await stop_telemetry_func()
    return {"status": "ok", "detail": "telemetry stopped"}


async def handle_reconnect(reconnect_telemetry_func) -> Dict[str, Any]:
    # Handle reconnect command
    await reconnect_telemetry_func()
    return {"status": "ok", "detail": "telemetry reconnected"}


async def handle_status(drone_connected: bool) -> Dict[str, Any]:
    # Handle status command
    return {"status": "ok", "drone_connected": drone_connected}


async def handle_arm(conn) -> Dict[str, Any]:
    """Handle arm command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.arm()
        return {"status": "ok" if result else "error", "detail": "armed" if result else "arm failed"}
    except Exception as e:
        return {"status": "error", "detail": f"arm exception: {e}"}


async def handle_disarm(conn) -> Dict[str, Any]:
    """Handle disarm command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.disarm()
        return {"status": "ok" if result else "error", "detail": "disarmed" if result else "disarm failed"}
    except Exception as e:
        return {"status": "error", "detail": f"disarm exception: {e}"}


async def handle_message(payload: dict, broadcast_func) -> Dict[str, Any]:
    """Handle message broadcast command."""
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
    
    # Add takeoff logic here when implementing
    return {"status": "info", "detail": f"takeoff to {altitude}m not yet implemented"}


async def handle_land(conn) -> Dict[str, Any]:
    """Handle land command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    # Add landing logic here when implementing
    return {"status": "info", "detail": "land command not yet implemented"}


async def handle_emergency_disarm(conn) -> Dict[str, Any]:
    # Handle emergency disarm command - bypasses safety checks
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    try:
        result = await controller.emergency_disarm()
        return {"status": "ok" if result else "error", "detail": "emergency disarmed" if result else "emergency disarm failed"}
    except Exception as e:
        return {"status": "error", "detail": f"emergency disarm exception: {e}"}


async def handle_rtl(conn) -> Dict[str, Any]:
    """Handle return to launch command."""
    controller = getattr(conn, "controller", None)
    if controller is None:
        return {"status": "error", "detail": "no controller available"}
    
    # Add RTL logic here when implementing
    return {"status": "info", "detail": "return to launch not yet implemented"}


# Command registry - maps command types to their handlers
COMMAND_HANDLERS = {
    "connect": handle_connect,
    "disconnect": handle_disconnect,
    "reconnect": handle_reconnect,
    "status": handle_status,
    "arm": handle_arm,
    "disarm": handle_disarm,
    "emergency_disarm": handle_emergency_disarm,  # Emergency safety command
    "message": handle_message,
    "takeoff": handle_takeoff,
    "land": handle_land,
    "rtl": handle_rtl,  
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
        return await handler(start_telemetry_func)
    elif command_type == "disconnect":
        return await handler(stop_telemetry_func)
    elif command_type == "reconnect":
        return await handler(reconnect_telemetry_func)
    elif command_type == "status":
        return await handler(drone_connected)
    elif command_type in ["arm", "disarm", "emergency_disarm", "takeoff", "land", "rtl"]:
        return await handler(conn)
    elif command_type == "message":
        return await handler(payload, broadcast_func)
    else:
        return {"status": "error", "detail": f"handler not implemented for: {command_type}"}