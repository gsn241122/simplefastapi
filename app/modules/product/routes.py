from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.responses import StandardJSONResponse
from app.modules.product import crud, schemas
from app.modules.auth.routes import get_current_user
from app.modules.user.models import User

router = APIRouter(prefix="/products", tags=["Product Management"])


@router.post("/", dependencies=[Depends(get_current_user)])
def create_product(
    product: schemas.ProductCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Hanya admin yang bisa membuat produk
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required to create products."
        )
    created_product = crud.create_product(db=db, product=product)
    response_data = schemas.ProductResponse.model_validate(created_product)
    return StandardJSONResponse.success(data=response_data, message="Product created successfully")


@router.get("/")
def read_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    products = crud.get_products(db, skip=skip, limit=limit)
    response_data = [schemas.ProductResponse.model_validate(product) for product in products]
    return StandardJSONResponse.success(data=response_data, message="Products retrieved successfully")


@router.get("/{product_id}")
def read_product(product_id: int, db: Session = Depends(get_db)):
    db_product = crud.get_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    response_data = schemas.ProductResponse.model_validate(db_product)
    return StandardJSONResponse.success(data=response_data, message="Product retrieved successfully")


@router.put("/{product_id}", dependencies=[Depends(get_current_user)])
def update_product(
    product_id: int,
    product_update: schemas.ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Hanya admin yang bisa mengupdate produk
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required to update products."
        )
    db_product = crud.update_product(db, product_id=product_id, product_update=product_update)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    response_data = schemas.ProductResponse.model_validate(db_product)
    return StandardJSONResponse.success(data=response_data, message="Product updated successfully")


@router.delete("/{product_id}", dependencies=[Depends(get_current_user)])
def delete_product(
    product_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Hanya admin yang bisa menghapus produk
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required to delete products."
        )
    db_product = crud.delete_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return StandardJSONResponse.success(message="Product soft deleted successfully")
