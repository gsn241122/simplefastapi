from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.user.models import User
from app.core.database import get_db
from app.core.config import settings, DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.core.responses import APIResponse, PaginationMeta, StandardJSONResponse
from app.core.upload import save_upload_file, delete_file
from app.modules.product import crud, schemas
from app.modules.auth.routes import get_current_user

router = APIRouter(prefix="/products", tags=["Product Management"], dependencies=[Depends(get_current_user)])


@router.post("/", response_model=APIResponse, summary="Create product")
def create_product(
    product: schemas.ProductCreate, 
    current_user: Any = Depends(get_current_user),
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


@router.get("/", response_model=APIResponse, summary="List products")
def read_products(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"),
    search: str | None = Query(None, description="Search by product name"),
    db: Session = Depends(get_db),
):
    products, total = crud.get_products(db, skip=skip, limit=limit, search=search)
    response_data = [schemas.ProductResponse.model_validate(product) for product in products]
    return StandardJSONResponse.success(
        data=response_data,
        message="Products retrieved successfully",
        meta=PaginationMeta.create(total=total, skip=skip, limit=limit),
    )


@router.get("/{product_id}", response_model=APIResponse, summary="Get product by ID")
def read_product(product_id: int, db: Session = Depends(get_db)):
    db_product = crud.get_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    response_data = schemas.ProductResponse.model_validate(db_product)
    return StandardJSONResponse.success(data=response_data, message="Product retrieved successfully")


@router.put("/{product_id}", response_model=APIResponse, summary="Update product")
def update_product(
    product_id: int,
    product_update: schemas.ProductUpdate,
    current_user: Any = Depends(get_current_user),
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


@router.delete("/{product_id}", response_model=APIResponse, summary="Delete product")
def delete_product(
    product_id: int,
    current_user: Any = Depends(get_current_user),
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
    # Delete associated image file if exists
    if db_product.image_url:
        delete_file(db_product.image_url)
    return StandardJSONResponse.success(message="Product soft deleted successfully")


@router.post("/{product_id}/image", response_model=APIResponse, summary="Upload product image")
def upload_product_image(
    product_id: int,
    file: UploadFile = File(...),
    current_user: Any = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Hanya admin yang bisa mengunggah gambar produk
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required to upload product images."
        )
    
    # Get the product
    db_product = crud.get_product(db, product_id=product_id)
    if db_product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Delete old image if exists
    if db_product.image_url:
        delete_file(db_product.image_url)
    
    # Save new image
    image_url = save_upload_file(file, subdirectory="products")
    
    # Update product with image URL
    db_product.image_url = image_url
    db.commit()
    db.refresh(db_product)
    
    response_data = schemas.ProductResponse.model_validate(db_product)
    return StandardJSONResponse.success(
        data=response_data,
        message="Product image uploaded successfully"
    )


# Summary provider for aggregator
def get_summary(db, redis=None):
    """Return a small summary dict for the product module.

    Expected shape consumed by the aggregator:
    {
      "counts": {"products": int},
      "meta": {"module": "product"}
    }
    """
    try:
        _, total = crud.get_products(db, skip=0, limit=1)
    except Exception:
        total = 0
    return {"counts": {"products": total}, "meta": {"module": "product"}}
