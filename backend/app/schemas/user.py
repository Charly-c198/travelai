"""用户相关 Pydantic 模型"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class UserCreate(BaseModel):
    """注册请求"""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    name: Optional[str] = Field(default=None, max_length=100)


class UserLogin(BaseModel):
    """登录请求"""
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """用户信息响应"""
    id: UUID
    email: EmailStr
    name: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class Token(BaseModel):
    """Token 响应"""
    access_token: str
    token_type: str = "bearer"
    user: Optional[UserOut] = None