"""商业仪表盘 API：汇总 LLM 成本/延迟指标 + CPS 漏斗 + 今日额度。

供前端 /dashboard 页展示"单会话成本/首字段延迟/转化漏斗"（商业化北极星观测）。
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.generation_metric import GenerationMetric
from app.models.tracking_event import TrackingEvent
from app.models.user import User
from app.services.llm_metrics import percentile
from app.services.quota_service import get_usage
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/dashboard", tags=["Dashboard"])


async def _generation_stats(db: AsyncSession, since: datetime) -> dict:
    rows = list((await db.execute(
        select(GenerationMetric).where(GenerationMetric.created_at >= since)
    )).scalars())
    if not rows:
        return {
            "count": 0, "first_token_p50": None, "first_token_p95": None,
            "total_p50": None, "total_p95": None,
            "prompt_tokens": 0, "completion_tokens": 0,
            "total_cost": 0.0, "avg_cost": 0.0,
            "per_day": [],
        }
    first_ms = [r.first_token_ms for r in rows if r.first_token_ms]
    total_ms = [r.total_ms for r in rows if r.total_ms]
    pt = sum(r.prompt_tokens or 0 for r in rows)
    ct = sum(r.completion_tokens or 0 for r in rows)
    cost = round(sum(r.cost or 0 for r in rows), 4)

    # 按日聚合（生成次数 + 成本 + token）
    day_map = {}
    for r in rows:
        d = (r.created_at or datetime.utcnow()).strftime("%Y-%m-%d")
        e = day_map.setdefault(d, {"date": d, "count": 0, "cost": 0.0, "tokens": 0})
        e["count"] += 1
        e["cost"] = round(e["cost"] + (r.cost or 0), 4)
        e["tokens"] += (r.prompt_tokens or 0) + (r.completion_tokens or 0)
    per_day = sorted(day_map.values(), key=lambda x: x["date"])

    return {
        "count": len(rows),
        "first_token_p50": percentile(first_ms, 50),
        "first_token_p95": percentile(first_ms, 95),
        "total_p50": percentile(total_ms, 50),
        "total_p95": percentile(total_ms, 95),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_cost": cost,
        "avg_cost": round(cost / len(rows), 4),
        "per_day": per_day,
    }


async def _cps_funnel(db: AsyncSession, since: datetime) -> dict:
    """CPS 漏斗：曝光(trip_view) → 点击(booking_click) → 预订(booking_success)。"""
    rows = list((await db.execute(
        select(TrackingEvent.event, func.count())
        .where(TrackingEvent.created_at >= since)
        .group_by(TrackingEvent.event)
    )).all())
    totals = {e: n for e, n in rows}
    trip_view = totals.get("trip_view", 0)
    booking_click = totals.get("booking_click", 0)
    booking_success = totals.get("booking_success", 0)
    return {
        "trip_view": trip_view,
        "booking_click": booking_click,
        "booking_success": booking_success,
        "click_rate": round(booking_click / trip_view, 4) if trip_view else None,
        "conversion": round(booking_success / trip_view, 4) if trip_view else None,
    }


@router.get("/summary")
async def summary(
    days: int = Query(7, ge=1, le=90),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """近 N 天商业仪表盘数据。"""
    since = datetime.utcnow() - timedelta(days=days)
    generation = await _generation_stats(db, since)
    cps = await _cps_funnel(db, since)
    usage = await get_usage(db, current_user.id)
    return {
        "days": days,
        "generation": generation,
        "cps": cps,
        "quota": {"user_id": str(current_user.id), **usage},
    }
