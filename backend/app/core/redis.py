import fakeredis.aioredis
import redis.asyncio as redis
from redis.asyncio.client import Redis
from .config import get_settings

_client: Redis | None = None


async def init_redis() -> Redis:
    global _client
    if _client is None:
        settings = get_settings()
        if settings.redis_url.startswith("fakeredis://"):
            _client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        else:
            _client = redis.from_url(settings.redis_url, decode_responses=True)
    await _client.ping()
    return _client


def get_redis() -> Redis:
    if _client is None:
        raise RuntimeError("Redis client is not initialized")
    return _client


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None
