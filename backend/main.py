import asyncio
import json
import logging
import os
import traceback
import uuid
from datetime import datetime
from pathlib import Path

import httpx
import sentry_sdk
import uvicorn
from dotenv import load_dotenv

# ============================================================
# Load environment variables FIRST, before any local module
# import below. auth.py (and possibly others) read env vars
# like JWT_SECRET_KEY at import time and raise immediately if
# they're missing — if load_dotenv() ran after those imports
# (as it used to, further down this file), it would always be
# too late: Python executes imports top-to-bottom, so the .env
# file needs to be loaded before `from auth import ...` etc.
# ever run, regardless of what the .env file actually contains.
#
# The .env file lives at the project root (one level up from
# this file, in backend/), NOT inside backend/ itself. Plain
# load_dotenv() only looks in the current working directory,
# so it silently found nothing whenever this was launched with
# `python main.py` from inside backend/ — same failure either
# way, just depending on which folder you happened to be in.
# Resolving the path relative to this file's own location
# makes it work no matter which directory you run it from.
# ============================================================
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)

from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import (
    AsyncSessionLocal,
    get_db,
)

from models import (
    User,
    EmailVerificationToken,
    RefreshToken,
    Conversation,
    Document,
    DocumentChunk,
    Message,
)

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    create_email_verification_token,
    create_refresh_token,
    hash_token,
)

from email_service import send_verification_email
from dependencies import get_current_user_id

from rag.embeddings import create_embedding
from rag.retriever import retrieve_chunks
from rag.prompt import build_rag_prompt

# IMPORTANT:
# queue.py was renamed to redis_queue.py
# because queue.py conflicts with Python's
# built-in queue module.
from redis_queue import document_queue

from jobs.document_jobs import (
    process_document_sync,
)

from cache import (
    get_cached_retrieval,
    cache_retrieval,
)

from rate_limiter import check_rate_limit
from redis_client import redis_client

# ============================================================
# ERROR MONITORING
# ============================================================
# (load_dotenv() already ran at the top of this file, before
# the local module imports above — see the comment there.)

SENTRY_DSN = os.getenv("SENTRY_DSN", "").strip()

if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv(
            "ENVIRONMENT",
            "development",
        ),
        traces_sample_rate=float(
            os.getenv(
                "SENTRY_TRACES_SAMPLE_RATE",
                "0.1",
            )
        ),
    )

logger = logging.getLogger("uvicorn.error")

# ============================================================
# ENVIRONMENT
# ============================================================
#
# Drives environment-specific behavior (currently just CORS
# below) without needing code changes between dev and prod —
# only .env changes. Defaults to "development" so nothing
# breaks if it's left unset locally.
# ============================================================

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Real-Time AI Chat",
    description="Real-Time AI Chat with RAG",
    version="1.0.0",
)


# ============================================================
# CORS (environment-aware)
# ============================================================
#
# A hand-rolled "bulletproof" CORS middleware + custom
# exception handlers used to live here, manually injecting
# headers and hardcoding the frontend origin to
# "http://localhost:5173". That's what caused /auth/login to
# intermittently fail with "blocked by CORS policy" /
# net::ERR_FAILED — JSON POST requests trigger a CORS
# preflight (OPTIONS), and the hand-rolled logic didn't
# handle every path through the app reliably.
#
# FRONTEND_URL is read from .env instead of hardcoded, so
# deploying to production is a config change, not a code
# change — set FRONTEND_URL=https://your-frontend-domain.com
# in production's .env and nothing here needs to be touched.
# ============================================================

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5174")

# Standard base parameters
cors_kwargs = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}

if ENVIRONMENT == "production":
    # Production: Strict URL match
    cors_kwargs["allow_origins"] = [FRONTEND_URL]
