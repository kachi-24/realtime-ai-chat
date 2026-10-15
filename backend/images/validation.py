from io import BytesIO

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_IMAGE_PIXELS = 20_000_000     # 20 megapixels

ALLOWED_FORMATS = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}


async def validate_and_sanitize_image(
    file: UploadFile,
) -> tuple[bytes, str, int, int]:
    """
    Validate an uploaded image and return sanitized image bytes.

    Returns:
        image_bytes
        mime_type
        width
        height
    """

    # ---------------------------------------------------------
    # 1. Don't trust the uploaded filename
    # ---------------------------------------------------------
    # We intentionally never use file.filename for storage.
    #
    # ---------------------------------------------------------
    # 2. Check the client-provided MIME type
    # ---------------------------------------------------------
    if file.content_type not in ALLOWED_FORMATS.values():
        raise HTTPException(
            status_code=400,
            detail="Only JPEG, PNG, and WebP images are allowed.",
        )

    # ---------------------------------------------------------
    # 3. Read the file with a hard size limit
    # ---------------------------------------------------------
    data = bytearray()

    while True:
        chunk = await file.read(1024 * 1024)  # 1 MB chunks

        if not chunk:
            break

        data.extend(chunk)

        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="Image exceeds the 10 MB size limit.",
            )

    if not data:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    # ---------------------------------------------------------
    # 4. Verify the actual image contents
    # ---------------------------------------------------------
    try:
        image = Image.open(BytesIO(data))

        # verify() checks that the file is actually a valid image
        image.verify()

    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid or corrupted image.",
        )

    # ---------------------------------------------------------
    # 5. Re-open after verify()
    # ---------------------------------------------------------
    try:
        image = Image.open(BytesIO(data))

        width, height = image.size

    except (UnidentifiedImageError, OSError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Unable to process image.",
        )

    # ---------------------------------------------------------
    # 6. Pixel/decompression-bomb protection
    # ---------------------------------------------------------
    total_pixels = width * height

    if total_pixels > MAX_IMAGE_PIXELS:
        raise HTTPException(
            status_code=413,
            detail="Image dimensions are too large.",
        )

    # ---------------------------------------------------------
    # 7. Verify the actual detected format
    # ---------------------------------------------------------
    detected_format = image.format

    if detected_format not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format.",
        )

    # ---------------------------------------------------------
    # 8. Re-encode the image
    #
    # This creates a fresh image instead of sending the
    # original uploaded bytes directly to Cloudinary.
    # ---------------------------------------------------------
    try:
        if detected_format == "JPEG":
            # JPEG doesn't support transparency.
            sanitized = image.convert("RGB")

            output = BytesIO()
            sanitized.save(
                output,
                format="JPEG",
                quality=85,
                optimize=True,
            )

            mime_type = "image/jpeg"

        elif detected_format == "PNG":
            # Preserve transparency for PNG.
            sanitized = image.convert("RGBA")

            output = BytesIO()
            sanitized.save(
                output,
                format="PNG",
                optimize=True,
            )

            mime_type = "image/png"

        elif detected_format == "WEBP":
            sanitized = image.convert("RGBA")

            output = BytesIO()
            sanitized.save(
                output,
                format="WEBP",
                quality=85,
                method=6,
            )

            mime_type = "image/webp"

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported image format.",
            )

    except (OSError, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Image could not be safely processed.",
        )

    sanitized_bytes = output.getvalue()

    if not sanitized_bytes:
        raise HTTPException(
            status_code=400,
            detail="Sanitized image is empty.",
        )

    return sanitized_bytes, mime_type, width, height