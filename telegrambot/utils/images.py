"""Image processing utility for Telegram Bot.

Validates, resizes, and encodes uploaded images to base64 data-URI.
Limits are read at call-time from Settings so they are .env-overridable.
"""
from __future__ import annotations

import base64
import io

from loguru import logger
from PIL import Image

from config import get_settings


def process_image(
    file_bytes: bytes | bytearray,
    file_size: int,
    mime_type: str,
) -> str | None:
    """Validate, resize (if needed) and encode an image as a base64 data-URI.

    Args:
        file_bytes: Raw bytes of the image file.
        file_size:  Reported file size in bytes (used for limit check).
        mime_type:  MIME type reported by Telegram (e.g. ``image/jpeg``).

    Returns:
        A ``data:image/jpeg;base64,…`` string, or ``None`` on validation/
        processing failure.
    """
    settings = get_settings()
    max_bytes = settings.max_image_file_size_mb * 1024 * 1024
    max_dim = settings.max_image_dimension

    if file_size > max_bytes:
        logger.warning(
            "Image rejected: size {} B exceeds limit of {} MB",
            file_size,
            settings.max_image_file_size_mb,
        )
        return None

    if not mime_type.startswith("image/"):
        logger.warning("Image rejected: unsupported MIME type '{}'", mime_type)
        return None

    try:
        img = Image.open(io.BytesIO(bytes(file_bytes)))

        # Resize proportionally if either dimension exceeds the limit
        if img.width > max_dim or img.height > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            logger.debug(
                "Image resized to {}x{} (limit={}px)",
                img.width, img.height, max_dim,
            )

        # Telegram photos may be RGBA/palette — convert to RGB for JPEG output
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"

    except Exception as exc:
        logger.exception("Failed to process image: {}", exc)
        return None
