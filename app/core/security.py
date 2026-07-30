"""
Security helpers: password hashing, JWT validation, RBAC dependencies.
"""
from __future__ import annotations

import re
from typing import Callable
from passlib.context import CryptContext
from app.core.config import MIN_PASSWORD_LENGTH

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pola regex untuk validasi kekuatan password
_RE_UPPERCASE = re.compile(r"[A-Z]")
_RE_LOWERCASE = re.compile(r"[a-z]")
_RE_DIGIT = re.compile(r"\d")
_RE_SPECIAL = re.compile(r"[!@#$%^&*(),.?\":{}|<>]")


# ─── Password Hashing ────────────────────────────────────────────────────────────

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


# ─── Token / Current User ────────────────────────────────────────────────────────

async def get_current_user_from_token(token: str, db) -> "User":
    """
    Dependency untuk mendapatkan user saat ini dari token JWT.

    Catatan: ini adalah versi "low-level" yang langsung menerima token.
    Untuk endpoint, lebih baik pakai `auth.routes.get_current_user`
    yang sudah terintegrasi dengan Redis IP-binding.

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


# ─── RBAC Dependencies ───────────────────────────────────────────────────────────

def require_auth(current_user: "User") -> "User":
    """
    Dependency untuk memastikan user sudah terautentikasi.

    Args:
        current_user: User yang sedang login (dari get_current_user).

    Returns:
        User object.
    """
    return current_user


def require_role(*allowed_roles: str) -> Callable:
    """
    Dependency factory: izinkan user yang memiliki salah satu role.

    Mendukung dua sumber kebenaran:
      1. Field legacy `User.role` (string)
      2. Relasi many-to-many `User.roles` (RBAC)

    Contoh:
        @router.get("/admin")
        def admin_dashboard(user: User = Depends(require_role("admin"))):
            ...

    Args:
        *allowed_roles: Nama-nama role yang diizinkan (variadic).

    Returns:
        Dependency function.
    """
    from fastapi import Depends, HTTPException, status
    from app.modules.auth.routes import get_current_user

    def role_checker(current_user: "User" = Depends(get_current_user)) -> "User":
        # Kumpulkan semua role user: dari relasi + legacy field
        user_roles = {r.name for r in current_user.roles}
        if current_user.role:
            user_roles.add(current_user.role)

        if not user_roles.intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(allowed_roles)}",
            )
        return current_user

    return role_checker


def require_permission(*required_permissions: str) -> Callable:
    """
    Dependency factory: izinkan user yang memiliki salah satu permission.

    Permission di-resolve otomatis dari role-role user (transitive).

    Contoh:
        @router.post("/users")
        def create_user(
            payload: UserCreate,
            user: User = Depends(require_permission("write:users"))
        ):
            ...

    Args:
        *required_permissions: Nama-nama permission yang diizinkan (variadic).
                              User harus punya SALAH SATU untuk lewat.

    Returns:
        Dependency function.
    """
    from fastapi import Depends, HTTPException, status
    from app.modules.auth.routes import get_current_user

    def permission_checker(current_user: "User" = Depends(get_current_user)) -> "User":
        # Ambil semua permission user (gabungan dari semua role)
        user_permissions = current_user.permissions

        if not user_permissions.intersection(required_permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of permissions: {list(required_permissions)}",
            )
        return current_user

    return permission_checker


def require_all_permissions(*required_permissions: str) -> Callable:
    """
    Dependency factory: user harus memiliki SEMUA permission yang diminta.

    Lebih ketat dari `require_permission` (OR). Gunakan untuk aksi kritis.

    Args:
        *required_permissions: Permission yang semuanya harus dimiliki user.

    Returns:
        Dependency function.
    """
    from fastapi import Depends, HTTPException, status
    from app.modules.auth.routes import get_current_user

    def all_perm_checker(current_user: "User" = Depends(get_current_user)) -> "User":
        user_permissions = current_user.permissions
        missing = set(required_permissions) - user_permissions
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions: {sorted(missing)}",
            )
        return current_user

    return all_perm_checker


# ─── Backward-compatible alias ───────────────────────────────────────────────────
# Dipertahankan agar kode lama yang import `require_admin` tidak rusak.
def require_admin(current_user: "User") -> "User":
    """
    Dependency untuk memastikan user adalah admin.

    Mendukung baik legacy `User.role == "admin"` maupun relasi RBAC.

    Args:
        current_user: User yang sedang login (dari get_current_user).

    Returns:
        User object.

    Raises:
        HTTPException: Jika user bukan admin.
    """
    from fastapi import HTTPException, status

    is_admin_legacy = current_user.role == "admin"
    is_admin_rbac = current_user.has_role("admin")

    if not (is_admin_legacy or is_admin_rbac):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user
