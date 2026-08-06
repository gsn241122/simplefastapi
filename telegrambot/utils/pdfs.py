"""PDF processing utility for Telegram Bot.

Extracts plain text from uploaded PDF files using pdfplumber.
Limits are read at call-time from Settings so they are .env-overridable.
"""
from __future__ import annotations

import io

import pdfplumber
from loguru import logger

from config import get_settings


def process_pdf(
    file_bytes: bytes | bytearray,
    file_size: int,
    mime_type: str,
) -> str | None:
    """Extract plain text from a PDF file.

    Args:
        file_bytes: Raw bytes of the PDF file.
        file_size:  Reported file size in bytes (used for limit check).
        mime_type:  MIME type reported by Telegram (should be ``application/pdf``).

    Returns:
        Extracted text (pages joined by double newlines), a warning string if
        the PDF has no extractable text, or ``None`` on validation/parse failure.
    """
    settings = get_settings()
    max_bytes = settings.max_pdf_file_size_mb * 1024 * 1024

    if file_size > max_bytes:
        logger.warning(
            "PDF rejected: size {} B exceeds limit of {} MB",
            file_size,
            settings.max_pdf_file_size_mb,
        )
        return None

    if mime_type != "application/pdf":
        logger.warning("PDF rejected: unexpected MIME type '{}'", mime_type)
        return None

    try:
        with pdfplumber.open(io.BytesIO(bytes(file_bytes))) as pdf:
            pages_text = [
                f"--- Halaman {i + 1} ---\n{page.extract_text()}"
                for i, page in enumerate(pdf.pages)
                if page.extract_text()
            ]

        if not pages_text:
            logger.warning("PDF has no extractable text (possibly scanned/image-only)")
            return "[Peringatan: PDF ini tidak memiliki teks yang bisa diekstrak (mungkin berbasis gambar/scan).]"

        full_text = "\n\n".join(pages_text)
        logger.debug("PDF extracted {} chars from {} pages", len(full_text), len(pages_text))
        return full_text

    except Exception as exc:
        logger.exception("Failed to process PDF: {}", exc)
        return None
