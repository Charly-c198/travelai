"""Agent 状态定义"""
from typing import TypedDict, List, Optional, Dict, Any
from enum import Enum
from datetime import date


class IntentType(str, Enum):
    """旅行意图类型"""
    TRIP_PLAN = "trip_plan"        # 行程规划
    SPOT_QUERY = "spot_query"      # 景点查询
    MODIFY_TRIP = "modify_trip"    # 修改行程
    BOOKING_QUERY = "booking_query"# 预订查询
    WEATHER_QUERY = "weather_query"# 天气查询
    BUDGET_QUERY = "budget_query"  # 预算查询
    TIPS_QUERY = "tips_query"      # 旅行 tips
    CHITCHAT = "chitchat"          # 闲聊


class TripStatus(str, Enum):
    """行程状态"""
    PLANNING = "planning"     # 规划中
    CONFIRMED = "confirmed"  # 已确认
    IN_PROGRESS = "in_progress"# 旅途中
    COMPLETED = "completed"   # 已完成
    CANCELLED = "cancelled"   # 已取消


class TravelStyle(str, Enum):
    """旅行风格"""
    RELAXED = "relaxed"        # 休闲度假
    ADVENTUROUS = "adventurous"# 探险挑战
    CULTURAL = "cultural"       # 文化探索
    FAMILY = "family"           # 亲子游
    ROMANTIC = "romantic"       # 蜜月/情侣
    BUSINESS = "business"       # 商务旅行
    FOODIE = "foodie"           # 美食之旅
    PHOTOGRAPHY = "photography" # 摄影采风


class AgentState(TypedDict):
    """
    Agent 状态定义
    包含规划过程中所有需要传递的数据
    """
    # 用户输入
    user_id: str
    user_message: str
    # 前端会话绑定的行程 id（有则"保存到我的行程"走更新，无则新建）
    trip_id: Optional[str]

    # 意图识别
    intent: Optional[IntentType]
    intent_confidence: float

    # 旅行需求解析
    destination: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    days: Optional[int]
    budget: Optional[int]
    travelers: Optional[int]
    travel_style: Optional[TravelStyle]
    # Schema 驱动的结构化需求（PlanSpec 的 dict 形式）：含 constraints/changed，
    # 是 constraints 透传 + 增量修改 + planning_sessions 持久化的载体
    plan_spec: Optional[Dict[str, Any]]

    # 检索结果
    retrieved_spots: List[Dict[str, Any]]
    retrieved_guides: List[Dict[str, Any]]
    weather_info: Optional[Dict[str, Any]]

    # 行程规划
    draft_itinerary: Optional[Dict[str, Any]]
    optimized_itinerary: Optional[Dict[str, Any]]

    # 预订信息
    flight_options: List[Dict[str, Any]]
    hotel_options: List[Dict[str, Any]]

    # 对话历史
    messages: List[Dict[str, str]]

    # 输出
    response: Optional[str]
    suggested_actions: List[str]

    # 错误处理
    error: Optional[str]
    retry_count: int

    # 缓存与数据来源（check_cache 节点 / 生成节点写入，用于条件路由与结果标注）
    from_cache: bool
    knowledge_source: Optional[str]
    # 显式"一键生成"时跳过缓存（true 时 check_cache 不查缓存、强制重新生成）
    skip_cache: bool

