from __future__ import annotations
import base64
import io
from PIL import Image
import streamlit as st
from config import MAX_IMAGE_FILE_SIZE_MB, SUPPORTED_IMAGE_TYPES, MAX_IMAGE_DIMENSION

def process_image(uploaded_file) -> str | None:
    """
    Validates, resizes, and converts image to Base64 data URL.
    Returns None if processing fails.
    """
    try:
        # Check size
        if uploaded_file.size > MAX_IMAGE_FILE_SIZE_MB * 1024 * 1024:
            st.error(f"Image too large (> {MAX_IMAGE_FILE_SIZE_MB}MB)")
            return None

        # Open image
        img = Image.open(uploaded_file)
        
        # Resize if necessary
        if img.width > MAX_IMAGE_DIMENSION or img.height > MAX_IMAGE_DIMENSION:
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))
        
        # Convert to RGB if needed (e.g., for RGBA/PNG)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Encode to base64
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        return f"data:image/jpeg;base64,{img_str}"
    except Exception as e:
        st.error(f"Error processing image: {e}")
        return None
