from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    bio: Optional[str] = Field(None, max_length=2000)
    password: Optional[str] = Field(None, min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    bio: str
    created_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field("", max_length=5000)
    price: float = Field(..., gt=0)
    stock: int = Field(0, ge=0)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    price: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = Field(None, ge=0)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    price: float
    stock: int
    created_at: datetime


class OrderItemIn(BaseModel):
    product_id: int
    quantity: int
    price: Optional[float] = None  # client-supplied unit price (business-logic probe)


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1, max_length=20)


class OrderCreate(BaseModel):
    items: List[OrderItemIn] = Field(..., min_length=1)
    status: Optional[str] = Field(None, max_length=20)  # client-supplied status probe


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity: int
    price: float


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: str
    total_amount: float
    created_at: datetime
    items: List[OrderItemOut] = []


class AdminStats(BaseModel):
    users: int
    products: int
    orders: int
    total_revenue: float