"""景点查询 API"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.trip import SpotOut
from app.services.spot_service import SpotService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/spots", tags=["Spots"])


@router.get("", response_model=list[SpotOut])
async def list_spots(
    city: Optional[str] = Query(None, description="按城市过滤"),
    category: Optional[str] = Query(None, description="按类别过滤"),
    keyword: Optional[str] = Query(None, description="关键词（名称/城市）"),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """分页/过滤查询景点（供规划页与搜索复用）。"""
    svc = SpotService()
    spots = await svc.list_spots(db, city=city, category=category, limit=limit)
    if keyword:
        k = keyword.lower()
        spots = [
            s for s in spots
            if k in (s.get("name") or "").lower() or k in (s.get("city") or "").lower()
        ]
    return [SpotOut(**s) for s in spots if s.get("id")]