else:
    # Development: Simple explicit array list
    cors_kwargs["allow_origins"] = [
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

# Apply ONLY this single middleware layer
app.add_middleware(CORSMiddleware, **cors_kwargs)


# ============================================================
# GLOBAL EXCEPTION HANDLER
# ============================================================
#
# Without this, an unhandled exception (Redis unreachable,
# a bug in a route, whatever) escapes FastAPI's normal
# exception handling and is caught by Starlette's
# ServerErrorMiddleware instead — which sits OUTSIDE
# CORSMiddleware in the middleware stack. That response never
# gets CORS headers attached, so the browser reports a
# misleading "blocked by CORS policy" / "preflight doesn't
# pass access control check" error for what is actually a
# plain 500 crash on the backend.
#
# Registering a handler for the base Exception class keeps
# the error response inside FastAPI's normal handling path
# (and therefore inside CORSMiddleware, so headers get
# attached correctly), and logs the real error server-side
# instead of hiding it behind a fake CORS message.
# ============================================================

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s:\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )

    with sentry_sdk.push_scope() as scope:
        scope.set_tag("http_method", request.method)
        scope.set_tag("route", request.url.path)
        scope.set_extra("query_params", dict(request.query_params))
        sentry_sdk.capture_exception(exc)

    return Response(
        content=json.dumps({"detail": "Internal server error"}),
        status_code=500,
        media_type="application/json",
    )


# ============================================================
# COOKIE CONFIGURATION
# ============================================================

COOKIE_SECURE = (
    os.getenv(
        "COOKIE_SECURE",
        "false",
    ).lower()
    == "true"
)

COOKIE_SAMESITE = os.getenv(
    "COOKIE_SAMESITE",
    "lax",
)

REFRESH_COOKIE_NAME = "refresh_token"

# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434/api/generate",
)

OLLAMA_MODEL = os.getenv(
    "OLLAMA_MODEL",
    "qwen3:1.7b",
)

# Resolve uploads relative to this file instead of the process
# working directory. This keeps the path deterministic.
#
# Local Windows:
#   backend/uploads/
#
# Docker:
#   /app/uploads/
#
# The backend and worker containers must mount the same directory
# at /app/uploads so both processes can access uploaded files.
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"

UPLOAD_DIR.mkdir(
    exist_ok=True
)

MAX_FILE_SIZE = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
}


# ============================================================
# REQUEST SCHEMAS
# ============================================================

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ============================================================
# DATABASE STARTUP
# ============================================================

@app.on_event("startup")
async def startup():
    print(
        "Startup complete. Schema is managed by Alembic — "
        "run 'alembic upgrade head' before starting the "
        "app if you have pending migrations."
    )


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():
    return {
        "message": "Real-Time AI Chat Backend",
        "status": "running",
    }


# ============================================================
# HEALTH CHECK
# ============================================================
#
# Unlike "/", this actually verifies Redis and Postgres are
# reachable, not just that the process is alive. Useful for
# Docker healthchecks, uptime monitors, or a load balancer
# once this is deployed.
# ============================================================

@app.get("/health")
async def health():
    checks = {}

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as error:
        checks["redis"] = f"error: {error}"
        sentry_sdk.capture_exception(error)

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(select(1))
        checks["database"] = "ok"
    except Exception as error:
        checks["database"] = f"error: {error}"
        sentry_sdk.capture_exception(error)

    overall_status = (
        "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    )

    return {
        "status": overall_status,
        "checks": checks,
    }


# ============================================================
# AUTH: REGISTER
# ============================================================

@app.post("/auth/register")
async def register(
        data: RegisterRequest,
        request: Request,
        db: AsyncSession = Depends(get_db),
):
    allowed, remaining = await check_rate_limit(
        f"register:{request.client.host}",
        5,
        60,
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts",
        )

    email = str(data.email).lower().strip()

    result = await db.execute(
        select(User).where(
            User.email == email
        )
    )

    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Unable to create account with this email",
        )

    user = User(
        email=email,
        password_hash=hash_password(
            data.password
        ),
        email_verified=False,
    )

    db.add(user)
    await db.flush()

    raw_token, expires_at = (
        create_email_verification_token()
    )

    verification_token = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=expires_at,
    )

    db.add(verification_token)
    await db.commit()

    try:
        await send_verification_email(
            email,
            raw_token,
        )
    except Exception as error:
        sentry_sdk.capture_exception(error)
        raise HTTPException(
            status_code=503,
            detail="Account created, but verification email could not be sent",
        )

    return {
        "message": (
            "Account created. "
            "Please check your email to verify your account."
        )
    }


# ============================================================
# AUTH: VERIFY EMAIL
# ============================================================

