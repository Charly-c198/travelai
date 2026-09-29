"""酒店查询 API（接入 RollingGo 道旅 MCP 真实可订房）"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.user import User
from app.services.rollinggo import search_hotels
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/hotels", tags=["Hotels"])


@router.get("")
async def search_hotels_api(
    place: str = Query(..., min_length=1, description="城市或地点名称"),
    place_type: str = Query("city", description="place 类型：city / geo / ..."),
    size: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """按地点搜索真实可订酒店（含价格与可追踪 bookingUrl）。"""
    try:
        return await search_hotels(place, place_type=place_type, size=size)
    except Exception as e:
        raise HTTPException(502, f"酒店查询失败: {e}")