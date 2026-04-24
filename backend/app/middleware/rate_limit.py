from fastapi import HTTPException
from redis.asyncio.client import Redis


async def enforce_rate_limit(
    redis_client: Redis,
    bucket: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> None:
    key = f"rate:{bucket}:{identifier}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window_seconds)
    if count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