@app.get("/auth/verify-email")
async def verify_email(
        token: str,
        db: AsyncSession = Depends(get_db),
):
    token_hash = hash_token(token)

    result = await db.execute(
        select(EmailVerificationToken)
        .where(
            EmailVerificationToken.token_hash
            == token_hash
        )
    )

    verification_token = (
        result.scalar_one_or_none()
    )

    if not verification_token:
        raise HTTPException(
            status_code=400,
            detail="Invalid verification token",
        )

    if verification_token.used:
        raise HTTPException(
            status_code=400,
            detail="Verification token has already been used",
        )
    if verification_token.expires_at < datetime.utcnow():

        raise HTTPException(
            status_code=400,
            detail="Verification token has expired",
        )

    result = await db.execute(
        select(User).where(
            User.id == verification_token.user_id
        )
    )

    user = result.scalar_one_or_none()

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user.email_verified = True

    verification_token.used = True

    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id
            == user.id
        )
        .where(
            EmailVerificationToken.id
            != verification_token.id
        )
        .values(used=True)
    )

    await db.commit()

    return {
        "message": "Email verified successfully"
    }


# ============================================================
# AUTH: RESEND VERIFICATION
# ============================================================

@app.post("/auth/resend-verification")
async def resend_verification(
    data: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    allowed, remaining = await check_rate_limit(
        f"resend-verification:{request.client.host}",
        3,
        300,
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests",
        )

    email = str(data.email).lower().strip()

    result = await db.execute(
        select(User).where(
            User.email == email
        )
    )

    user = result.scalar_one_or_none()

    # Generic response prevents easy account enumeration.
    if not user:
        return {
            "message": (
                "If the account exists, "
                "a verification email has been sent."
            )
        }

    if user.email_verified:
        return {
            "message": "Email is already verified."
        }

    # Invalidate previous tokens
    await db.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id
            == user.id
        )
        .values(used=True)
    )

    raw_token, expires_at = (
        create_email_verification_token()
    )

    verification_token = EmailVerificationToken(
        user_id=user.id,
        token_hash=hash_token(raw_token),
        expires_at=expires_at,
    )

    db.add(verification_token)

    await db.commit()

    await send_verification_email(
        user.email,
        raw_token,
    )

    return {
        "message": (
            "If the account exists, "
            "a verification email has been sent."
        )
    }


# ============================================================
# AUTH: LOGIN
# ============================================================

@app.post("/auth/login")
async def login(
    data: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    allowed, remaining = await check_rate_limit(
        f"login:{request.client.host}",
        5,
        60,
    )

    if not allowed:

        raise HTTPException(
            status_code=429,
            detail="Too many login attempts",
        )

    email = (
        str(data.email)
        .lower()
        .strip()
    )

    result = await db.execute(
        select(User).where(
            User.email == email
        )
    )

    user = result.scalar_one_or_none()

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if not verify_password(
        data.password,
        user.password_hash,
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    if not user.email_verified:

        raise HTTPException(
            status_code=403,
            detail="Please verify your email before logging in",
        )

    # -----------------------------------------
    # ACCESS TOKEN
    # -----------------------------------------

    access_token = create_access_token(
        str(user.id)
    )

    # -----------------------------------------
    # REFRESH TOKEN
    # -----------------------------------------

    raw_refresh_token, expires_at = (
        create_refresh_token()
    )

    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(
            raw_refresh_token
        ),
        expires_at=expires_at,
    )

    db.add(refresh_token)

    await db.commit()

    # -----------------------------------------
    # HTTPONLY COOKIE
    # -----------------------------------------

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw_refresh_token,
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/auth",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "email": user.email,
    }


# ============================================================
# AUTH: REFRESH
# ============================================================

