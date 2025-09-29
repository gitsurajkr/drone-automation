import asyncio
from ws_server.ws_server import start_ws_server
from config import WS_HOST, WS_PORT

async def main():
    print(f"Starting WebSocket server at ws://{WS_HOST}:{WS_PORT}...")
    await start_ws_server()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server shutdown requested by user.")
    except Exception as e:
        print(f"Server encountered an error: {e}")