"""行程 CRUD API"""
import logging
import secrets
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.trip import Trip
from app.models.user import User
from app.models.spot import Spot
from app.models.shared_trip import SharedTrip
from app.schemas.trip import TripCreate, TripUpdate, TripOut, TripListOut
from app.agent.graph import run_travel_agent
from app.services.amap_service import enrich_itinerary
from app.services.quota_service import check_and_consume
from app.services.rate_limit import check_rate
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/trips", tags=["Trips"])
share_router = APIRouter(prefix="/api/v1/s", tags=["Share"])
logger = logging.getLogger(__name__)


def _trip_to_out(trip: Trip) -> TripOut:
    return TripOut(
        id=str(trip.id),
        user_id=str(trip.user_id),
        title=trip.title,
        destination=trip.destination,
        start_date=trip.start_date,
        end_date=trip.end_date,
        budget=trip.budget or 0,
        travelers=trip.travelers or 1,
        status=trip.status or "planning",
        requirements=trip.requirements,
        generated_plan=trip.generated_plan,
        created_at=trip.created_at,
        updated_at=trip.updated_at,
    )


async def _get_own_trip(db: AsyncSession, trip_id: str, user_id) -> Trip:
    """按 id + 所属用户取行程；非本人一律 404（防枚举）。"""
    try:
        tid = uuid.UUID(trip_id)
    except (ValueError, AttributeError):
        raise HTTPException(404, "行程不存在")
    result = await db.execute(select(Trip).where(Trip.id == tid, Trip.user_id == user_id))
    trip = result.scalar_one_or_none()
    if trip is None:
        raise HTTPException(404, "行程不存在")
    return trip


@router.post("", response_model=TripOut, status_code=201)
async def create_trip(
    data: TripCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建行程（默认归属当前用户）。"""
    trip = Trip(
        user_id=current_user.id,
        title=data.title or f"{data.destination}之旅",
        destination=data.destination,
        start_date=data.start_date,
        end_date=data.end_date,
        budget=data.budget or 0,
        travelers=data.travelers or 1,
        status=data.status or "planning",
        requirements=data.requirements or {},
        generated_plan=data.generated_plan,
    )
    db.add(trip)
    await db.commit()
    await db.refresh(trip)
    return _trip_to_out(trip)


@router.get("", response_model=TripListOut)
async def list_trips(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """分页列出当前用户的行程（按创建时间倒序）。"""
    total = (
        await db.execute(
            select(func.count()).select_from(Trip).where(Trip.user_id == current_user.id)
        )
    ).scalar_one()
    stmt = (
        select(Trip)
        .where(Trip.user_id == current_user.id)
        .order_by(Trip.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = list((await db.execute(stmt)).scalars())
    return TripListOut(
        items=[_trip_to_out(t) for t in rows],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


@router.get("/{trip_id}", response_model=TripOut)
async def get_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trip = await _get_own_trip(db, trip_id, current_user.id)
    # 计划有正文/天数但缺坐标 → 自动从正文抽景点名+高德补坐标（一次性，回写 DB，之后秒开）
    # name_en 一并回填（spots 表精确名匹配）：有英文名=可验证的真地点，图鉴才能按景点配图。
    gp = trip.generated_plan or {}
    if (gp.get("content") or gp.get("days")) and not any(
        s.get("latitude") and s.get("longitude") for s in (gp.get("spots") or [])
    ):
        try:
            async def _lookup_name_en(n: str) -> Optional[str]:
                try:
                    row = (
                        await db.execute(select(Spot.name_en).where(Spot.name == n).limit(1))
                    ).scalar_one_or_none()
                    return row or None
                except Exception:
                    return None

            enriched = await enrich_itinerary(gp, trip.destination or "", name_en_lookup=_lookup_name_en)
            if enriched:
                gp["spots"] = enriched
                trip.generated_plan = gp
                await db.commit()
        except Exception as e:
            logger.warning(f"行程坐标补全失败: {e}")
    return _trip_to_out(trip)


@router.put("/{trip_id}", response_model=TripOut)
async def update_trip(
    trip_id: str,
    data: TripUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    trip = await _get_own_trip(db, trip_id, current_user.id)
    updates = data.model_dump(exclude_unset=True)
    if "title" in updates and not updates.get("title"):
        updates["title"] = f"{trip.destination}之旅"
    for k, v in updates.items():
        setattr(trip, k, v)
    await db.commit()
    await db.refresh(trip)
    return _trip_to_out(trip)


@router.delete("/{trip_id}", status_code=204)
async def delete_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # ORM 级联会同时删除 itinerary_days/itinerary_spots/bookings
    trip = await _get_own_trip(db, trip_id, current_user.id)
    await db.delete(trip)
    await db.commit()


@router.post("/{trip_id}/generate", response_model=TripOut)
async def generate_trip_plan(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为（暂无AI计划的）行程一键生成计划并存入。同步跑 Agent（约 1 分钟）。"""
    trip = await _get_own_trip(db, trip_id, current_user.id)
    await check_rate(str(current_user.id))
    days = max(1, (trip.end_date - trip.start_date).days + 1)
    # 额度控制：仅全新生成本计数
    ok, _u = await check_and_consume(db, str(current_user.id))
    if not ok:
        raise HTTPException(429, "今日免费生成次数已用完，升级 Pro 可无限次生成")
    # 带真实起止日期，让解析拿到实际天数/区间 → 生成的行程严格对应行程约束
    msg = f"去{trip.destination}玩{days}天，日期{trip.start_date}到{trip.end_date}，{trip.travelers or 1}人"
    if trip.budget:
        msg += f"，预算{trip.budget}元"
    result = await run_travel_agent(
        user_id=str(current_user.id),
        user_message=msg,
        db=db,
        skip_cache=True,  # 显式"一键生成"：按当前行程约束强制重新生成，不复用容差内旧计划
    )
    if not (result.get("draft_itinerary") or {}).get("content"):
        raise HTTPException(500, "行程生成失败，请重试")
    trip.generated_plan = result["draft_itinerary"]
    trip.requirements = {"intent": result.get("intent")}
    await db.commit()
    await db.refresh(trip)
    return _trip_to_out(trip)


@router.post("/{trip_id}/share", response_model=dict)
async def share_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """为本人行程生成公开分享短链接（token 只生成一次并复用）。"""
    trip = await _get_own_trip(db, trip_id, current_user.id)
    result = await db.execute(select(SharedTrip).where(SharedTrip.trip_id == trip.id))
    st = result.scalar_one_or_none()
    if st is None:
        st = SharedTrip(token=secrets.token_hex(8), trip_id=trip.id, created_by=current_user.id)
        db.add(st)
        await db.commit()
        await db.refresh(st)
    return {"token": st.token, "url": f"/s/{st.token}"}


@share_router.get("/{token}", response_model=TripOut)
async def view_shared_trip(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """公开查看分享的行程（无需登录）。"""
    result = await db.execute(select(SharedTrip).where(SharedTrip.token == token))
    st = result.scalar_one_or_none()
    if st is None:
        raise HTTPException(404, "分享不存在或已失效")
    trip = (await db.execute(select(Trip).where(Trip.id == st.trip_id))).scalar_one_or_none()
    if trip is None:
        raise HTTPException(404, "分享的行程已不存在")
    return _trip_to_out(trip)