from fastapi import Header, HTTPException

from auth import decode_access_token


async def get_current_user_id(
    authorization: str | None = Header(default=None),
):

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    token = authorization.split(
        " ",
        1,
    )[1]

    try:
        user_id = decode_access_token(token)

        return user_id

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )