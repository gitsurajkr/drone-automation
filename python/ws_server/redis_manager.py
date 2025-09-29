import redis.asyncio as aioredis
import asyncio

class RedisManager:
    def __init__(self, host, port, channel):
        self.host = host
        self.port = port
        self.channel = channel
        self.redis = aioredis.Redis(host=host, port=port, decode_responses=True)
        self.pubsub = None

    async def publish(self, message):
        await self.redis.publish(self.channel, message)

    async def subscribe(self, on_message):
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(self.channel)
        print(f"Subscribed to Redis channel: {self.channel}")
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    await on_message(message["data"])
        except asyncio.CancelledError:
            print("Redis subscription cancelled.")
        finally:
            try:
                await self.pubsub.unsubscribe(self.channel)
            except Exception as e:
                print(f"Error unsubscribing: {e}")
            try:
                await self.pubsub.close()
                await self.redis.close()
            except Exception as e:
                print(f"Error closing Redis: {e}")
