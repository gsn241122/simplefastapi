from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, Any
from app.modules.user.models import User


def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id, User.is_deleted == False).first()


def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username, User.is_deleted == False).first()


def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email, User.is_deleted == False).first()


def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).filter(User.is_deleted == False).offset(skip).limit(limit).all()


def create_user(db: Session, user_data: Dict[str, Any]):
    # Set default role if not provided
    if "role" not in user_data or user_data["role"] is None:
        user_data["role"] = "user"
    db_user = User(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def update_user(db: Session, user_id: int, user_update_data: Dict[str, Any]):
    db_user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if db_user:
        for key, value in user_update_data.items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id: int):
    db_user = db.query(User).filter(User.id == user_id, User.is_deleted == False).first()
    if db_user:
        db_user.is_deleted = True
        db_user.deleted_at = datetime.utcnow()
        db.commit()
    return db_user

