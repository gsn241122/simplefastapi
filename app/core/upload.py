from __future__ import annotations

import os
import uuid
import shutil
from pathlib import Path
from typing import Optional, Iterable
from app.core.config import settings

def _normalize_allowed_image_types(value: "str | Iterable[str]") -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        # support JSON list or comma-separated
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x).strip() for x in parsed if x is not None]
            except Exception:
                pass
        return [item.strip() for item in s.split(",") if item.strip()]
    if isinstance(value, Iterable):
        return [str(x).strip() for x in value]
    return [str(value)]

from fastapi import UploadFile, HTTPException, status
from app.core.config import settings
import json

def validate_image_file(upload_file: UploadFile) -> None:
    """
    Validate that the uploaded file is an allowed image type and within size limits.
    Raises HTTPException if validation fails.
    """
    # Check file size
    upload_file.file.seek(0, 2)  # Seek to end
    file_size = upload_file.file.tell()
    upload_file.file.seek(0)  # Reset pointer
    
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE // (1024*1024)} MB"
        )
    
    # Check content type
    allowed_types = _normalize_allowed_image_types(settings.ALLOWED_IMAGE_TYPES)
    if upload_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type '{upload_file.content_type}' is not allowed. Allowed types: {', '.join(allowed_types)}"
        )

def save_upload_file(upload_file: UploadFile, subdirectory: str = "") -> str:
    """
    Save an uploaded file to the uploads directory and return its relative path.
    
    Args:
        upload_file: The uploaded file
        subdirectory: Optional subdirectory within UPLOAD_DIR (e.g., "products")
        
    Returns:
        Relative path to the saved file (e.g., "uploads/products/filename.jpg")
    """
    # Validate the file
    validate_image_file(upload_file)
    
    # Ensure upload directory exists
    upload_path = Path(settings.UPLOAD_DIR)
    if subdirectory:
        upload_path = upload_path / subdirectory
    upload_path.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename to avoid collisions
    file_extension = Path(upload_file.filename).suffix if upload_file.filename else ""
    unique_filename = f"{uuid.uuid4().hex}{file_extension}"
    file_path = upload_path / unique_filename
    
    # Save the file
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        upload_file.file.close()
    
    # Return relative path for storage in database
    return str(file_path).replace("\\", "/")  # Ensure Unix-style paths

def delete_file(file_path: str) -> bool:
    """
    Delete a file if it exists.
    
    Args:
        file_path: Relative or absolute path to the file
        
    Returns:
        True if file was deleted, False if file didn't exist
    """
    try:
        path = Path(file_path)
        if path.is_file():
            path.unlink()
            return True
        return False
    except Exception:
        return False