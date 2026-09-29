"""额度/订阅服务：每日高质量生成免费额度控制 + Pro 权益。"""
from datetime import datetime
from typing import Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.quota_usage import QuotaUsage

settings = get_settings()


def _to_uuid(user_id) -> UUID:
    """将 user_id（str 或 UUID）转为 UUID 对象，匹配 UUID 列的绑定类型"""
    return user_id if isinstance(user_id, UUID) else UUID(str(user_id))


def _today() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")


def _limit(plan: str) -> int:
    return settings.PRO_DAILY_GENERATIONS if plan == "pro" else settings.FREE_DAILY_GENERATIONS


def _usage(row, plan, limit) -> dict:
    return {"date": row.date if row else _today(), "plan": plan, "used": row.used_count if row else 0,
            "limit": limit, "remaining": max(0, limit - (row.used_count if row else 0))}


async def get_usage(db: AsyncSession, user_id) -> dict:
    """读取今日用量（不新建行）。"""
    user_uuid = _to_uuid(user_id)
    r = await db.execute(select(QuotaUsage).where(QuotaUsage.user_id == user_uuid, QuotaUsage.date == _today()))
    row = r.scalar_one_or_none()
    plan = row.plan if row else "free"
    return _usage(row, plan, _limit(plan))


async def check_and_consume(db: AsyncSession, user_id) -> Tuple[bool, dict]:
    """今日额度内则消耗一次并返回 True；超额度返回 False。新建当日行。"""
    user_uuid = _to_uuid(user_id)
    r = await db.execute(select(QuotaUsage).where(QuotaUsage.user_id == user_uuid, QuotaUsage.date == _today()))
    row = r.scalar_one_or_none()
    if row is None:
        row = QuotaUsage(user_id=user_uuid, date=_today(), used_count=0, plan="free")
        db.add(row)
        await db.flush()
    limit = _limit(row.plan)
    if row.used_count >= limit:
        await db.commit()
        return False, _usage(row, row.plan, limit)
    row.used_count += 1
    await db.commit()
    return True, _usage(row, row.plan, limit)


async def set_plan(db: AsyncSession, user_id, plan: str) -> str:
    """设置用户权益(free/pro)。"""
    user_uuid = _to_uuid(user_id)
    r = await db.execute(select(QuotaUsage).where(QuotaUsage.user_id == user_uuid, QuotaUsage.date == _today()))
    row = r.scalar_one_or_none()
    if row is None:
        row = QuotaUsage(user_id=user_uuid, date=_today(), used_count=0, plan=plan)
        db.add(row)
    else:
        row.plan = plan
    await db.commit()
    return plan