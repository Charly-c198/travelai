"""规划状态存取：把最近一份 `PlanSpec` + 行程对象持久化到 planning_sessions 表。

多轮修改的事实唯一真源（替代"每次从历史文本重新推导"）：
- 加载最近 plan → 用 `PlanSpec.changed` 应用增量 → 生成/修改 → 回写。
- 生成 prompt 注入完整 plan（含 constraints + changed），修改 = 改几个字段再注入，其余保持。

注意：user_id 列是 UUID 类型（即便底层 SQLite），收字符串须先归一化为 UUID 对象
（见 memory UUID 列坑），否则写入报 'str' object has no attribute 'hex'。
"""
import logging
import uuid
from datetime import datetime
from typing import Optional, Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.planning_session import PlanningSession
from app.agent.schemas import PlanSpec

logger = logging.getLogger(__name__)

# 该 app 无显式会话 id，固定用单条"主会话"记录用户的最近一份规划状态。
SESSION_KEY = "main"


def _to_uuid(user_id) -> Optional[uuid.UUID]:
    try:
        return uuid.UUID(str(user_id))
    except Exception:
        return None


def _to_date(v) -> Any:
    """字符串/date/None → 可入库的 date（字符串 ISO 转成 date 对象）。"""
    if v is None or v == "":
        return None
    from datetime import date as date_cls
    if isinstance(v, date_cls):
        return v
    try:
        return date_cls(*[int(x) for x in str(v).split("-")[:3]])
    except Exception:
        return None


async def load_planning_session(
    db: Optional[AsyncSession],
    user_id,
    session_key: str = SESSION_KEY,
) -> Optional[PlanningSession]:
    """加载用户最近一份规划状态；无 db 或未命中返回 None。"""
    if db is None:
        return None
    uid = _to_uuid(user_id)
    if uid is None:
        return None
    try:
        stmt = (
            select(PlanningSession)
            .where(
                PlanningSession.user_id == uid,
                PlanningSession.session_key == session_key,
            )
            .order_by(PlanningSession.updated_at.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()
    except Exception as e:
        logger.warning(f"加载规划状态失败: {e}")
        return None


async def save_planning_session(
    db: Optional[AsyncSession],
    user_id,
    *,
    plan_spec: Optional[Dict[str, Any]],
    itinerary: Optional[Dict[str, Any]],
    destination: Optional[str],
    start_date,
    end_date,
    session_key: str = SESSION_KEY,
) -> bool:
    """回写最新规划状态（upsert：有则更新，否则新建）。失败静默，不影响主流程。"""
    if db is None:
        return False
    uid = _to_uuid(user_id)
    if uid is None:
        return False
    now = datetime.utcnow()
    try:
        row = (
            await db.execute(
                select(PlanningSession).where(
                    PlanningSession.user_id == uid,
                    PlanningSession.session_key == session_key,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = PlanningSession(user_id=uid, session_key=session_key)
            db.add(row)
        row.plan_spec_json = plan_spec
        row.itinerary_json = itinerary
        row.destination = destination
        row.start_date = _to_date(start_date)
        row.end_date = _to_date(end_date)
        row.updated_at = now
        await db.commit()
        return True
    except Exception as e:
        logger.warning(f"回写规划状态失败: {e}")
        return False


def session_to_state(row: Optional[PlanningSession]) -> Dict[str, Any]:
    """把持久化的规划状态转成可注入 state 的 dict。

    - 上一版行程（prior_itinerary_content/prior_itinerary/prior_destination…）：保存/修改的"在底子上改"基座
    - plan_spec：作为多轮增量的上一个基线
    """
    if row is None:
        return {}
    out: Dict[str, Any] = {}
    it = row.itinerary_json or {}
    content = (it.get("content") or "").strip()
    if content:
        out["prior_itinerary_content"] = content
        out["prior_itinerary"] = it
    if row.destination:
        out["prior_destination"] = row.destination
    if row.start_date:
        out["prior_start_date"] = row.start_date.isoformat()
    if row.end_date:
        out["prior_end_date"] = row.end_date.isoformat()
    if row.plan_spec_json:
        out["plan_spec"] = row.plan_spec_json
    return out


def merge_plan_spec(base: Optional[Dict], new: Optional[Dict]) -> PlanSpec:
    """把本次解析出的新 PlanSpec 增量合并到上一个基线 Spec 上。

    - 非 modify_trip：用新的（全新规划）；
    - modify_trip：新字段设定则覆盖，未设定沿用基线；constraints 累积（保持完整性）；
      changed 只取本次（作为"这次改了什么"，不必回放历史）。
    """
    new = new or {}
    base = base or {}
    if new.get("intent") != "modify_trip":
        return PlanSpec.load(new)
    merged = PlanSpec.load(base)
    # 说话前先记住【基线目的地】：换城市 → 约束视为全新（避免跨城污染）。
    # 必须在字段覆盖循环之前取，因为循环把 destination 改成新值后对比会失真。
    orig_dest = (base or {}).get("destination") or merged.destination
    # 覆盖有明确新值的字段
    for name in PlanSpec.model_fields:
        v = new.get(name)
        if v is None:
            continue
        if name == "constraints":
            continue  # 单独处理（累积）
        if name == "changed":
            merged.changed = list(new.get("changed") or [])
            continue
        setattr(merged, name, v)
    # 宿制兜底天数：合并后仍无 days 则用日期区间推导（由调用方在此前完成）
    # constraints 累积（去重保序；目的地变了则视为全新约束，避免跨城污染）
    new_constraints = list(new.get("constraints") or [])
    if orig_dest and new.get("destination") and new["destination"] != orig_dest:
        merged.constraints = list(dict.fromkeys(new_constraints))
    else:
        merged.constraints = list(dict.fromkeys(list(merged.constraints) + new_constraints))
    merged.changed = list(new.get("changed") or merged.changed)
    return merged