"""相似行程缓存：命中相似已生成行程时直接复用，避免重复昂贵 LLM 生成。

- 存储：plan_cache 表，按 cache_key（目的地|天数|风格|预算档）去重、保留最新。
- 命中规则（get_cached_plan）：同目的地 + 风格一致(或未知) + 天数±1 + 预算±30%。
- 所有函数 best-effort，任何失败不影响主流程。
"""
import logging
import re
from datetime import date as date_cls, datetime, timedelta
from typing import Dict, Optional, Any

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.plan_cache import PlanCache

logger = logging.getLogger(__name__)


_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn_to_int(s: str) -> Optional[int]:
    """中文数字 → 整数（支持一~三十九；ASCII 数字原样返回）。"""
    s = (s or "").strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if s in _CN_NUM:
        return _CN_NUM[s]
    if len(s) == 2 and s[0] == "十" and s[1] in _CN_NUM:
        return 10 + _CN_NUM[s[1]]
    if len(s) == 2 and s[0] in _CN_NUM and s[1] == "十":
        return _CN_NUM[s[0]] * 10
    if len(s) == 3 and s[0] in _CN_NUM and s[1] == "十" and s[2] in _CN_NUM:
        return _CN_NUM[s[0]] * 10 + _CN_NUM[s[2]]
    return None


def derive_days(user_message: str, start_date, end_date) -> Optional[int]:
    """从日期区间或 "N天/三天" 推断行程天数。

    用负向断言排除"第3天/第二天"这类"行程内天序"（不是时长），避免误判。
    """
    if start_date and end_date:
        try:
            def _to_date(v):
                if isinstance(v, date_cls):
                    return v
                y, m, d = (int(x) for x in str(v).split("-")[:3])
                return date_cls(y, m, d)
            days = (_to_date(end_date) - _to_date(start_date)).days + 1
            if 1 <= days <= 31:
                return days
        except Exception:
            pass
    m = re.search(r"(?<!第)([0-9]{1,2}|[一二三四五六七八九十]{1,3})\s*天", user_message or "")
    if m:
        d = _cn_to_int(m.group(1))
        if d and 1 <= d <= 31:
            return d
    return None


def budget_bucket(budget) -> Optional[int]:
    """把预算圆整到千元档，提高命中率。"""
    if not budget:
        return None
    try:
        b = int(budget)
        if b <= 0:
            return None
        return max(1000, round(b / 1000) * 1000)
    except Exception:
        return None


def _cache_key(destination: str, days, travel_style, budget) -> str:
    return f"{destination}|{days or 0}|{travel_style or ''}|{budget or 0}"


async def get_cached_plan(
    destination: str,
    user_message: str,
    start_date,
    end_date,
    travel_style,
    budget,
) -> Optional[Dict[str, Any]]:
    """查找相似缓存行程；无命中返回 None。"""
    if not destination:
        return None
    days = derive_days(user_message, start_date, end_date)
    bucket = budget_bucket(budget)
    dest = destination

    try:
        async with AsyncSessionLocal() as db:
            # 缓存较小：全量读，Python 端做"目的地双向包含"模糊匹配，
            # 兼容 LLM 解析目的地不一致（如 大理 vs 云南大理），提高命中率。
            result = await db.execute(select(PlanCache).order_by(PlanCache.created_at.desc()))
            rows = list(result.scalars())
    except Exception as e:
        logger.warning(f"查询行程缓存失败: {e}")
        return None

    best, best_score = None, -1.0
    for row in rows:
        # 硬条件①：目的地双向包含，或（抗 LLM 解析漂移）该缓存城市名出现在用户消息里
        rd = (row.destination or "")
        dest_ok = (dest in rd or rd in dest or (user_message and rd and rd in user_message))
        if not dest_ok:
            continue
        # 硬条件②：天数容差(±1)（按缓存行记录的 days 字段）
        if days and row.days and abs(days - row.days) > 1:
            continue
        # 硬条件③：天数容差也作用于"正文实际天数"（防历史缓存 days 字段与新正文不一致——
        # 早年"规划3天却生成5天"的结果被缓存：row.days=3 但正文是 5 天，仅靠字段仍命中错误天数；
        # 且历史行 itinerary 可能是 JSON 字符串、场景不一，故统一从正文标题解析，格式无关最可靠）。
        if days:
            from app.agent.nodes import _derive_days  # 惰性导入避免与 nodes 的循环依赖
            content_days = len(_derive_days(row.content or ""))
            if content_days and abs(days - content_days) > 1:
                continue
        # 软偏好：风格匹配 +2，预算匹配 +1；只为"择优"，而非排除
        score = 0.0
        if travel_style and row.travel_style and travel_style == row.travel_style:
            score += 2
        if budget and bucket and row.budget and abs(row.budget - bucket) <= 0.3 * max(bucket, row.budget):
            score += 1
        if score > best_score or (
            score == best_score
            and best is not None
            and (row.created_at or datetime.min) > (best.created_at or datetime.min)
        ):
            best, best_score = row, score
    if best is None:
        return None
    logger.info(f"⚡ 命中相似行程缓存: {dest} {days}天/{travel_style or '-'} (评分{best_score})")
    return {"content": best.content, "itinerary": best.itinerary}


async def save_plan(
    destination: str,
    user_message: str,
    start_date,
    end_date,
    travel_style,
    budget,
    content: str,
    itinerary: Optional[Dict[str, Any]],
) -> None:
    """写入行程缓存（按 cache_key 去重、保留最新）。"""
    if not destination or not content:
        return
    days = derive_days(user_message, start_date, end_date)
    bucket = budget_bucket(budget)
    key = _cache_key(destination, days, travel_style, bucket)
    now = datetime.utcnow()
    try:
        async with AsyncSessionLocal() as db:
            row = (
                await db.execute(select(PlanCache).where(PlanCache.cache_key == key))
            ).scalar_one_or_none()
            if row:
                row.content = content
                row.itinerary = itinerary
                row.destination = destination
                row.days = days or 0
                row.travel_style = travel_style or ""
                row.budget = bucket or 0
                row.created_at = now
            else:
                db.add(PlanCache(
                    cache_key=key,
                    destination=destination,
                    days=days or 0,
                    travel_style=travel_style or "",
                    budget=bucket or 0,
                    content=content,
                    itinerary=itinerary,
                    created_at=now,
                ))
            await db.commit()
    except Exception as e:
        logger.warning(f"行程缓存写入失败: {e}")