@app.post("/auth/refresh")
async def refresh_access_token(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(
        default=None,
        alias=REFRESH_COOKIE_NAME,
    ),
):
    if not refresh_token:

        raise HTTPException(
            status_code=401,
            detail="Refresh token required",
        )

    token_hash = hash_token(
        refresh_token
    )

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash
            == token_hash
        )
    )

    stored_token = (
        result.scalar_one_or_none()
    )

    if not stored_token:

        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )

    # -----------------------------------------
    # CHECK REVOCATION
    # -----------------------------------------

    if stored_token.revoked:

        raise HTTPException(
            status_code=401,
            detail="Refresh token has been revoked",
        )

    # -----------------------------------------
    # CHECK EXPIRATION
    # -----------------------------------------

    if (
        stored_token.expires_at
        < datetime.utcnow()
    ):

        stored_token.revoked = True

        await db.commit()

        raise HTTPException(
            status_code=401,
            detail="Refresh token expired",
        )

    # -----------------------------------------
    # GET USER
    # -----------------------------------------

    result = await db.execute(
        select(User).where(
            User.id == stored_token.user_id
        )
    )

    user = result.scalar_one_or_none()

    if not user:

        raise HTTPException(
            status_code=401,
            detail="User not found",
        )

    if not user.email_verified:

        raise HTTPException(
            status_code=403,
            detail="Email is not verified",
        )

    # -----------------------------------------
    # ROTATE REFRESH TOKEN
    # -----------------------------------------

    new_raw_refresh_token, expires_at = (
        create_refresh_token()
    )

    new_refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(
            new_raw_refresh_token
        ),
        family_id=stored_token.family_id,
        expires_at=expires_at,
    )

    db.add(new_refresh_token)

    await db.flush()

    # Old token is now invalid.
    stored_token.revoked = True

    stored_token.replaced_by_id = (
        new_refresh_token.id
    )

    # -----------------------------------------
    # NEW ACCESS TOKEN
    # -----------------------------------------

    access_token = create_access_token(
        str(user.id)
    )

    await db.commit()

    # -----------------------------------------
    # NEW COOKIE
    # -----------------------------------------

    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=new_raw_refresh_token,
        max_age=30 * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/auth",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


# ============================================================
# AUTH: LOGOUT
# ============================================================

@app.post("/auth/logout")
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    refresh_token: str | None = Cookie(
        default=None,
        alias=REFRESH_COOKIE_NAME,
    ),
):
    if refresh_token:

        token_hash = hash_token(
            refresh_token
        )

        result = await db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash
                == token_hash
            )
        )

        stored_token = (
            result.scalar_one_or_none()
        )

        if stored_token:

            stored_token.revoked = True

            await db.commit()

    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path="/auth",
    )

    return {
        "message": "Logged out successfully"
    }


# ============================================================
# AUTH: CURRENT USER
# ============================================================

@app.get("/auth/me")
async def get_me(
    user_id: str = Depends(get_current_user_id),
):

    async with AsyncSessionLocal() as session:

        result = await session.execute(
            select(User).where(
                User.id == uuid.UUID(user_id)
            )
        )

        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="User not found",
            )

        return {
            "user_id": str(user.id),
            "email": user.email,
        }


# ============================================================
# CONVERSATIONS
# ============================================================

@app.get("/conversations")
async def get_conversations(
    authorization: str | None = Header(default=None),
):
    user_id = await get_current_user_id(authorization)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Conversation)
            .where(
                Conversation.user_id == uuid.UUID(user_id)
            )
            .order_by(Conversation.updated_at.desc())
        )

        conversations = result.scalars().all()

        return [
            {
                "id": str(conversation.id),
                "created_at": conversation.created_at.isoformat(),
                "updated_at": conversation.updated_at.isoformat(),
            }
            for conversation in conversations
        ]


@app.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    authorization: str | None = Header(default=None),
):
    user_id = await get_current_user_id(authorization)

    try:
        conversation_uuid = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid conversation ID",
        )

    async with AsyncSessionLocal() as session:

        # --------------------------------------------------
        # Confirm the conversation exists AND belongs to
        # this user before returning any messages from it.
        # --------------------------------------------------

        result = await session.execute(
            select(Conversation).where(
                Conversation.id == conversation_uuid,
                Conversation.user_id == uuid.UUID(user_id),
            )
        )

        conversation = result.scalar_one_or_none()

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found",
            )

        result = await session.execute(
            select(Message)
            .where(
                Message.conversation_id == conversation_uuid
            )
            .order_by(Message.created_at)
        )

        messages = result.scalars().all()

        return [
            {
                "role": message.role,
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            }
            for message in messages
        ]


# ============================================================
# DOCUMENT LIST
# ============================================================

@app.get("/documents")
async def get_documents(
    authorization: str | None = Header(default=None),
):
    user_id = await get_current_user_id(authorization)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document)
            .where(
                Document.user_id == uuid.UUID(user_id)
            )
            .order_by(Document.created_at.desc())
        )

        documents = result.scalars().all()

        return [
            {
                "document_id": str(document.id),
                "filename": document.filename,
                "status": document.status,
                "error": document.error_message,
            }
            for document in documents
        ]


