import os
from pathlib import Path

from dotenv import load_dotenv
import redis.asyncio as redis

# Same reasoning as database.py: resolve .env relative to this
# file's location so it's found regardless of which directory
# you run from.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not configured")

redis_client = redis.from_url(
    REDIS_URL,
    decode_responses=True,
)


async def test_redis():
    response = await redis_client.ping()
    return response