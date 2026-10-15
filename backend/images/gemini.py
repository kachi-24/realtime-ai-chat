import os
from pathlib import Path
from dotenv import load_dotenv
from typing import AsyncGenerator
from google import genai
from google.genai import types

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-3.5-flash-lite")
_client = None


def _get_client() -> genai.Client:
    # Lazy: a missing key fails only when an image is analyzed,
    # not at import time (which would break CI and text-only use).
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        _client = genai.Client(api_key=key)
    return _client


async def analyze_image(
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
) -> str:
    response = await _get_client().aio.models.generate_content(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
    )
    return response.text or "I couldn't analyze the image."


async def analyze_image_stream(
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
) -> AsyncGenerator[str, None]:
    """
    Streams the vision model response chunk by chunk to be compatible
    with the consumer WebSocket loop.
    """
    response_stream = await _get_client().aio.models.generate_content_stream(
        model=MODEL,
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
    )

    async for chunk in response_stream:
        if chunk.text:
            yield chunk.text
