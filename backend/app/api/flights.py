"""机票 CPS 深链接口（方案A）：返回预订落地页，前端"去购票"跳转并埋点。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.models.user import User
from app.services.flight_cps import build_flight_plan
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/flights", tags=["Flights"])


@router.get("")
async def search_flights(
    to: str = Query(..., description="目的地（如 上海）"),
    date: str = Query(..., description="去程日期 YYYY-MM-DD"),
    from_city: Optional[str] = Query(None, alias="from", description="出发地（缺省用 config 默认）"),
    return_date: Optional[str] = Query(None, description="返程日期"),
    current_user: User = Depends(get_current_user),
):
    """为指定 路线+日期 生成可追踪的机票预订落地页（无实时价格，走 CPS 深链）。"""
    plan = build_flight_plan(from_city, to, date, return_date)
    return {
        "success": True,
        "from": plan["from"],
        "to": plan["to"],
        "departure": plan["departure"],
        "return": plan["return"],
    }