
import json
from typing import Any, Callable, Awaitable, Dict


async def handle_command(
    payload: Dict[str, Any],
    start_telemetry: Callable[[], Awaitable[None]],
    stop_telemetry: Callable[[], Awaitable[None]],
    reconnect_telemetry: Callable[[], Awaitable[None]],
    get_controller: Callable[[], Any],
    broadcast_to_clients: Callable[[str], Awaitable[None]],
    get_drone_connected: Callable[[], bool],
) -> Dict[str, Any]:

    t = str(payload.get("type", "")).lower()

    if t == "message":
        msg = payload.get("message", "")
        # Broadcast a normalized message object to connected websocket clients
        try:
            await broadcast_to_clients(json.dumps({"type": "message", "message": msg}))
            return {"status": "ok", "detail": "message broadcast"}
        except Exception as e:
            return {"status": "error", "detail": f"broadcast failed: {e}"}

    if t == "connect":
        # start telemetry loop
        await start_telemetry()
        return {"status": "ok", "detail": "telemetry started"}

    if t == "disconnect":
        await stop_telemetry()
        return {"status": "ok", "detail": "telemetry stopped"}

    if t == "reconnect":
        await reconnect_telemetry()
        return {"status": "ok", "detail": "telemetry reconnected"}

    if t == "status":
        return {"status": "ok", "drone_connected": get_drone_connected()}

    if t == "arm":
        controller = get_controller()
        if controller is None:
            return {"status": "error", "detail": "no controller available"}
        try:
            res = await controller.arm()
            return {"status": "ok" if res else "error", "detail": "armed" if res else "arm failed"}
        except Exception as e:
            return {"status": "error", "detail": f"arm exception: {e}"}

    if t == "disarm":
        controller = get_controller()
        if controller is None:
            return {"status": "error", "detail": "no controller available"}
        try:
            res = await controller.disarm()
            return {"status": "ok" if res else "error", "detail": "disarmed" if res else "disarm failed"}
        except Exception as e:
            return {"status": "error", "detail": f"disarm exception: {e}"}

    return {"status": "error", "detail": f"unknown command type: {t}"}
