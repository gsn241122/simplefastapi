from __future__ import annotations

import base64
import io

from PIL import Image

import streamlit as st
from config import MAX_IMAGE_FILE_SIZE_MB, MAX_IMAGE_DIMENSION


def process_image(uploaded_file) -> str | None:
    """Validate, resize, and convert an uploaded image to a base64 data URL.

    Returns ``None`` if the file is too large, has an unsupported MIME type,
    or cannot be decoded by Pillow. On ``None``, an ``st.error`` has already
    been emitted so callers do not need to display anything.
    """
    try:
        # Size guard (avoid loading huge files into RAM).
        if uploaded_file.size > MAX_IMAGE_FILE_SIZE_MB * 1024 * 1024:
            st.error(f"Image too large (> {MAX_IMAGE_FILE_SIZE_MB} MB).")
            return None

        # MIME guard — surface a clearer error for non-images instead of a
        # Pillow decode exception.
        mime = (getattr(uploaded_file, "type", None) or "").lower()
        if mime and not mime.startswith("image/"):
            st.error(f"Unsupported file type: {mime}.")
            return None

        img = Image.open(uploaded_file)

        # Resize while preserving aspect ratio.
        if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))

        # JPEG cannot store an alpha channel; flatten RGBA / palette images first.
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return f"data:image/jpeg;base64,{img_str}"
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None
