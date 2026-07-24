from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime


class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal = Field(..., ge=0)
    stock: int = Field(default=0, ge=0)
    is_available: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    is_available: Optional[bool] = None


class ProductResponse(ProductBase):
    id: int
    is_deleted: bool
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
