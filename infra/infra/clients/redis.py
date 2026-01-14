import os
from typing import Any, Optional


class RedisClient:
    def __init__(self, url: Optional[str] = None):
        self._url = url or os.environ.get("REDIS_URL", "redis://localhost:6379")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import redis.asyncio as redis
            except ImportError:
                raise ImportError("redis package required. Install with: pip install redis")

            self._client = redis.from_url(self._url)
        return self._client

    async def get(self, key: str) -> Optional[str]:
        client = self._get_client()
        result = await client.get(key)
        return result.decode("utf-8") if result else None

    async def set(
        self,
        key: str,
        value: str,
        ex: Optional[int] = None,
        px: Optional[int] = None,
    ) -> bool:
        client = self._get_client()
        return await client.set(key, value, ex=ex, px=px)

    async def delete(self, *keys: str) -> int:
        client = self._get_client()
        return await client.delete(*keys)

    async def exists(self, *keys: str) -> int:
        client = self._get_client()
        return await client.exists(*keys)

    async def expire(self, key: str, seconds: int) -> bool:
        client = self._get_client()
        return await client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        client = self._get_client()
        return await client.ttl(key)

    async def incr(self, key: str) -> int:
        client = self._get_client()
        return await client.incr(key)

    async def hget(self, name: str, key: str) -> Optional[str]:
        client = self._get_client()
        result = await client.hget(name, key)
        return result.decode("utf-8") if result else None

    async def hset(self, name: str, key: str, value: str) -> int:
        client = self._get_client()
        return await client.hset(name, key, value)

    async def hgetall(self, name: str) -> dict[str, str]:
        client = self._get_client()
        result = await client.hgetall(name)
        return {k.decode("utf-8"): v.decode("utf-8") for k, v in result.items()}

    async def lpush(self, key: str, *values: str) -> int:
        client = self._get_client()
        return await client.lpush(key, *values)

    async def rpush(self, key: str, *values: str) -> int:
        client = self._get_client()
        return await client.rpush(key, *values)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        client = self._get_client()
        result = await client.lrange(key, start, end)
        return [item.decode("utf-8") for item in result]

    async def sadd(self, key: str, *values: str) -> int:
        client = self._get_client()
        return await client.sadd(key, *values)

    async def smembers(self, key: str) -> set[str]:
        client = self._get_client()
        result = await client.smembers(key)
        return {item.decode("utf-8") for item in result}

    async def sismember(self, key: str, value: str) -> bool:
        client = self._get_client()
        return await client.sismember(key, value)

    async def execute_command(self, *args: Any, **kwargs: Any) -> Any:
        client = self._get_client()
        return await client.execute_command(*args, **kwargs)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def __aenter__(self) -> "RedisClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
