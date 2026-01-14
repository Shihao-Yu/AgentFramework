from typing import Optional, List, Tuple
import logging
import json
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional["RedisClient"] = None
_redis_init_lock: Optional[asyncio.Lock] = None


def _get_init_lock() -> asyncio.Lock:
    """Get or create the initialization lock (must be called from async context)."""
    global _redis_init_lock
    if _redis_init_lock is None:
        _redis_init_lock = asyncio.Lock()
    return _redis_init_lock


class RedisClient:
    
    def __init__(self):
        self._client = None
        self._sentinel = None
    
    async def connect(self) -> bool:
        try:
            import redis.asyncio as redis
            from redis.asyncio.sentinel import Sentinel
        except ImportError:
            logger.warning("redis package not installed. Graph caching disabled.")
            return False
        
        if not settings.REDIS_SENTINEL_HOSTS:
            logger.info("REDIS_SENTINEL_HOSTS not configured. Graph caching disabled.")
            return False
        
        try:
            sentinel_hosts = self._parse_sentinel_hosts(settings.REDIS_SENTINEL_HOSTS)
            
            self._sentinel = Sentinel(
                sentinel_hosts,
                socket_timeout=5.0,
                password=settings.REDIS_PASSWORD,
            )
            
            self._client = self._sentinel.master_for(
                settings.REDIS_SENTINEL_MASTER,
                socket_timeout=5.0,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
            )
            
            await self._client.ping()
            logger.info(f"Connected to Redis Sentinel master '{settings.REDIS_SENTINEL_MASTER}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Redis Sentinel: {e}")
            self._client = None
            self._sentinel = None
            return False
    
    def _parse_sentinel_hosts(self, hosts_str: str) -> List[Tuple[str, int]]:
        result = []
        for host_port in hosts_str.split(","):
            host_port = host_port.strip()
            if ":" in host_port:
                host, port = host_port.rsplit(":", 1)
                result.append((host, int(port)))
            else:
                result.append((host_port, 26379))
        return result
    
    @property
    def is_connected(self) -> bool:
        return self._client is not None
    
    async def get(self, key: str) -> Optional[bytes]:
        if not self._client:
            return None
        try:
            return await self._client.get(key)
        except Exception as e:
            logger.warning(f"Redis GET failed for {key}: {e}")
            return None
    
    async def set(self, key: str, value: bytes, ttl: Optional[int] = None) -> bool:
        if not self._client:
            return False
        try:
            if ttl:
                await self._client.setex(key, ttl, value)
            else:
                await self._client.set(key, value)
            return True
        except Exception as e:
            logger.warning(f"Redis SET failed for {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        if not self._client:
            return False
        try:
            await self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis DELETE failed for {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        if not self._client:
            return 0
        try:
            cursor = 0
            deleted = 0
            while True:
                cursor, keys = await self._client.scan(cursor, match=pattern, count=100)
                if keys:
                    await self._client.delete(*keys)
                    deleted += len(keys)
                if cursor == 0:
                    break
            return deleted
        except Exception as e:
            logger.warning(f"Redis DELETE pattern failed for {pattern}: {e}")
            return 0
    
    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None
            self._sentinel = None


async def get_redis_client() -> RedisClient:
    """Get or create the Redis client singleton with thread-safe initialization."""
    global _redis_client
    
    # Fast path: client already initialized
    if _redis_client is not None:
        return _redis_client
    
    # Slow path: acquire lock and double-check
    async with _get_init_lock():
        # Double-check after acquiring lock
        if _redis_client is None:
            client = RedisClient()
            await client.connect()
            _redis_client = client
    
    return _redis_client


async def close_redis_client():
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
