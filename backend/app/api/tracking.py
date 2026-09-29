"""商业埋点 API：记录 CPS 漏斗事件（曝光/点击/预订…），并返回漏斗汇总。"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.tracking_event import TrackingEvent
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/tracking", tags=["Tracking"])


class TrackIn(BaseModel):
    event: str
    channel: str = ""
    trip_id: Optional[str] = None
    meta: Dict[str, Any] = {}


@router.post("", status_code=201)
async def track(
    data: TrackIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """记录一个埋点事件（best-effort，异常不影响主流程）。"""
    try:
        tid = uuid.UUID(data.trip_id) if data.trip_id else None
    except (ValueError, AttributeError):
        tid = None
    ev = TrackingEvent(
        user_id=current_user.id,
        event=data.event,
        channel=data.channel or "",
        trip_id=tid,
        meta=data.meta or {},
    )
    db.add(ev)
    await db.commit()
    return {"ok": True}


@router.get("/summary")
async def summary(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """近 N 天按 事件+渠道 汇总（供漏斗报表/dashboard）。"""
    since = datetime.utcnow() - timedelta(days=days)
    rows = (
        await db.execute(
            select(TrackingEvent.event, TrackingEvent.channel, func.count())
            .where(TrackingEvent.created_at >= since)
            .group_by(TrackingEvent.event, TrackingEvent.channel)
        )
    ).all()
    # 计算漏斗：把常见事件按序凑成漏斗
    funnel = [{"event": e, "channel": c, "count": n} for e, c, n in rows]
    # 各事件总数（不分渠道）
    totals = {}
    for e, c, n in rows:
        totals[e] = totals.get(e, 0) + n
    return {"days": days, "funnel": funnel, "totals": totals}