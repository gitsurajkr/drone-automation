import json
import redis.asyncio as aioredis

class AsyncTelemetryPublisher:
    def __init__(self, drone_id: str, host: str, port: int, channel: str):
        self.drone_id = drone_id
        self.channel = channel
        self.redis = aioredis.Redis(host=host, port=port, decode_responses=True)
        self.connected = False

    async def connect(self):
        if not self.connected:
            try:
                await self.redis.ping()
                self.connected = True
                print(f"Connected to Redis at {self.redis.connection_pool.connection_kwargs['host']}:{self.redis.connection_pool.connection_kwargs['port']}")
            except Exception as e:
                print(f"Failed to connect to Redis: {e}")
                self.connected = False

    async def publish(self, event_type: str, payload: dict):
        if not self.connected:
            await self.connect()
        if not self.connected:
            return
        event = {
            "drone_id": self.drone_id,
            "event_type": event_type,
            "payload": payload
        }
        try:
            await self.redis.publish(self.channel, json.dumps(event))
        except Exception as e:
            print(f"Failed to publish telemetry: {e}")

    async def close(self):
        if self.connected:
            await self.redis.close()
            self.connected = False
            print("Redis connection closed.")



# flow connection send data to redis (publish data) -> ws py subscribe on redis get the data and -> nodejs backend connect with ws and get the data  ->done 

# connection logic -> frontend (connect)-> backend send ("Connect") to python ws -> python ws ("send connect with i guess some function to redis but redis is just broadcast message (confusion) -> flight controller") 

# look at this today 
# Today task 
# connect with backend and get the data to console and send some request like connect disconnect and if connected automatic message start flow
#  