"""LangGraph Agent 图构建"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.memory import get_conversation_history
from app.agent.plan_cache import get_cached_plan, save_plan
from app.services.llm_metrics import set_metrics_ctx
from app.agent.nodes import (
    parse_requirements,
    search_spots,
    fetch_weather,
    generate_itinerary,
    optimize_route,
    generate_response,
    should_retry,
    is_trip_planning_complete
)

logger = logging.getLogger(__name__)


async def check_cache(state: AgentState) -> AgentState:
    """解析需求后查相似行程缓存：命中则直接产出结果，跳过昂贵的搜索+生成。

    skip_cache 为 True（显式"一键生成"）时跳过缓存，强制按当前约束重新生成。
    """
    cached = None if state.get("skip_cache") else await get_cached_plan(
        state.get("destination"),
        state.get("user_message"),
        state.get("start_date"),
        state.get("end_date"),
        state.get("travel_style"),
        state.get("budget"),
    )
    if cached:
        state["from_cache"] = True
        state["knowledge_source"] = "cache"
        state["response"] = cached["content"]
        state["draft_itinerary"] = cached["itinerary"]
        state["suggested_actions"] = []
    else:
        state["from_cache"] = False
    return state


def route_after_cache(state: AgentState) -> str:
    """缓存命中则结束，否则进入搜索/生成流程。"""
    return "end" if state.get("from_cache") else "search_spots"


def create_travel_agent_graph() -> StateGraph:
    """
    创建旅行规划 Agent 图

    工作流:
    解析需求 → (缓存命中?结束 | 搜索景点 → 获取天气 → 生成行程 → 优化路线 → 生成回复)
    """

    # 创建图
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("parse_requirements", parse_requirements)
    graph.add_node("check_cache", check_cache)
    graph.add_node("search_spots", search_spots)
    graph.add_node("fetch_weather", fetch_weather)
    graph.add_node("generate_itinerary", generate_itinerary)
    graph.add_node("optimize_route", optimize_route)
    graph.add_node("generate_response", generate_response)

    # 设置入口
    graph.set_entry_point("parse_requirements")

    # 添加边（parse 后先查缓存，命中直接归结束）
    graph.add_edge("parse_requirements", "check_cache")
    graph.add_conditional_edges(
        "check_cache",
        route_after_cache,
        {"end": END, "search_spots": "search_spots"},
    )
    graph.add_edge("search_spots", "fetch_weather")
    graph.add_edge("fetch_weather", "generate_itinerary")
    graph.add_edge("generate_itinerary", "optimize_route")
    graph.add_edge("optimize_route", "generate_response")
    graph.add_edge("generate_response", END)

    # 编译图
    compiled_graph = graph.compile()

    logger.info("✅ TravelAI Agent 图构建完成")

    return compiled_graph


# 全局 Agent 实例
_travel_agent = None


def get_travel_agent():
    """获取 Agent 实例（单例）"""
    global _travel_agent

    if _travel_agent is None:
        _travel_agent = create_travel_agent_graph()

    return _travel_agent


async def run_travel_agent(
    user_id: str,
    user_message: str,
    context: dict = None,
    db: AsyncSession = None,
    skip_cache: bool = False,
) -> dict:
    """
    运行旅行规划 Agent

    Args:
        user_id: 用户 ID
        user_message: 用户消息
        context: 上下文信息（可选）
        db: 数据库会话（可选，用于加载对话历史支持多轮）
        skip_cache: 跳过相似行程缓存，强制按当前约束重新生成

    Returns:
        Agent 执行结果
    """
    logger.info(f"🚀 [Agent] 开始处理用户请求: {user_message[:50]}...")

    # 指标归属：整条图内所有 LLM 调用都记到该用户下
    set_metrics_ctx(user_id=user_id)

    # 初始化状态: AgentState = {
    initial_state = {
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
        "skip_cache": skip_cache
    }

    # 注入上下文
    if context:
        for key, value in context.items():
            if key in initial_state:
                initial_state[key] = value

    # 加载对话历史支持多轮（提供了 db 时）
    if db is not None:
        try:
            recent = await get_conversation_history(user_id=user_id, db=db, limit=8)
            initial_state["messages"] = [
                {"role": m["role"], "content": m["content"]}
                for m in recent
                if m.get("role") in ("user", "assistant") and m.get("content")
            ]
        except Exception as e:
            logger.warning(f"加载对话历史失败，忽略（单轮继续）: {e}")

    # 运行 Agent
    agent = get_travel_agent()
    result = await agent.ainvoke(initial_state)

    logger.info(f"✅ [Agent] 处理完成")

    return {
        "response": result.get("response"),
        "intent": result.get("intent"),
        "suggested_actions": result.get("suggested_actions", []),
        "weather_info": result.get("weather_info"),
        "draft_itinerary": result.get("draft_itinerary"),
        "optimized_itinerary": result.get("optimized_itinerary"),
        "knowledge_source": result.get("knowledge_source"),
    }
