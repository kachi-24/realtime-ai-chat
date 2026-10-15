import os
from io import BytesIO
from uuid import uuid4

import cloudinary
import cloudinary.uploader
import cloudinary.utils
import httpx


def configure_cloudinary() -> None:
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )


def upload_image(
    image_bytes: bytes,
    mime_type: str,
    user_id: str,
) -> dict:
    """
    Upload sanitized image bytes to Cloudinary.
    """

    configure_cloudinary()

    public_id = f"chat-images/{user_id}/{uuid4()}"

    result = cloudinary.uploader.upload(
        BytesIO(image_bytes),
        public_id=public_id,
        resource_type="image",
        type="authenticated",
        overwrite=False,
        use_filename=False,
        unique_filename=True,
    )

    return {
        "public_id": result["public_id"],
        "resource_type": result["resource_type"],
        "format": result.get("format"),
        "width": result.get("width"),
        "height": result.get("height"),
        "bytes": result.get("bytes"),
    }


def get_authenticated_image_url(public_id: str) -> str:
    """Signed delivery URL, built from the trusted DB public_id only."""
    configure_cloudinary()

    url, _ = cloudinary.utils.cloudinary_url(
        public_id,
        resource_type="image",
        type="authenticated",
        secure=True,
        sign_url=True,
    )

    return url


async def download_image_bytes(public_id: str) -> tuple[bytes, str]:
    url = get_authenticated_image_url(public_id)

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()

    mime_type = response.headers.get("content-type", "image/jpeg")
    return response.content, mime_type.split(";")[0]
