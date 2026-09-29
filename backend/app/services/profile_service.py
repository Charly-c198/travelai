"""用户画像服务：沉淀旅行偏好（风格/目的地），用于个性化生成。"""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_profile import UserProfile


def _to_uuid(user_id) -> UUID:
    """将 user_id（str 或 UUID）转为 UUID 对象，匹配 UUID 列的绑定类型"""
    return user_id if isinstance(user_id, UUID) else UUID(str(user_id))


def _to_dict(p: UserProfile) -> dict:
    return {
        "travel_style": p.travel_style or "",
        "travel_styles": p.travel_styles or {},
        "destinations": p.destinations or [],
    }


async def get_profile(db: AsyncSession, user_id) -> dict:
    """读取用户画像；无则返回空 dict。"""
    user_uuid = _to_uuid(user_id)
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_uuid))
    p = result.scalar_one_or_none()
    return _to_dict(p) if p else {}


async def record_trip(
    db: AsyncSession,
    user_id,
    travel_style: Optional[str] = None,
    destination: Optional[str] = None,
) -> dict:
    """记录一次旅行的风格/目的地；画像风格取"最常见的风格"。"""
    user_uuid = _to_uuid(user_id)
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_uuid))
    p = result.scalar_one_or_none()
    if p is None:
        p = UserProfile(user_id=user_uuid)
        db.add(p)

    styles = dict(p.travel_styles or {})
    if travel_style:
        styles[travel_style] = styles.get(travel_style, 0) + 1
    if styles:
        p.travel_style = max(styles, key=styles.get)
    p.travel_styles = styles

    dests = list(p.destinations or [])
    if destination and destination not in dests:
        dests.append(destination)
        p.destinations = dests[-50:]  # 控制长度

    await db.commit()
    # 回读
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_uuid))
    return _to_dict(result.scalar_one())