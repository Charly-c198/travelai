"""机票 CPS（方案A）：不查实时价格，用预订落地页深链把用户推进到购票页。

RollingGo 已取消飞行 MCP，这里改为生成可追踪的机票搜索深链（默认携程移动端），
带渠道参数后可计入 CPS 返佣。链接模板在 config `FLIGHT_BOOKING_URL_TEMPLATE` 配置。
"""
from datetime import date as date_cls
from typing import Optional

from app.config import get_settings

settings = get_settings()


def _fmt_date(d) -> str:
    if isinstance(d, date_cls):
        return d.strftime("%Y-%m-%d")
    return str(d)[:10]


def _build_url(origin: str, dest: str, ddate: str) -> str:
    return settings.FLIGHT_BOOKING_URL_TEMPLATE.format(
        **{"from": origin, "to": dest, "date": ddate},
    )


def build_flight_plan(
    origin: Optional[str],
    dest: str,
    date,
    return_date=None,
) -> dict:
    """生成去程(+返程)购票落地页。返回 {departure, return} 各一条可追踪 booking_url。"""
    origin = (origin or settings.FLIGHT_DEFAULT_ORIGIN or "").strip() or "出发地"
    opt = {
        "from": origin,
        "to": dest,
        "date": _fmt_date(date),
        "booking_url": _build_url(origin, dest, _fmt_date(date)),
    }
    plan = {"from": origin, "to": dest, "departure": opt, "return": None}
    if return_date and return_date != date:
        plan["return"] = {
            "from": dest,
            "to": origin,
            "date": _fmt_date(return_date),
            "booking_url": _build_url(dest, origin, _fmt_date(return_date)),
        }
    return plan