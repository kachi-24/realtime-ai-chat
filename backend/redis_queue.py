import os
from pathlib import Path

from dotenv import load_dotenv
import redis
from rq import Queue

# Same reasoning as redis_client.py / database.py: resolve .env
# relative to this file's location so it's found regardless of
# working directory, and read REDIS_URL from the environment
# instead of hardcoding it. A hardcoded "localhost:6381" only
# ever worked when this ran directly on the Windows host —
# inside a container, "localhost" refers to the container
# itself, not the host machine, so it silently pointed at
# nothing.
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not configured")

redis_connection = redis.from_url(
    REDIS_URL,
    decode_responses=False,
)

document_queue = Queue(
    "document-processing",
    connection=redis_connection,
)