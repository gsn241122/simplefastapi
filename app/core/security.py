from __future__ import annotations

import re
from passlib.context import CryptContext
from app.core.config import MIN_PASSWORD_LENGTH

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pola regex untuk validasi kekuatan password
_RE_UPPERCASE = re.compile(r"[A-Z]")
_RE_LOWERCASE = re.compile(r"[a-z]")
_RE_DIGIT = re.compile(r"\d")
_RE_SPECIAL = re.compile(r"[!@#$%^&*(),.?\":{}|<>]")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifikasi plain password terhadap hashed password.

    Args:
        plain_password: Password teks biasa dari user input.
        hashed_password: Hash bcrypt yang tersimpan di database.

    Returns:
        True jika password cocok, False jika tidak.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash sebuah password menggunakan bcrypt.

    Args:
        password: Password teks biasa.

    Returns:
        String hash bcrypt.
    """
    return pwd_context.hash(password)


def validate_password_strength(password: str) -> list[str]:
    """
    Validasi kekuatan password dan kembalikan daftar error.

    Args:
        password: Password yang akan divalidasi.

    Returns:
        List pesan error. Kosong berarti password valid.
    """
    errors: list[str] = []

    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(f"Password minimal {MIN_PASSWORD_LENGTH} karakter.")

    if not _RE_UPPERCASE.search(password):
        errors.append("Password harus mengandung minimal satu huruf kapital.")

    if not _RE_LOWERCASE.search(password):
        errors.append("Password harus mengandung minimal satu huruf kecil.")

    if not _RE_DIGIT.search(password):
        errors.append("Password harus mengandung minimal satu angka.")

    if not _RE_SPECIAL.search(password):
        errors.append("Password harus mengandung minimal satu karakter spesial (!@#$%^&* dll.).")

    return errors
