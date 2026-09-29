"""Agent 流式对话编排(SSE) —— 薄编排层。

复用 graph 的节点函数做"快速前置阶段"(解析/检索/天气)，
仅对最耗时的"生成行程"用 llm.astream 逐 token 产出，从而让用户看到"打字机"式实时输出。
从需求解析起交给 Schema 驱动的 `PlanSpec` + 通用动作调度器 `handle_action`（注册制），
"保存/天气/酒店/闲聊/修改"都走同一 dispatcher，而非散落的 if/else。

事件约定(每行一条, 空行分隔):
  data: {"type":"status","payload":{"step":"...","label":"..."}}
  data: {"type":"token","payload":{"text":"..."}}
  data: {"type":"done","payload":{...结构化结果...}}
  data: {"type":"error","payload":{"message":"..."}}
"""
import json
import logging
from typing import Any, Dict, Optional, AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.memory import get_conversation_history
from app.agent.nodes import parse_requirements
from app.agent.actions import handle_action
from app.services.planning_state import (
    load_planning_session,
    session_to_state,
    merge_plan_spec,
    SESSION_KEY,
)
from app.services.llm_metrics import set_metrics_ctx

logger = logging.getLogger(__name__)


def _fmt(type_: str, payload: dict) -> str:
    """将事件格式化为一条 SSE data 行"""
    return f"data: {json.dumps({'type': type_, 'payload': payload}, ensure_ascii=False)}\n\n"


def _build_initial_state(user_id: str, user_message: str, context: dict = None) -> dict:
    state = {
        "user_id": user_id,
        "user_message": user_message,
        "trip_id": None,
        "intent": None,
        "intent_confidence": 0.0,
        "destination": None,
        "start_date": None,
        "end_date": None,
        "days": None,
        "budget": None,
        "travelers": None,
        "travel_style": None,
        "plan_spec": None,
        "retrieved_spots": [],
        "retrieved_guides": [],
        "weather_info": None,
        "draft_itinerary": None,
        "optimized_itinerary": None,
        "flight_options": [],
        "hotel_options": [],
        "messages": [],
        "response": None,
        "suggested_actions": [],
        "error": None,
        "retry_count": 0,
    }
    if context:
        for key, value in context.items():
            if key in state:
                state[key] = value
    return state


async def _load_prior_state(state: dict, user_id: str, db: Optional[AsyncSession]) -> None:
    """加载对话历史 + 持久化规划状态，填入上一版行程(prior_*)/messages/基线 plan_spec。

    - 对话历史文本为兜底；
    - planning_sessions 为结构性真源（多轮修改的事实唯一真源）。
    """
    if db is None:
        return
    try:
        recent = await get_conversation_history(user_id=user_id, db=db, limit=8)
        state["messages"] = [
            {"role": m["role"], "content": m["content"]}
            for m in recent
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
    except Exception as e:
        logger.warning(f"加载对话历史失败，忽略（单轮继续）: {e}")

    try:
        sess = await load_planning_session(db, user_id, session_key=SESSION_KEY)
        if sess is not None:
            state.update(session_to_state(sess))  # 权威 prior_* + 基线 plan_spec
    except Exception as e:
        logger.warning(f"加载规划状态失败，忽略: {e}")


def _apply_plan_spec(state: dict) -> None:
    """把 PlanSpec 合并结果回填到 state 的原有字段（向下兼容既有节点/前端）。"""
    spec = state.get("plan_spec") or {}
    state["destination"] = spec.get("destination") or state.get("destination")
    state["days"] = spec.get("days") or state.get("days")
    state["start_date"] = spec.get("start_date") or state.get("start_date")
    state["end_date"] = spec.get("end_date") or state.get("end_date")
    state["budget"] = spec.get("budget") or state.get("budget")
    state["travelers"] = spec.get("travelers") or state.get("travelers") or 1
    state["travel_style"] = spec.get("travel_style") or state.get("travel_style")
    if spec.get("intent"):
        state["intent"] = spec["intent"]


async def stream_travel_agent(
    user_id: str,
    user_message: str,
    context: dict = None,
    db: AsyncSession = None,
) -> AsyncIterator[str]:
    """生成 SSE 事件流(status/token/done/error)。

    编排：构建状态 → 加载历史/规划状态 → Schema 解析 → 基线合并 → 通用 dispatcher。
    """
    try:
        # 指标归属：把 user_id 提前放进 contextvar，LLM 客户端包装器据此记账
        set_metrics_ctx(user_id=user_id)
        yield _fmt("status", {"step": "parsing", "label": "正在解析你的需求…"})
        state = _build_initial_state(user_id, user_message, context)

        # 加载对话历史 + 持久化规划状态（基线 plan_spec 和多轮 prior_*）
        await _load_prior_state(state, user_id, db)
        baseline_spec: Optional[Dict[str, Any]] = state.get("plan_spec")

        state = await parse_requirements(state)

        # Phase 2：modify_trip 时把新需求增量合并到持久化基线（其余字段/约束保持），
        # 再用 `changed` 让生成 prompt 只改被要求的方面。
        if baseline_spec:
            merged = merge_plan_spec(baseline_spec, state.get("plan_spec"))
            state["plan_spec"] = merged.dump()
            state["intent"] = merged.intent or state["intent"]

        _apply_plan_spec(state)

        # 解析出目的地后更新指标归属（行程生成/酒店等后续调用都算在本次会话下）
        if state.get("destination"):
            set_metrics_ctx(user_id=user_id, destination=state.get("destination"))

        # 通用动作调度：intent → 注册的 handler（保存/天气/酒店/闲聊/生成/修改同一链路）
        async for ev in handle_action(state, db):
            yield ev
    except Exception as e:
        logger.exception("流式 Agent 处理失败")
        yield _fmt("error", {"message": f"Agent 处理失败: {str(e)}"})