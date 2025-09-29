import asyncio
import websockets
from .telemetry_pub import AsyncTelemetryPublisher
from telemetry_data import TelemetryData
from connection import Connection
from controller import Controller
from config import DRONE_ID, TELEMETRY_INTERVAL, WS_HOST, WS_PORT, REDIS_HOST, REDIS_PORT, REDIS_CHANNEL
from .redis_subscriber import RedisSubscriber
from . import commands
import json

connected_clients = set()
telemetry_task = None
redis_subscriber = None
conn = None
publisher = None
drone_connected = False
stop_redis_listener = False

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
    global telemetry_task, conn, publisher, drone_connected
    if telemetry_task:
        print("Telemetry already running")
        return

    conn = Connection()
    connected = await conn.connect("/dev/ttyACM0", 115200)
    if not connected or conn.vehicle is None:
        print("Failed to connect to vehicle")
        drone_connected = False
        return

    # Attach a Controller instance to the connection so command handlers can
    # access arm/disarm functionality via conn.controller
    try:
        conn.controller = Controller(conn)
    except Exception as e:
        print(f"Failed to create controller: {e}")

    drone_connected = True
    print("Telemetry loop started – Drone connected")

    telemetry = TelemetryData(conn.vehicle)
  
    publisher = AsyncTelemetryPublisher(DRONE_ID, REDIS_HOST, REDIS_PORT, REDIS_CHANNEL)
    await publisher.connect()

    async def telemetry_loop():
        global drone_connected
        try:
            while True:
                data = await telemetry.snapshot()
                await publisher.publish("DATA", data)
                await asyncio.sleep(TELEMETRY_INTERVAL)
        except asyncio.CancelledError:
            print("Telemetry loop cancelled")
        finally:
            drone_connected = False
            print("Telemetry loop stopped – Drone disconnected")

    telemetry_task = asyncio.create_task(telemetry_loop())

async def stop_telemetry():
    global telemetry_task, conn, publisher, drone_connected
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
    if publisher:
        await publisher.close()
        publisher = None
    drone_connected = False
    print("Telemetry stopped – Drone disconnected")

async def reconnect_telemetry():
    await stop_telemetry()
    await start_telemetry()

async def ws_handler(ws):
    await register_client(ws)
    try:
        async for message in ws:
            # Attempt to parse JSON command payloads first. If parsing fails,
            # fall back to simple text commands for backward compatibility.
            try:
                payload = json.loads(message)
                resp = await commands.handle_command(
                    payload,
                    start_telemetry=start_telemetry,
                    stop_telemetry=stop_telemetry,
                    reconnect_telemetry=reconnect_telemetry,
                    get_controller=lambda: getattr(conn, "controller", None),
                    broadcast_to_clients=broadcast_to_clients,
                    get_drone_connected=lambda: drone_connected,
                )
                await ws.send(json.dumps(resp))
                continue
            except json.JSONDecodeError:
                # Not JSON — fall through to legacy text handling
                pass

            cmd = message.lower()
            if cmd == "connect":
                await start_telemetry()
                await ws.send("Telemetry started – Drone connected")
            elif cmd == "arm":
                # Legacy text command: delegate to the JSON command handler for consistency
                resp = await commands.handle_command(
                    {"type": "arm"},
                    start_telemetry=start_telemetry,
                    stop_telemetry=stop_telemetry,
                    reconnect_telemetry=reconnect_telemetry,
                    get_controller=lambda: getattr(conn, "controller", None),
                    broadcast_to_clients=broadcast_to_clients,
                    get_drone_connected=lambda: drone_connected,
                )
                await ws.send(json.dumps(resp))
            elif cmd == "disconnect":
                await stop_telemetry()
                await ws.send("Telemetry stopped – Drone disconnected")
            elif cmd == "disarm":
                # Legacy text command: delegate to the JSON command handler for consistency
                resp = await commands.handle_command(
                    {"type": "disarm"},
                    start_telemetry=start_telemetry,
                    stop_telemetry=stop_telemetry,
                    reconnect_telemetry=reconnect_telemetry,
                    get_controller=lambda: getattr(conn, "controller", None),
                    broadcast_to_clients=broadcast_to_clients,
                    get_drone_connected=lambda: drone_connected,
                )
                await ws.send(json.dumps(resp))
            elif cmd == "reconnect":
                await reconnect_telemetry()
                await ws.send("Telemetry reconnected – Drone connected")
            elif cmd == "status":
                status_msg = "Drone connected" if drone_connected else "Drone disconnected"
                await ws.send(status_msg)
    finally:
        await unregister_client(ws)


async def start_ws_server():
    global redis_subscriber
    server = await websockets.serve(ws_handler, WS_HOST, WS_PORT)
    print(f"Python WS server running at ws://{WS_HOST}:{WS_PORT}")

    redis_subscriber = RedisSubscriber(broadcast_to_clients)
    await redis_subscriber.start()

    try:
        await asyncio.Future()
    finally:
        print("Shutting down server...")
        if redis_subscriber:
            await redis_subscriber.stop()
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
