"""行程相关的服务函数：对话内"保存到我的行程"等动作复用。

注意：id/user_id 列是 sqlalchemy UUID 类型（即便底层 SQLite），收字符串必须先归一化为
UUID 对象（见 memory 的 UUID 列坑），否则查询/写入会报 'str' object has no attribute 'hex'。
"""
import logging
import uuid
from datetime import date as date_cls, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trip import Trip

logger = logging.getLogger(__name__)


def _to_date(v) -> Optional[date_cls]:
    """字符串/date/None → date 对象。"""
    if v is None or v == "":
        return None
    if isinstance(v, date_cls):
        return v
    try:
        return date_cls(*[int(x) for x in str(v).split("-")[:3]])
    except Exception:
        return None


def _to_uuid(user_id) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(user_id))
    except Exception:
        return None


async def save_trip_from_plan(
    db: AsyncSession,
    user_id,
    destination: str,
    start_date,
    end_date,
    plan: dict,
    title: Optional[str] = None,
    trip_id: Optional[str] = None,
) -> Optional[str]:
    """把一份行程（generated_plan）保存到「我的行程」。

    - 给了 trip_id 且属于该用户 → 更新该行程；
    - 否则新建一条 Trip。
    返回 trip id（str）；失败返回 None。
    """
    uid = _to_uuid(user_id)
    if uid is None or not (destination or "").strip():
        return None
    plan = plan or {}
    # trips.start_date/end_date 是 NOT NULL：缺省时用明天起 + 行程天数（兜底 3 天）
    days = len((plan.get("days") or []) or []) or 3
    start = _to_date(start_date) or (date_cls.today() + timedelta(days=1))
    end = _to_date(end_date) or (start + timedelta(days=max(1, days - 1)))

    if trip_id:
        tid = _to_uuid(trip_id)
        if tid:
            try:
                row = (
                    await db.execute(select(Trip).where(Trip.id == tid, Trip.user_id == uid))
                ).scalar_one_or_none()
                if row is not None:
                    row.destination = destination
                    if start:
                        row.start_date = start
                    if end:
                        row.end_date = end
                    if title:
                        row.title = title
                    row.generated_plan = plan
                    await db.commit()
                    await db.refresh(row)
                    return str(row.id)
            except Exception as e:
                logger.warning(f"更新行程失败(降级为新建): {e}")

    trip = Trip(
        user_id=uid,
        title=title or f"{destination}之旅",
        destination=destination,
        start_date=start,
        end_date=end,
        budget=0,
        travelers=1,
        status="planning",
        requirements={},
        generated_plan=plan,
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)
    return str(trip.id)
