import asyncio
from dronekit import connect

class Connection:
    def __init__(self):
        self.vehicle = None
        self.is_connected = False
        self.initial_heartbeat = None
        self.last_heartbeat = None
        self.monitoring = False
        self.monitor_task = None

    async def connect(self, connection_string, baud_rate):
        if self.vehicle is not None:
            print("Vehicle already connected.")
            return True
        try:
            print(f"Connecting to vehicle on {connection_string} with baud {baud_rate}...")
            self.vehicle = await asyncio.to_thread(connect, connection_string, baud=baud_rate, wait_ready=True)
            self.is_connected = True
            print("Vehicle connected successfully.")
            # Start heartbeat monitor
            started = await self.start_heartbeat_monitor()
            if not started:
                print("Failed to start heartbeat monitor.")
                await self.disconnect()
                return False
            return True
        except KeyboardInterrupt:
            print("Connection interrupted by user.")
            return False
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
        
        
    async def disconnect(self):
        try:
            if self.vehicle:
                print("Disconnecting from vehicle...")
                self.vehicle.close()
                self.vehicle = None
                self.is_connected = False
                await self.stop_heartbeat_monitor()
                print("Vehicle disconnected.")
                return True
            else:
                print("No vehicle to disconnect.")
                return False
        except Exception as e:
            print(f"Disconnection failed: {e}")
            return False

    async def start_heartbeat_monitor(self, interval=1):
        if self.monitoring:
            print("Heartbeat monitor already running.")
            return True
        self.monitoring = True

        async def monitor():
            while self.monitoring and self.vehicle:
                self.last_heartbeat = getattr(self.vehicle, "last_heartbeat", None)
                if self.initial_heartbeat is None:
                    self.initial_heartbeat = self.last_heartbeat
                print(f"[Heartbeat] {self.last_heartbeat}")
                await asyncio.sleep(interval)

        self.monitor_task = asyncio.create_task(monitor())
        return True

    async def stop_heartbeat_monitor(self):
        if not self.monitoring:
            return True
        self.monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                print("Heartbeat monitor task cancelled.")
            self.monitor_task = None
        print("Heartbeat monitor stopped.")
        return True

    # async def get_vehicle_status(self):
    #     if not self.vehicle:
    #         print("No vehicle connected.")
    #         return None
    #     status = {
    #         "is_connected": self.is_connected,
    #         "last_heartbeat": self.last_heartbeat,
    #         "initial_heartbeat": self.initial_heartbeat,
    #         # "location": getattr(self.vehicle.location, "global_frame", None),
    #         "attitude": getattr(self.vehicle, "attitude", None),
    #         "battery": getattr(self.vehicle, "battery", None),
    #         # "mode": getattr(self.vehicle.mode, "name", None),
    #     }
    #     return status


# if __name__ == "__main__":
#     async def main():
#         conn = Connection()
#         connected = await conn.connect("/dev/ttyACM0", 115200)
#         if not connected:
#             print("Failed to connect to vehicle.")
#             return
#         await asyncio.sleep(10)  # Keep connection for 10 seconds
#         await conn.disconnect()

#     asyncio.run(main())