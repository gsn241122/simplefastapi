from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime, timezone
from typing import Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.user.models import User
from jose import JWTError, jwt
import redis

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash
from app.core.config import settings
from app.core.responses import StandardJSONResponse
from app.modules.user import crud, schemas

# ─── Redis Client ────────────────────────────────────────────────────────────────
_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis | None:
    """Lazily create and return the Redis client, or None if disabled/unavailable."""
    global _redis_client
    if not settings.REDIS_ENABLE:
        return None
    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            _redis_client.ping()  # verify connectivity
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Redis unavailable — token IP-binding disabled: %s", exc
            )
            _redis_client = None
    return _redis_client

# ─── Router & OAuth2 Scheme ──────────────────────────────────────────────────────
router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login-swagger",
    auto_error=True,
    scheme_name="bearer",
    description="JWT Bearer Token",
    scopes={
        "read": "Read access",
        "write": "Write access",
    },
)


# ─── Helpers ──────────────────────────────────────────────────────────────────────
def _get_client_ip(request: Request) -> str:
    """Extract the real client IP, respecting proxy headers."""
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.client.host


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _store_token_in_redis(ip_address: str, token: str, username: str) -> None:
    """Persist token ↔ IP binding in Redis with TTL (no-op if Redis is unavailable)."""
    client = _get_redis()
    if client is None:
        return
    try:
        client.set(
            f"{settings.REDIS_PREFIX}:ip:{ip_address}:token:{token}",
            username,
            ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Redis set failed: %s", exc)


def _remove_token_from_redis(ip_address: str, token: str) -> None:
    """Remove a token from Redis (logout). No-op if Redis is unavailable."""
    client = _get_redis()
    if client is None:
        return
    try:
        client.delete(f"{settings.REDIS_PREFIX}:ip:{ip_address}:token:{token}")
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Redis delete failed: %s", exc)


# ─── Dependencies ─────────────────────────────────────────────────────────────────
async def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
 ) -> Any:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. Verify token exists in Redis (bound to client IP)
    #    If Redis is unavailable, skip IP binding check and rely on JWT alone.
    ip_address = _get_client_ip(request)
    client = _get_redis()
    if client is not None:
        try:
            if not client.exists(f"{settings.REDIS_PREFIX}:ip:{ip_address}:token:{token}"):
                raise credentials_exception
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "Redis check failed (falling back to JWT-only auth): %s", exc
            )

    # 2. Decode & validate JWT payload
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 3. Fetch user from DB
    user = crud.get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception

    if user.is_deleted or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or deleted",
        )

    return user


async def get_current_user_with_token(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
 ) -> tuple[Any, str]:
    """Same as get_current_user but also returns the raw token (needed for logout)."""
    user = await get_current_user(request=request, token=token, db=db)
    return user, token


# ─── Public Endpoints ─────────────────────────────────────────────────────────────
@router.get("/get-real-ip")
async def get_real_ip(request: Request):
    """Return the detected client IP (useful for debugging proxy setups)."""
    return {"real_client_ip": _get_client_ip(request)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    if crud.get_user_by_username(db, username=user.username):
        raise HTTPException(status_code=400, detail="Username already registered")

    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    # Prevent self-registration as admin
    if getattr(user, "role", None) == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot register as admin. Admin must be created by an existing admin.",
        )

    user_data = user.model_dump()
    user_data["hashed_password"] = get_password_hash(user_data.pop("password"))

    created_user = crud.create_user(db=db, user_data=user_data)
    response_data = schemas.UserResponse.model_validate(created_user)

    return StandardJSONResponse.success(
        data=response_data, message="User registered successfully"
    )


@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate with username/password and receive a JWT access token."""
    user = crud.get_user_by_username(db, username=form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.is_deleted or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or deleted",
        )

    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    _store_token_in_redis(_get_client_ip(request), access_token, user.username)

    return StandardJSONResponse.success(
        data={"access_token": access_token, "token_type": "bearer"},
        message="Login successful",
    )


@router.post("/login-swagger")
async def login_for_swagger(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    Login endpoint tailored for Swagger UI (expects x-www-form-urlencoded).
    Returns access_token with scope for OpenAPI compatibility.
    """
    user = crud.get_user_by_username(db, username=form_data.username)

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.is_deleted or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive or deleted",
        )

    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    _store_token_in_redis(_get_client_ip(request), access_token, user.username)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "scope": "read write",
    }


# ─── Protected Endpoints ──────────────────────────────────────────────────────────
@router.get("/me")
def read_users_me(current_user: Any = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    response_data = schemas.UserResponse.model_validate(current_user)
    return StandardJSONResponse.success(
        data=response_data, message="Current user retrieved successfully"
    )


@router.post("/logout")
async def logout(
    request: Request,
    auth: tuple[Any, str] = Depends(get_current_user_with_token),
):
    """Invalidate the current token (logout)."""
    _, token = auth
    _remove_token_from_redis(_get_client_ip(request), token)
    return StandardJSONResponse.success(data=None, message="Logout successful")