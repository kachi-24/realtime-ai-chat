from fastapi import HTTPException
from rate_limiter import check_rate_limit


async def check_login_rate_limit(identifier: str):
    allowed, remaining = await check_rate_limit(
        key=f"login:{identifier}",
        limit=5,
        window_seconds=60,
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
            headers={
                "Retry-After": "60",
            },
        )

    return remaining


async def check_register_rate_limit(identifier: str):
    allowed, remaining = await check_rate_limit(
        key=f"register:{identifier}",
        limit=3,
        window_seconds=60 * 60,
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts. Please try again later.",
            headers={
                "Retry-After": "3600",
            },
        )

    return remaining