from __future__ import annotations

import pdfplumber

import streamlit as st

from config import MAX_PDF_FILE_SIZE_MB


def process_pdf(uploaded_file) -> str | None:
    """Extract text from an uploaded PDF file using pdfplumber.

    Returns ``None`` if the file is too large, has an unsupported MIME type,
    or cannot be parsed. On ``None``, an ``st.error`` has already been emitted
    so callers do not need to display anything. Returns an empty-PDF warning
    *string* (not ``None``) if the PDF was parsed but contains no extractable
    text — distinguishing "no file" from "empty document" matters for the UI.
    """
    try:
        if uploaded_file.size > MAX_PDF_FILE_SIZE_MB * 1024 * 1024:
            st.error(f"PDF file too large (> {MAX_PDF_FILE_SIZE_MB} MB).")
            return None

        # MIME guard — surface a clearer error for non-PDFs instead of a
        # pdfplumber parse exception.
        mime = (getattr(uploaded_file, "type", None) or "").lower()
        if mime and mime != "application/pdf":
            st.error(f"Unsupported file type: {mime}.")
            return None

        with pdfplumber.open(uploaded_file) as pdf:
            pages_text = [
                f"--- Page {i + 1} ---\n{page.extract_text()}"
                for i, page in enumerate(pdf.pages)
                if page.extract_text()
            ]

        full_text = "\n\n".join(pages_text)
        if not full_text.strip():
            return "[Warning: No extractable text found in this PDF (it might be a scanned image without a text layer)]."

        return full_text
    except Exception as e:
        st.error(f"Error processing PDF: {e}")
        return None
