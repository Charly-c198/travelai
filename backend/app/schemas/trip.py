"""行程相关 Pydantic 模型"""
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field


class TripBase(BaseModel):
    destination: str = Field(..., min_length=1, max_length=200, description="目的地")
    start_date: date
    end_date: date
    budget: Optional[int] = 0
    travelers: Optional[int] = 1
    status: Optional[str] = "planning"
    requirements: Optional[Dict[str, Any]] = None
    # AI 生成的行程（含 content / days / spots_used 等）
    generated_plan: Optional[Dict[str, Any]] = None
    title: Optional[str] = Field(default=None, max_length=200, description="行程标题，缺省自动生成")


class TripCreate(TripBase):
    pass


class TripUpdate(BaseModel):
    title: Optional[str] = None
    destination: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    budget: Optional[int] = None
    travelers: Optional[int] = None
    status: Optional[str] = None
    requirements: Optional[Dict[str, Any]] = None
    generated_plan: Optional[Dict[str, Any]] = None


class TripOut(BaseModel):
    id: str
    user_id: str
    title: str
    destination: str
    start_date: date
    end_date: date
    budget: int = 0
    travelers: int = 1
    status: str = "planning"
    requirements: Optional[Dict[str, Any]] = None
    generated_plan: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TripListOut(BaseModel):
    items: List[TripOut]
    total: int
    page: int
    page_size: int
    has_more: bool


class SpotOut(BaseModel):
    id: str
    name: str
    name_en: Optional[str] = None
    city: str
    country: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    rating: float = 0
    ticket_info: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    recommend_duration: int = 120
    tags: Optional[List[str]] = []