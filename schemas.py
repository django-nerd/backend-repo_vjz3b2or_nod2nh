"""
Database Schemas for Giftnama (E-commerce)

Each Pydantic model represents a MongoDB collection. The collection name is the lowercase of the class name.

Examples:
- Product -> "product"
- Order -> "order"
- Category -> "category"
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class ProductImage(BaseModel):
    url: str = Field(..., description="Public image URL")
    alt: Optional[str] = Field(None, description="Alt text for accessibility")


class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field("", description="Detailed description")
    price: float = Field(..., ge=0, description="Price in USD")
    category: Optional[str] = Field(None, description="Primary category")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")
    images: List[ProductImage] = Field(default_factory=list, description="Product images")
    rating: Optional[float] = Field(4.8, ge=0, le=5, description="Average rating 0-5")
    in_stock: bool = Field(True, description="Whether product is in stock")
    stock_qty: Optional[int] = Field(50, ge=0, description="Quantity available")


class OrderItem(BaseModel):
    product_id: str = Field(..., description="Referenced product _id as string")
    title: str = Field(..., description="Snapshot of product title at purchase time")
    price: float = Field(..., ge=0, description="Price at purchase time")
    quantity: int = Field(..., ge=1, description="Units purchased")
    image: Optional[str] = Field(None, description="Primary image URL")


class CustomerInfo(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str = "US"


class Order(BaseModel):
    items: List[OrderItem]
    subtotal: float = Field(..., ge=0)
    shipping: float = Field(0.0, ge=0)
    tax: float = Field(0.0, ge=0)
    total: float = Field(..., ge=0)
    customer: CustomerInfo
    status: str = Field("processing", description="processing | shipped | delivered | cancelled")


# Optional: Category schema if needed later
class Category(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
