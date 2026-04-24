import asyncio
import ast
from app.core.redis import init_redis
from app.services.mail_service import send_email


async def run_worker(poll_interval: float = 1.0) -> None:
    redis_client = await init_redis()
    while True:
        _, raw = await redis_client.blpop("queue:emails", timeout=5)
        if not raw:
            await asyncio.sleep(poll_interval)
            continue
        task = ast.literal_eval(raw)
        payload = task.get("payload", {})
        await send_email(payload.get("to", ""), payload.get("subject", ""), payload.get("html", ""))


if __name__ == "__main__":
    asyncio.run(run_worker())
