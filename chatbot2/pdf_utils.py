from __future__ import annotations
import pdfplumber
import streamlit as st
from config import MAX_PDF_FILE_SIZE_MB

def process_pdf(uploaded_file) -> str | None:
    """
    Validates and extracts text from an uploaded PDF file using pdfplumber.
    Returns the extracted text content or None if processing fails.
    """
    try:
        # Check size
        if uploaded_file.size > MAX_PDF_FILE_SIZE_MB * 1024 * 1024:
            st.error(f"PDF file too large (> {MAX_PDF_FILE_SIZE_MB}MB)")
            return None

        text_content = []
        with pdfplumber.open(uploaded_file) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                extracted = page.extract_text()
                if extracted:
                    text_content.append(f"--- Page {page_idx + 1} ---\n{extracted}")

        full_text = "\n\n".join(text_content)
        if not full_text.strip():
            return "[Warning: No extractable text found in this PDF (it might be a scanned image without a text layer)]."
        
        return full_text
    except Exception as e:
        st.error(f"Error processing PDF: {e}")
        return None