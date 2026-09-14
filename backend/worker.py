import os

import redis
import sentry_sdk
from dotenv import load_dotenv
from rq import Queue, Worker
from sentry_sdk.integrations.rq import RqIntegration


# ---------------------------------------------------------
# Load environment variables
# ---------------------------------------------------------

load_dotenv()


# ---------------------------------------------------------
# Sentry
# ---------------------------------------------------------
#
# .strip() guards against a SENTRY_DSN that's present in the
# environment but empty or whitespace-only (e.g. `SENTRY_DSN=`
# with nothing after the `=` in an env_file) — Docker's
# env_file loading doesn't drop keys with empty values the way
# you might expect, so os.getenv() can return "" or " " rather
# than None, and a bare `if SENTRY_DSN:` check on an unstripped
# whitespace string would still evaluate truthy. This does NOT
# protect against a non-empty placeholder like "YOUR_SENTRY_DSN"
# — that's still a truthy, non-blank string, so it's on the
# .env.docker file itself to leave SENTRY_DSN unset (or filled
# with a real DSN) rather than templated placeholder text.
# ---------------------------------------------------------

SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("ENVIRONMENT", "development"),
        integrations=[
            RqIntegration(),
        ],
        traces_sample_rate=float(
            os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")
        ),
    )

    print("Sentry initialized for RQ worker")
else:
    print("Sentry disabled: SENTRY_DSN is not configured")


# ---------------------------------------------------------
# Redis configuration
# ---------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise RuntimeError("REDIS_URL is not configured")


redis_connection = redis.from_url(REDIS_URL)


# ---------------------------------------------------------
# RQ queue
# ---------------------------------------------------------

queue = Queue(
    "document-processing",
    connection=redis_connection,
)


# ---------------------------------------------------------
# Worker
# ---------------------------------------------------------

print(
    f"Starting document-processing worker "
    f"(Redis: {REDIS_URL}, queue: document-processing)"
)

worker = Worker(
    [queue],
    connection=redis_connection,
)

worker.work()