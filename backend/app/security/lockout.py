from fastapi import HTTPException
from redis.asyncio.client import Redis
from app.core.config import get_settings


def _key(identifier: str) -> str:
    return f"lockout:{identifier}"


async def check_lockout(redis_client: Redis, identifier: str) -> None:
    settings = get_settings()
    count = await redis_client.get(_key(identifier))
    if not count:
        return
    if int(count) >= settings.lockout_threshold:
        raise HTTPException(status_code=429, detail="Too many failed attempts. Try again in a few minutes.")


async def record_failed_attempt(redis_client: Redis, identifier: str) -> None:
    settings = get_settings()
    key = _key(identifier)
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, settings.lockout_minutes * 60)


async def clear_attempts(redis_client: Redis, identifier: str) -> None:
    await redis_client.delete(_key(identifier))