# ============================================================
# DOCUMENT UPLOAD
# ============================================================

@app.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None),
):
    # ==========================================
    # Authenticate user
    # ==========================================

    try:
        user_id = await get_current_user_id(
            authorization
        )

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(error)}",
        )


    # ==========================================
    # Rate limit uploads per user
    # ==========================================

    allowed, remaining = await check_rate_limit(
        key=f"upload:{user_id}",
        limit=10,
        window_seconds=60 * 60,
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Upload limit reached. Try again later.",
            headers={
                "Retry-After": "3600",
            },
        )


    # --------------------------------------------------------
    # Validate filename
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="Filename is required",
        )


    # --------------------------------------------------------
    # Validate extension
    # --------------------------------------------------------
    #
    # `file.filename or ""` guards against a None filename
    # reaching Path() (defense in depth — even though we
    # already reject a missing filename above, this keeps
    # the check safe on its own). This is what blocks
    # things like .exe, .sh, .py, .bat from being accepted
    # as "documents".
    # --------------------------------------------------------

    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400,
            detail="Unsupported file type.",
        )


    # --------------------------------------------------------
    # Generate document ID
    # --------------------------------------------------------

    document_id = uuid.uuid4()


    # --------------------------------------------------------
    # Create safe filename
    # --------------------------------------------------------

    safe_filename = (
        f"{document_id}{extension}"
    )


    file_path = (
        UPLOAD_DIR / safe_filename
    )


    try:

        # ----------------------------------------------------
        # Save uploaded file (size-limited)
        # ----------------------------------------------------
        #
        # Read at most MAX_FILE_SIZE + 1 bytes. If more than
        # that comes back, the upload exceeds the limit and
        # is rejected — we never trust file.size alone, since
        # that value can be missing or spoofed by the client.
        # ----------------------------------------------------

        contents = await file.read(MAX_FILE_SIZE + 1)

        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File too large. Maximum size is 10 MB.",
            )

        with open(file_path, "wb") as buffer:
            buffer.write(contents)


        # ----------------------------------------------------
        # Create database document
        # ----------------------------------------------------

        async with AsyncSessionLocal() as session:

            document = Document(
                id=document_id,

                # IMPORTANT
                # Associate document with logged-in user
                user_id=uuid.UUID(user_id),

                filename=file.filename,

                status="processing",

                error_message=None,
            )

            session.add(
                document
            )

            await session.commit()


        # ----------------------------------------------------
        # Queue document processing job
        # ----------------------------------------------------

        job = document_queue.enqueue(
            process_document_sync,
            str(document_id),
            str(file_path),
        )


        print(
            f"Queued document job: {job.id}"
        )


        # ----------------------------------------------------
        # Return immediately
        # ----------------------------------------------------

        return {

            "message": (
                "Document uploaded and "
                "queued for processing"
            ),

            "document_id": str(
                document_id
            ),

            "filename": file.filename,

            "job_id": job.id,

            "status": "processing",
        }


    except HTTPException:

        # ----------------------------------------------------
        # Let intentional HTTP errors (e.g. 413 file too
        # large) pass through with their correct status
        # code, instead of being wrapped into a 500 below.
        # ----------------------------------------------------

        if file_path.exists():
            file_path.unlink()

        raise

    except Exception as error:

        # ----------------------------------------------------
        # Delete uploaded file if something fails
        # ----------------------------------------------------

        if file_path.exists():

            file_path.unlink()

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("operation", "document_upload")
            scope.set_extra("filename", file.filename)
            scope.set_extra("document_id", str(document_id))
            sentry_sdk.capture_exception(error)

        raise HTTPException(
            status_code=500,
            detail=(
                f"Document upload failed: "
                f"{str(error)}"
            ),
        )


# ============================================================
# DOCUMENT STATUS
# ============================================================

