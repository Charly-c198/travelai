"""Schema 驱动的结构化需求解析 `PlanSpec`。

对话 Agent 的唯一结构化需求类型，取代原先硬编码 6 字段的 parse_requirements：

- 解析 prompt 由 schema 字段描述**自动生成**（加字段只需在 schema 加一行，二者恒同步）；
- `constraints` 是兜底泛化：把所有自由语义约束原样塞进来（"要民宿""别赶路""爱吃辣"…），
  生成 prompt 原样透传、模型自行遵守 → 新需求 = 不改代码；
- `changed` 记录本次改动了哪些字段（增量更新依据，而非整段重建）。
"""
from datetime import date
from typing import Optional, List

from pydantic import BaseModel, Field

# 每个 schema 字段的人类可读描述（generate 解析 prompt 用）。
_FIELD_DESC = {
    "intent": "用户意图，只能是以下之一（根据语境判断，一次一个）："
    "trip_plan(规划新行程) / modify_trip(修改已有行程，如改天数/预算/加一晚/换城市/取消某天) / "
    "save_trip(把行程保存到我的行程) / weather_query(查天气) / hotel_query(查询或预订酒店) / "
    "chitchat(闲聊，与行程无关)。",
    "destination": "目的地（城市/国家）。未提及为 null。",
    "start_date": "开始日期 (YYYY-MM-DD)。未提及为 null。",
    "end_date": "结束日期 (YYYY-MM-DD)。未提及为 null。可直接让模型推断（有了 天数和起点 就能算）。",
    "days": "行程天数（整数）。“三天”→3，“5天”→5。未提及为 null。",
    "budget": "预算（整数，人民币）。未提及为 null。",
    "travelers": "出行人数（整数）。未提及为 1。",
    "travel_style": "旅行风格，只能是以下之一：relaxed/adventurous/cultural/family/romantic/"
    "business/foodie/photography。未提及为 null。",
    "constraints": "用户的所有自由语义约束**原样**放入数组，一条一条（如 [“住宿要民宿”, “别赶路,轻松点”, “爱吃辣”, “离地铁近”]）。"
    "很口语也直接原文塞进来，不要改写、不要归纳丢失。没有则为空数组。",
    "changed": "本次消息相对上一版行程**改动了哪些字段名**。改成两天→[\"days\"]；加一晚→[\"days\"]；换成民宿→[\"constraints\"]；"
    "改成经济型→[\"budget\",\"constraints\"]。全新规划或没有明确改动→空数组。",
}

# 合法意图集合（agent/actions.py 的 ACTIONS 注册表键，二者需一致）
VALID_INTENTS = {
    "trip_plan",
    "modify_trip",
    "save_trip",
    "weather_query",
    "hotel_query",
    "chitchat",
}


class PlanSpec(BaseModel):
    """对话 Agent 的结构化需求 schema。"""

    intent: Optional[str] = None
    destination: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    days: Optional[int] = None
    budget: Optional[int] = None
    travelers: Optional[int] = None
    travel_style: Optional[str] = None
    constraints: List[str] = Field(default_factory=list)
    changed: List[str] = Field(default_factory=list)

    @classmethod
    def field_descriptions(cls) -> str:
        """由 schema 字段自动生成解析 prompt 的字段列表。"""
        lines = []
        for name in cls.model_fields:
            lines.append(f"- {name}: {_FIELD_DESC.get(name, '')}")
        return "\n".join(lines)

    @classmethod
    def parse_prompt(
        cls,
        user_message: str,
        history_block: str = "",
        note: str = "",
    ) -> str:
        """生成"需求解析" prompt：字段描述由 schema 自动派生，与 PlanSpec 恒同步。"""
        hist = (
            f"\n以下是同一对话的最近记录（用于理解上下文，最终以用户当前输入为准）：\n{history_block}\n"
            if history_block
            else ""
        )
        return f"""{hist}分析用户的旅行需求，提取为一个 JSON 对象。

请严格按照以下 schema 提取（只输出这个 JSON，不要任何解释、不要 markdown 代码块）：\n{cls.field_descriptions()}

{note}
用户当前输入: {user_message}"""

    @classmethod
    def load(cls, data: dict) -> "PlanSpec":
        """从 LLM 返回的 dict 稳健构造 PlanSpec（字段缺失/类型异常时降级，不抛错）。

        优先用模型构造（让 pydantic 完成类型强转：'3'→3、字符串→date 等）；
        个别字段坏值导致整体失败时才逐字段回退。
        """
        data = data or {}
        try:
            spec = cls(**data)
        except Exception:
            # 整体构造失败：逐字段构造并让 pydantic 单独校验类型；坏值字段丢弃
            spec = cls()
            for name in cls.model_fields:
                v = data.get(name)
                if v is None:
                    continue
                try:
                    setattr(spec, name, getattr(cls(**{name: v}), name))
                except Exception:
                    pass
        if spec.intent not in VALID_INTENTS:
            spec.intent = None
        return spec

    def dump(self) -> dict:
        """序列化为可持久化/注入 state 的纯 dict（date→ISO 字符串）。"""
        return self.model_dump(mode="json")