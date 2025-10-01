import asyncio
import websockets
import json
from telemetry_data import TelemetryData
from connection import Connection
from controller import Controller
from config import DRONE_ID, TELEMETRY_INTERVAL, WS_HOST, WS_PORT
from command_handlers import execute_command

connected_clients = set()
telemetry_task = None
conn = None
drone_connected = False

async def register_client(ws):
    connected_clients.add(ws)
    print(f"Client connected. Total clients: {len(connected_clients)}")

async def unregister_client(ws):
    connected_clients.discard(ws)
    print(f"Client disconnected. Total clients: {len(connected_clients)}")

async def broadcast_to_clients(message: str):
    if connected_clients:
        await asyncio.gather(
            *(client.send(message) for client in connected_clients),
            return_exceptions=True
        )

async def start_telemetry():
    global telemetry_task, conn, drone_connected
    if telemetry_task:
        print("Telemetry already running")
        return

    conn = Connection()
    connected = await conn.connect("/dev/ttyACM0", 115200)
    if not connected or conn.vehicle is None:
        print("Failed to connect to vehicle")
        drone_connected = False
        return
    try:
        conn.controller = Controller(conn)
    except Exception as e:
        print(f"Failed to create controller: {e}")

    drone_connected = True
    print("Telemetry loop started – Drone connected")

    telemetry = TelemetryData(conn.vehicle)

    async def telemetry_loop():
        global drone_connected
        try:
            while True:
                data = await telemetry.snapshot()
                # Create telemetry event and broadcast directly to WebSocket clients
                event = {
                    "drone_id": DRONE_ID,
                    "event_type": "DATA",
                    "payload": data
                }
                await broadcast_to_clients(json.dumps(event))
                await asyncio.sleep(TELEMETRY_INTERVAL)
        except asyncio.CancelledError:
            print("Telemetry loop cancelled")
        finally:
            drone_connected = False
            print("Telemetry loop stopped – Drone disconnected")

    telemetry_task = asyncio.create_task(telemetry_loop())

async def stop_telemetry():
    global telemetry_task, conn, drone_connected
    if telemetry_task:
        telemetry_task.cancel()
        try:
            await telemetry_task
        except asyncio.CancelledError:
            pass
        telemetry_task = None
    if conn:
        await conn.disconnect()
        conn = None
    drone_connected = False
    print("Telemetry stopped – Drone disconnected")

async def reconnect_telemetry():
    await stop_telemetry()
    await start_telemetry()

async def handle_message(message: str, ws) -> None:
    """Handle incoming message and send appropriate response."""
    
    # Try to parse as JSON first
    try:
        payload = json.loads(message)
        command_type = str(payload.get("type", "")).lower()
        message_id = payload.get("id")
    except json.JSONDecodeError:
        # Legacy text command
        command_type = message.lower()
        payload = None
        message_id = None
    
    # Execute command using the command handler
    response = await execute_command(
        command_type=command_type,
        payload=payload,
        conn=conn,
        drone_connected=drone_connected,
        start_telemetry_func=start_telemetry,
        stop_telemetry_func=stop_telemetry,
        reconnect_telemetry_func=reconnect_telemetry,
        broadcast_func=broadcast_to_clients
    )
    
    # Add message ID if provided for correlation
    if message_id is not None and response:
        response["id"] = message_id
    
    # Send response
    if response:
        await ws.send(json.dumps(response))


async def ws_handler(ws):
    await register_client(ws)
    try:
        async for message in ws:
            await handle_message(message, ws)
    finally:
        await unregister_client(ws)


async def start_ws_server():
    server = await websockets.serve(ws_handler, WS_HOST, WS_PORT)
    print(f"Python WS server running at ws://{WS_HOST}:{WS_PORT}")

    try:
        await asyncio.Future()
    finally:
        print("Shutting down server...")
        await stop_telemetry()
        server.close()
        await server.wait_closed()
        print("Server shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(start_ws_server())
    except KeyboardInterrupt:
        print("Server shutdown requested by user")
    except Exception as e:
        print(f"Server error: {e}")