@app.get(
    "/documents/{document_id}"
)
async def get_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
):

    # --------------------------------------------------------
    # Validate UUID
    # --------------------------------------------------------

    try:

        document_uuid = uuid.UUID(
            document_id
        )

    except ValueError:

        raise HTTPException(
            status_code=400,
            detail="Invalid document ID",
        )


    # --------------------------------------------------------
    # Query database
    # --------------------------------------------------------

    async with AsyncSessionLocal() as session:

        result = await session.execute(

            select(Document)
            .where(
                Document.id
                == document_uuid,
                Document.user_id
                == uuid.UUID(user_id),
            )

        )


        document = (
            result.scalar_one_or_none()
        )


        if document is None:

            raise HTTPException(
                status_code=404,
                detail="Document not found",
            )


        return {

            "document_id": str(
                document.id
            ),

            "filename": (
                document.filename
            ),

            "status": (
                document.status
            ),

            "error": (
                document.error_message
            ),
        }


# ============================================================
# SEMANTIC SEARCH (with Redis retrieval cache)
# ============================================================

@app.post("/search")
async def search_documents(
    query: str,
    top_k: int = 5,
    user_id: str = Depends(get_current_user_id),
):

    # --------------------------------------------------------
    # Validate query
    # --------------------------------------------------------

    if not query.strip():

        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )


    # --------------------------------------------------------
    # Validate top_k
    # --------------------------------------------------------

    if top_k < 1 or top_k > 20:

        raise HTTPException(
            status_code=400,
            detail=(
                "top_k must be between 1 and 20"
            ),
        )


    # --------------------------------------------------------
    # Rate limit search requests
    # --------------------------------------------------------

    allowed, remaining = await check_rate_limit(
        key=f"search:{user_id}",
        limit=30,
        window_seconds=60,
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many search requests. Please try again later.",
            headers={
                "Retry-After": "60",
            },
        )


    try:

        # ----------------------------------------------------
        # 1. Check Redis retrieval cache
        # ----------------------------------------------------

        cached_results = await get_cached_retrieval(
            user_id,
            query,
            top_k,
        )

        if cached_results is not None:

            print("Retrieval cache HIT")

            return {
                "query": query,
                "results": cached_results,
                "cached": True,
            }

        print("Retrieval cache MISS")


        # ----------------------------------------------------
        # 2. Create query embedding
        # ----------------------------------------------------

        query_embedding = (
            await create_embedding(
                query
            )
        )


        # ----------------------------------------------------
        # 3. Search pgvector
        # ----------------------------------------------------

        async with AsyncSessionLocal() as session:

            rows = await retrieve_chunks(
                session=session,
                query_embedding=query_embedding,
                user_id=uuid.UUID(user_id),
                top_k=top_k,
            )


            formatted_results = []


            for chunk, distance, filename in rows:

                formatted_results.append({

                    "chunk_id": str(
                        chunk.id
                    ),

                    "document_id": str(
                        chunk.document_id
                    ),

                    "filename": filename,

                    "chunk_index": (
                        chunk.chunk_index
                    ),

                    "content": (
                        chunk.content
                    ),

                    "distance": float(
                        distance
                    ),
                })


        # ----------------------------------------------------
        # 4. Store retrieval results in Redis
        # ----------------------------------------------------

        await cache_retrieval(
            user_id,
            query,
            formatted_results,
            top_k,
        )


        # ----------------------------------------------------
        # 5. Return results
        # ----------------------------------------------------

        return {

            "query": query,

            "results": formatted_results,

            "cached": False,
        }


    except Exception as error:

        print(
            f"Semantic search error: "
            f"{error}"
        )
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("operation", "semantic_search")
            scope.set_extra("top_k", top_k)
            sentry_sdk.capture_exception(error)


        raise HTTPException(
            status_code=500,
            detail="Semantic search failed",
        )


# ============================================================
# WEBSOCKET CHAT
# ============================================================

