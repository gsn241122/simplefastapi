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


async def get_current_user_from_token(token: str, db) -> "User":
    """
    Dependency untuk mendapatkan user saat ini dari token JWT.
    
    Args:
        token: JWT access token.
        db: Database session.
        
    Returns:
        User object.
        
    Raises:
        HTTPException: Jika token tidak valid atau user tidak ditemukan.
    """
    from fastapi import HTTPException, status
    from jose import JWTError, jwt
    from app.core.config import settings
    from app.modules.user import crud, schemas
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    user = crud.get_user_by_username(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    
    if user.is_deleted or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or deleted"
        )
    
    return user


def require_auth(current_user: "User") -> "User":
    """
    Dependency untuk memastikan user sudah terautentikasi.
    
    Args:
        current_user: User yang sedang login (dari get_current_user).
        
    Returns:
        User object.
    """
    return current_user


def require_admin(current_user: "User") -> "User":
    """
    Dependency untuk memastikan user adalah admin.
    
    Args:
        current_user: User yang sedang login (dari get_current_user).
        
    Returns:
        User object.
        
    Raises:
        HTTPException: Jika user bukan admin.
    """
    from fastapi import HTTPException, status
    
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user
