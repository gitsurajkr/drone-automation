import asyncio
from .redis_manager import RedisManager
from config import REDIS_HOST, REDIS_PORT, REDIS_CHANNEL

class RedisSubscriber:
    def __init__(self, broadcast_callback):
        self.manager = RedisManager(REDIS_HOST, REDIS_PORT, REDIS_CHANNEL)
        self.broadcast_callback = broadcast_callback
        self.task = None

    async def start(self):
        self.task = asyncio.create_task(self.manager.subscribe(self.broadcast_callback))

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None
