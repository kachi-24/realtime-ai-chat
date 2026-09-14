import hashlib
import os
import secrets

from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from fastapi import Header, HTTPException
from jose import JWTError, jwt
from pwdlib import PasswordHash


load_dotenv()


SECRET_KEY = os.getenv("JWT_SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not configured"
    )


ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "15",
    )
)

REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.getenv(
        "REFRESH_TOKEN_EXPIRE_DAYS",
        "30",
    )
)

EMAIL_VERIFICATION_EXPIRE_HOURS = int(
    os.getenv(
        "EMAIL_VERIFICATION_EXPIRE_HOURS",
        "24",
    )
)


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(
    password: str,
    hashed_password: str,
) -> bool:
    return password_hash.verify(
        password,
        hashed_password,
    )


def hash_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def create_access_token(user_id: str) -> str:

    expire = (
        datetime.now(timezone.utc)
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    payload = {
        "sub": user_id,
        "type": "access",
        "exp": expire,
    }

    return jwt.encode(
        payload,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> str:

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        if payload.get("type") != "access":
            raise HTTPException(
                status_code=401,
                detail="Invalid token type",
            )

        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token",
            )

        return user_id

    except JWTError:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
        )


def create_email_verification_token():

    raw_token = secrets.token_urlsafe(48)

    expires_at = (
        datetime.utcnow()
        + timedelta(
            hours=EMAIL_VERIFICATION_EXPIRE_HOURS
        )
    )

    return raw_token, expires_at


def create_refresh_token():

    raw_token = secrets.token_urlsafe(64)

    expires_at = (
        datetime.utcnow()
        + timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        )
    )

    return raw_token, expires_at


async def get_current_user_id(
    authorization: str | None = Header(None),
) -> str:

    if not authorization:

        raise HTTPException(
            status_code=401,
            detail="Authorization header required",
        )

    if not authorization.startswith(
        "Bearer "
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    token = authorization.replace(
        "Bearer ",
        "",
        1,
    )

    return decode_access_token(token)