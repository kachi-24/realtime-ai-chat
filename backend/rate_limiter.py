from redis_client import redis_client

# --------------------------------------------------------
# Generic rate limiter used by login, register, upload,
# search, and WebSocket messages.
#
# Uses a fixed-window counter: the first request for a
# given key starts a window of `window_seconds` and sets
# it to expire automatically. Every request within that
# window increments the same counter. Once the window
# expires, Redis drops the key and the next request
# starts a fresh window.
# --------------------------------------------------------


async def check_rate_limit(
    key: str,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """
    Returns (allowed, remaining):
      - allowed: False if the caller has exceeded `limit`
        requests within the current window.
      - remaining: how many requests are left in the
        current window (0 if not allowed).
    """

    rate_limit_key = f"rate_limit:{key}"

    current_count = await redis_client.incr(
        rate_limit_key
    )

    # Only the request that actually creates the counter
    # (count == 1) sets the expiry, so later requests
    # don't keep pushing the window back.
    if current_count == 1:
        await redis_client.expire(
            rate_limit_key,
            window_seconds,
        )

    if current_count > limit:
        return False, 0

    remaining = limit - current_count

    return True, remaining