from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.core.security import get_password_hash, require_admin
from app.modules.user import crud, schemas
from app.modules.auth.routes import get_current_user
from app.modules.user.models import User

router = APIRouter(prefix="/users", tags=["User Management"], dependencies=[Depends(get_current_user)])


@router.get("/", response_model=APIResponse, summary="List semua user")
def read_users(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by username, email, or full name"),
    db: Session = Depends(get_db),
):
    items, total = crud.get_users(db, skip=skip, limit=limit, search=search)
    response_data = [schemas.UserResponse.model_validate(user) for user in items]
    return StandardJSONResponse.success(
        data=response_data,
        message="Users retrieved successfully",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    db_email = crud.get_user_by_email(db, email=user.email)
    if db_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password before storing
    user_data = user.model_dump()
    user_data["hashed_password"] = get_password_hash(user.password)
    del user_data["password"]
    
    created_user = crud.create_user(db=db, user_data=user_data)
    response_data = schemas.UserResponse.model_validate(created_user)
    return StandardJSONResponse.success(data=response_data, message="User created successfully")


@router.get("/{user_id}", response_model=APIResponse, summary="Get user by ID")
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    response_data = schemas.UserResponse.model_validate(db_user)
    return StandardJSONResponse.success(data=response_data, message="User retrieved successfully")


@router.put("/{user_id}", response_model=APIResponse, summary="Update user")
def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Cek apakah user yang login adalah admin atau mengupdate diri sendiri
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. You can only update your own profile."
        )
    
    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data and update_data["password"] is not None:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    
    # Hanya admin yang bisa mengubah role
    if "role" in update_data and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change user roles."
        )
    
    db_user = crud.update_user(db, user_id=user_id, user_update_data=update_data)
    response_data = schemas.UserResponse.model_validate(db_user)
    return StandardJSONResponse.success(data=response_data, message="User updated successfully")


@router.delete("/{user_id}", response_model=APIResponse, summary="Delete user")
def delete_user(
    user_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Hanya admin yang bisa menghapus user
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required to delete users."
        )
    
    db_user = crud.delete_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return StandardJSONResponse.success(message="User soft deleted successfully")
