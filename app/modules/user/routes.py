from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.responses import StandardJSONResponse, APIResponse
from app.modules.user import crud, schemas

router = APIRouter(prefix="/users", tags=["User Management"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    db_email = crud.get_user_by_email(db, email=user.email)
    if db_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    created_user = crud.create_user(db=db, user=user)
    response_data = schemas.UserResponse.model_validate(created_user)
    return StandardJSONResponse.success(data=response_data, message="User created successfully")


@router.get("/")
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db, skip=skip, limit=limit)
    response_data = [schemas.UserResponse.model_validate(user) for user in users]
    return StandardJSONResponse.success(data=response_data, message="Users retrieved successfully")


@router.get("/{user_id}")
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    response_data = schemas.UserResponse.model_validate(db_user)
    return StandardJSONResponse.success(data=response_data, message="User retrieved successfully")


@router.put("/{user_id}")
def update_user(
    user_id: int,
    user_update: schemas.UserUpdate,
    db: Session = Depends(get_db)
):
    db_user = crud.update_user(db, user_id=user_id, user_update=user_update)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    response_data = schemas.UserResponse.model_validate(db_user)
    return StandardJSONResponse.success(data=response_data, message="User updated successfully")


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.delete_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return StandardJSONResponse.success(message="User soft deleted successfully")
