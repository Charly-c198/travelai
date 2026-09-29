"""景点服务层"""
from typing import Optional, Dict, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.spot import Spot


def _spot_to_dict(spot: Spot) -> Dict[str, Any]:
    """将 Spot 模型转为 dict"""
    return {
        "id": str(spot.id),
        "name": spot.name,
        "name_en": spot.name_en,
        "city": spot.city,
        "country": spot.country,
        "category": spot.category,
        "address": spot.address,
        "latitude": spot.latitude,
        "longitude": spot.longitude,
        "rating": spot.rating,
        "ticket_info": spot.ticket_info or {},
        "description": spot.description,
        "recommend_duration": spot.recommend_duration,
        "tags": spot.tags or [],
    }


class SpotService:
    """景点业务服务"""

    async def get_spot_by_id(self, spot_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取景点详情"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Spot).where(Spot.id == spot_id))
            spot = result.scalar_one_or_none()
            return _spot_to_dict(spot) if spot else None

    async def list_spots(
        self,
        db: AsyncSession,
        city: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> list[Dict[str, Any]]:
        """分页查询景点列表（可供 CRUD 接口复用）"""
        stmt = select(Spot)
        if city:
            stmt = stmt.where(Spot.city == city)
        if category:
            stmt = stmt.where(Spot.category == category)
        stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        return [_spot_to_dict(s) for s in result.scalars().all()]