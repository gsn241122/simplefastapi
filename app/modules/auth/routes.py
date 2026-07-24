from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from typing import Optional
from jose import JWTError, jwt
from app.core.database import get_db
from app.core.security import verify_password, get_password_hash
from app.core.config import settings
from app.core.responses import StandardJSONResponse
from app.modules.user import crud, schemas
from app.modules.user.models import User

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
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


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    db_email = crud.get_user_by_email(db, email=user.email)
    if db_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hanya admin yang bisa mendaftarkan user dengan role admin
    if hasattr(user, 'role') and user.role == "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot register as admin. Admin must be created by existing admin."
        )
    
    # Hash password before storing
    user_data = user.model_dump()
    user_data["hashed_password"] = get_password_hash(user.password)
    del user_data["password"]
    
    created_user = crud.create_user(db=db, user_data=user_data)
    response_data = schemas.UserResponse.model_validate(created_user)
    return StandardJSONResponse.success(data=response_data, message="User registered successfully")


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login and get access token."""
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
            detail="User account is inactive or deleted"
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    return StandardJSONResponse.success(
        data={"access_token": access_token, "token_type": "bearer"},
        message="Login successful"
    )


@router.get("/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    response_data = schemas.UserResponse.model_validate(current_user)
    return StandardJSONResponse.success(data=response_data, message="Current user retrieved successfully")
