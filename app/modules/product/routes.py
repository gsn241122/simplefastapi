from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.responses import StandardJSONResponse
from app.modules.product import crud, schemas

router = APIRouter(prefix="/products", tags=["Product Management"])


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
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


@router.put("/{product_id}")
def update_product(
    product_id: int,
    product_update: schemas.ProductUpdate,
    db: Session = Depends(get_db)
):
    db_product = crud.update_product(db, product_id=product_id, product_update=product_update)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    response_data = schemas.ProductResponse.model_validate(db_product)
    return StandardJSONResponse.success(data=response_data, message="Product updated successfully")


@router.delete("/{product_id}", status_code=status.HTTP_200_OK)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    db_product = crud.delete_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return StandardJSONResponse.success(message="Product soft deleted successfully")
