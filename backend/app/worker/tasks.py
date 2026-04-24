from datetime import datetime, timezone
from redis.asyncio.client import Redis


async def enqueue_email_task(redis_client: Redis, payload: dict) -> str:
    task_id = payload.get("task_id") or f"mail_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    task = {"task_id": task_id, "payload": payload, "created_at": datetime.now(timezone.utc).isoformat()}
    await redis_client.rpush("queue:emails", str(task))
    return task_id