@app.websocket("/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    token: str = Query(...),
):

    try:
        user_id = decode_access_token(token)

    except Exception:
        await websocket.close(
            code=1008,
            reason="Invalid or expired token",
        )
        return

    await websocket.accept()

    print(
        f"Authenticated user connected: {user_id}"
    )


    try:

        while True:

            # ------------------------------------------------
            # Receive message
            # ------------------------------------------------

            raw_message = (
                await websocket.receive_text()
            )


            # ------------------------------------------------
            # Parse JSON
            # ------------------------------------------------

            try:

                data = json.loads(
                    raw_message
                )


                user_message = data.get(
                    "message"
                )


                conversation_id = (
                    data.get(
                        "conversation_id"
                    )
                )


                if not user_message:

                    await websocket.send_json({

                        "type": "error",

                        "message": (
                            "Message cannot "
                            "be empty"
                        ),

                    })

                    continue


            except json.JSONDecodeError:

                await websocket.send_json({

                    "type": "error",

                    "message": "Invalid JSON",

                })

                continue


            # ------------------------------------------------
            # Rate limit messages per user
            # ------------------------------------------------

            allowed, remaining = await check_rate_limit(
                key=f"ws_message:{user_id}",
                limit=20,
                window_seconds=60,
            )

            if not allowed:
                await websocket.send_json({
                    "type": "error",
                    "message": "You are sending messages too quickly. Please wait."
                })
                continue


            # ------------------------------------------------
            # Database session
            # ------------------------------------------------

            async with AsyncSessionLocal() as session:

                # --------------------------------------------
                # Find or create conversation
                # --------------------------------------------

                if conversation_id:

                    try:

                        conversation_uuid = (
                            uuid.UUID(
                                conversation_id
                            )
                        )


                    except ValueError:

                        await websocket.send_json({

                            "type": "error",

                            "message": (
                                "Invalid "
                                "conversation ID"
                            ),

                        })

                        continue


                    result = await session.execute(

                        select(
                            Conversation
                        )
                        .where(
                            Conversation.id
                            == conversation_uuid,
                            Conversation.user_id
                            == uuid.UUID(user_id),
                        )

                    )


                    conversation = (
                        result.scalar_one_or_none()
                    )


                    if conversation is None:

                        await websocket.send_json({

                            "type": "error",

                            "message": (
                                "Conversation "
                                "not found"
                            ),

                        })

                        continue


                else:

                    conversation = (
                        Conversation(
                            user_id=uuid.UUID(
                                user_id
                            )
                        )
                    )

                    session.add(
                        conversation
                    )

                    await session.flush()

                    conversation_uuid = (
                        conversation.id
                    )


                # --------------------------------------------
                # Save user message
                # --------------------------------------------

                user_db_message = Message(

                    conversation_id=(
                        conversation_uuid
                    ),

                    role="user",

                    content=user_message,

                )

                session.add(
                    user_db_message
                )

                await session.commit()


                # --------------------------------------------
                # Retrieve conversation history
                # --------------------------------------------
                #
                # Only pull the most recent messages instead
                # of the entire conversation. This keeps the
                # prompt from growing unbounded as a
                # conversation gets longer, while still giving
                # the model enough context to resolve
                # follow-up questions like "why is it used?"
                # after "what database does it use?".
                # --------------------------------------------

                HISTORY_MESSAGE_LIMIT = 10

                result = await session.execute(

                    select(Message)
                    .where(
                        Message.conversation_id
                        == conversation_uuid
                    )
                    .order_by(
                        Message.created_at.desc()
                    )
                    .limit(HISTORY_MESSAGE_LIMIT)

                )


                # Query returns newest-first (for the LIMIT
                # to keep the *most recent* messages) — flip
                # back to chronological order before building
                # the prompt.
                history = list(
                    reversed(
                        result.scalars().all()
                    )
                )


                # --------------------------------------------
                # Create question embedding
                # --------------------------------------------

                try:

                    query_embedding = (
                        await create_embedding(
                            user_message
                        )
                    )


                except Exception as error:

                    print(
                        f"Embedding error: "
                        f"{error}"
                    )
                    with sentry_sdk.push_scope() as scope:
                        scope.set_tag("operation", "websocket_embedding")
                        scope.set_tag("user_id", str(user_id))
                        sentry_sdk.capture_exception(error)


                    await websocket.send_json({

                        "type": "error",

                        "message": (
                            "Could not create "
                            "question embedding"
                        ),

                    })

                    continue


                # --------------------------------------------
                # Retrieve relevant chunks
                # --------------------------------------------

                try:

                    retrieved_chunks = (
                        await retrieve_chunks(

                            session=session,

                            query_embedding=(
                                query_embedding
                            ),

                            user_id=uuid.UUID(
                                user_id
                            ),

                            top_k=5,

                        )
                    )


                except Exception as error:

                    print(
                        f"Retrieval error: "
                        f"{error}"
                    )
                    with sentry_sdk.push_scope() as scope:
                        scope.set_tag("operation", "websocket_retrieval")
                        scope.set_tag("user_id", str(user_id))
                        sentry_sdk.capture_exception(error)


                    await websocket.send_json({

                        "type": "error",

                        "message": (
                            "Could not retrieve "
                            "documents"
                        ),

                    })

                    continue


                print(
                    f"Retrieved "
                    f"{len(retrieved_chunks)} "
                    f"chunks"
                )


                # --------------------------------------------
                # Send sources
                # --------------------------------------------

                await websocket.send_json({

                    "type": "sources",

                    "sources": [

                        {

                            "chunk_id": str(
                                chunk.id
                            ),

                            "document_id": str(
                                chunk.document_id
                            ),

                            "filename": filename,

                            "chunk_index": (
                                chunk.chunk_index
                            ),

                            "content": (
                                chunk.content
                            ),

                            "distance": float(
                                distance
                            ),

                        }

                        for chunk, distance, filename
                        in retrieved_chunks

                    ],

                })


                # --------------------------------------------
                # Send conversation ID
                # --------------------------------------------

                await websocket.send_json({

                    "type": "conversation",

                    "conversation_id": str(
                        conversation_uuid
                    ),

                })


                # --------------------------------------------
                # Build RAG prompt
                # --------------------------------------------

                prompt = build_rag_prompt(

                    question=user_message,

                    history=history,

                    retrieved_chunks=(
                        retrieved_chunks
                    ),

                )


                print(
                    "\n--- RAG PROMPT ---"
                )

                print(prompt)

                print(
                    "--- END PROMPT ---\n"
                )


                # --------------------------------------------
                # Ollama payload
                # --------------------------------------------

                payload = {

                    "model": OLLAMA_MODEL,

                    "prompt": prompt,

                    "stream": True,

                    "options": {
                        "num_ctx": 1024,
                    },

                }


                full_response = ""


                # --------------------------------------------
                # Stream Ollama response
                # --------------------------------------------

                try:

                    async with httpx.AsyncClient() as client:

                        async with client.stream(

                            "POST",

                            OLLAMA_URL,

                            json=payload,

                            timeout=None,

                        ) as response:

                            response.raise_for_status()


                            async for line in (
                                response.aiter_lines()
                            ):

                                if not line:

                                    continue


                                try:

                                    ollama_data = (
                                        json.loads(
                                            line
                                        )
                                    )


                                    chunk = (
                                        ollama_data.get(
                                            "response",
                                            "",
                                        )
                                    )


                                    if chunk:

                                        full_response += (
                                            chunk
                                        )


                                        await websocket.send_json({

                                            "type": (
                                                "chunk"
                                            ),

                                            "content": (
                                                chunk
                                            ),

                                        })


                                        await asyncio.sleep(
                                            0
                                        )


                                    if ollama_data.get(
                                        "done"
                                    ):

                                        break


                                except json.JSONDecodeError:

                                    continue


                except Exception as error:

                    print(
                        f"Ollama error: "
                        f"{error}"
                    )
                    with sentry_sdk.push_scope() as scope:
                        scope.set_tag("operation", "ollama_stream")
                        scope.set_tag("ollama_model", OLLAMA_MODEL)
                        sentry_sdk.capture_exception(error)


                    await websocket.send_json({

                        "type": "error",

                        "message": (
                            "Could not connect "
                            "to Ollama"
                        ),

                    })

                    continue


                # --------------------------------------------
                # Save AI response
                # --------------------------------------------

                ai_message = Message(

                    conversation_id=(
                        conversation_uuid
                    ),

                    role="assistant",

                    content=full_response,

                )

                session.add(
                    ai_message
                )

                await session.commit()


                # --------------------------------------------
                # Tell frontend generation is finished
                # --------------------------------------------

                await websocket.send_json({

                    "type": "done",

                })


    except WebSocketDisconnect:

        print(
            "React Client disconnected"
        )

    except Exception as error:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("operation", "websocket_chat")
            scope.set_tag("user_id", str(user_id))
            sentry_sdk.capture_exception(error)

        try:
            await websocket.close(code=1011)
        except Exception:
            pass

# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    uvicorn.run(

        "main:app",

        host="127.0.0.1",

        port=8000,

        reload=True,

    )