"""Agent节点定义"""
from typing import Dict,Any,List
from app.agent.state import AgentState, IntentType, TravelStyle
from app.agent.tools.spot_tools import SpotSearchTool
from app.agent.tools.weather_tools import WeatherTool
from app.agent.tools.route_tools import RouteOptimizer
from app.agent.plan_cache import save_plan, derive_days
from app.rag.chain import RAGChain
from app.llm.client import get_llm_client
import logging
import json
import re
from datetime import date as date_cls

logger = logging.getLogger(__name__)


def spot_city_ok(city, dest) -> bool:
    """景点城市与行程目的地一致（双向包含，容忍"广东广州"/"广州"写法）才算本城景点。
    设计约束：行程 spots 只允许本城景点，防止检索/通识混入他城地点（如广州行程里的天安门）。"""
    return bool(city and dest and (city in dest or dest in city))


def _format_history(messages: Any) -> str:
    """把对话历史压缩成纯文本块，供 prompt 参考（截断避免引入噪声/超长）"""
    if not messages:
        return ""
    lines = []
    for m in messages[-4:]:
        role = "用户" if m.get("role") == "user" else "AI"
        content = (m.get("content") or "")[:150].replace("\n", " ")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _derive_days(content: str) -> list:
    """把生成的 markdown 行程按天标题启发式拆成结构化 days，供时间线/增量修改用。

    识别 "第 2 天：xxx" / "第二天：xxx" / "Day 3 " 等标题行，其后内容归入当天。
    解析失败/无标题时返回空列表（前端回退纯 markdown）。
    """
    if not content:
        return []
    cjk = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}

    def _num(v: str) -> int:
        if v.isdigit():
            return int(v)
        return cjk.get(v, 999)

    days, current = [], None
    for raw in (ln.rstrip() for ln in content.splitlines()):
        s = raw.lstrip()
        # 只把"以 # 开头的、含天数标记的标题"当作一天；排除表格/引用/小结/预算/天气等子标题
        if s.startswith("#") and not any(k in s for k in ("小结", "总结", "预算", "天气", "明细")):
            c = re.sub(r"^#+\s*", "", s)
            c = re.sub(r"^[\W_]+", "", c, flags=re.UNICODE)  # 去掉行首 emoji/符号
            m = re.match(r"^(?:第|Day)\s*([0-9]{1,2}|[一二三四五六七八九十]+)", c, re.I)
            if m:
                if current:
                    days.append(current)
                rest = c[m.end():].lstrip("｜|·：: -—")
                current = {"day": _num(m.group(1)), "title": rest or c, "text": ""}
                continue
        if current is not None:
            current["text"] += "\n" + raw
    if current:
        days.append(current)
    return days


async def parse_requirements(state: AgentState) -> AgentState:
    """
    节点 1: 解析用户需求(Schema 驱动)
    用 PlanSpec 的字段描述自动生成 prompt，抽取到结构化 PlanSpec（含 constraints/changed），
    并回填到 state 的原有字段（destination/days/budget…），向下兼容既有节点。
    """
    logger.info("📝 [Node] 解析用户旅行需求")

    llm = get_llm_client()
    from app.agent.schemas import PlanSpec

    history = _format_history(state.get("messages"))
    today = date_cls.today()
    note = (
        f"今天是 {today.isoformat()}。日期一律使用真实日历，任何日期字段都不得早于今天、不得出现历史年份。"
        "如果当前输入是对历史对话既有行程的修改/延续（如“预算降到3000”“改成两天”“加一晚”“换民宿”），"
        "基于最近一次的行程补足未提及字段，并把 intent 置为 modify_trip。"
        "如果当前输入是“保存/存到我的行程/把行程放到我的行程”等保存意图，intent 置为 save_trip，其余字段为 null。"
        "如果只问天气/酒店/闲聊，intent 置为对应类型。"
    )
    prompt = PlanSpec.parse_prompt(
        state["user_message"], history_block=history, note=note
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content or ""
        try:
            import json
            result = json.loads(content)
        except Exception:
            result = {}
        spec = PlanSpec.load(result)

        from datetime import date as _d, timedelta as _td  # noqa: E402
        today = _d.today()

        # 天数兜底：LLM 没给出但正文/中文数字里有（如"规划三天"）
        if not spec.days:
            spec.days = derive_days(
                state.get("user_message") or "", spec.start_date, spec.end_date
            )
        # 只有天数没有具体日期 → 推导出发/结束日期，让生成 prompt 有真实区间
        if spec.days and not spec.end_date:
            start = spec.start_date
            if not isinstance(start, _d):
                start = today + _td(days=1)
            spec.start_date = start
            spec.end_date = start + _td(days=spec.days - 1)
        # 生成类请求完全没给日期：默认明天出发（否则模型会臆造历史年份，如 2024）。
        # end_date 仅在已知天数时推断；天数未知则不硬填，让模型在"不早于今天"前提下自行安排。
        gen_intent = spec.intent in (None, "trip_plan", "modify_trip")
        if gen_intent and spec.destination and not spec.start_date:
            spec.start_date = today + _td(days=1)

        # 回填 state（向下兼容），并把 PlanSpec 作为结构化载体写入 plan_spec
        state['destination'] = spec.destination
        state['start_date'] = spec.start_date.isoformat() if isinstance(spec.start_date, date_cls) else spec.start_date
        state['end_date'] = spec.end_date.isoformat() if isinstance(spec.end_date, date_cls) else spec.end_date
        state['budget'] = spec.budget
        state['travelers'] = spec.travelers if spec.travelers else 1
        state['travel_style'] = spec.travel_style if spec.travel_style else None
        state['days'] = spec.days
        state['intent'] = spec.intent
        state['plan_spec'] = spec.dump()

        logger.info(f"✅ 需求解析完成: {state.get('plan_spec')}")

    except Exception as e:
        logger.error(f"❌ 需求解析失败: {e}")
        state['error'] = str(e)

    return state


async def search_spots(state: AgentState) -> AgentState:
    """
    节点 2: 搜索景点
    使用 RAG 从知识库中检索相关景点信息
    """
    logger.info(f"🔍 [Node] 搜索景点: {state.get('destination')}")

    if not state.get('destination'):
        logger.warning("⚠️ 未指定目的地，跳过景点搜索")
        return state

    try:
        # RAG 检索景点
        rag = RAGChain()
        spots = await rag.search_spots(
            query=f"{state['destination']} 热门景点 必去",
            top_k=20,
            filters={
                'city': state['destination'],
                'category': state.get('travel_style', 'relaxed')
            }
        )

        state['retrieved_spots'] = spots
        logger.info(f"✅ 找到 {len(spots)} 个相关景点")

    except Exception as e:
        logger.error(f"❌ 景点搜索失败: {e}")
        state['error'] = str(e)

    return state


async def fetch_weather(state: AgentState) -> AgentState:
    """
    节点 3: 获取天气信息
    查询目的地未来天气预报
    """
    logger.info(f"🌤️ [Node] 获取天气信息: {state.get('destination')}")

    if not state.get('destination'):
        return state

    try:
        weather_tool = WeatherTool()
        weather = await weather_tool.get_weather(
            city=state['destination'],
            start_date=state.get('start_date'),
            end_date=state.get('end_date')
        )
        state['weather_info'] = weather
        logger.info(f"✅ 天气信息获取成功")

    except Exception as e:
        logger.warning(f"⚠️ 天气获取失败: {e}")
        state['weather_info'] = None

    return state


async def generate_itinerary(state: AgentState) -> AgentState:
    """
    节点 4: 生成行程
    基于景点和约束条件生成初步行程
    """
    logger.info("📅 [Node] 生成旅行行程")

    spots = state.get('retrieved_spots') or []
    if spots:
        state['knowledge_source'] = 'rag'
        spots_block = json.dumps(spots[:15], ensure_ascii=False, indent=2)
    else:
        # 本地库缺数据：依赖 LLM 通识兜底，绝不硬失败（诚实标注常识性推荐）
        state['knowledge_source'] = 'llm_knowledge'
        spots_block = (
            "（本地知识库暂无该目的地的检索结果。请依据对该目的地的通识合理规划："
            "自行安排当地知名景点、大致开放时间、交通与餐饮建议，并说明这些为常识性推荐，价格以购买时为准。）"
        )

    llm = get_llm_client()

    history = _format_history(state.get("messages"))
    history_block = (
        "\n以下是同一对话的最近记录（用于保持行程要求的一致性，勿与当前需求冲突）：\n"
        + history
        + "\n"
    ) if history else ""
    prior = (state.get("prior_itinerary_content") or "").strip()
    prior_block = (
        "\n以下是用户在本次对话中已有的行程（当前请求是对它的修改/延续，必须在其基础上调整，"
        "只改被要求的方面，输出修改后的完整行程）：\n"
        + prior[:2000]
        + "\n"
    ) if prior else ""
    days = state.get("days")
    days_line = f"天数: {days} 天" if days else "天数: 未指定（默认合理规划 3-7 天）"
    days_rule = (
        f"\n【硬性要求】本行程必须严格按 {days} 天规划：用 {days} 个“第N天”标题（第1天…第{days}天），"
        "每天都有具体安排，不多不少。"
        if days else ""
    )

    # Schema 泛化：constraints 原样透传，模型自行遵守（新需求=不改代码）；changed 标注本次改动方向
    spec = state.get("plan_spec") or {}
    spec_constraints = spec.get("constraints") or []
    constraints_block = (
        "\n以下为用户的所有偏好约束，务必逐条满足（时间/住宿/节奏等）：\n- "
        + "\n- ".join(spec_constraints)
        + "\n"
    ) if spec_constraints else ""
    changed_block = (
        f"\n【本次是在上一版基础上的修改请求】请只改这些方面：{('、'.join(str(c) for c in spec.get('changed') or []))}，"
        "其余保持上一版一致。"
        if state.get("intent") == "modify_trip" and spec.get("changed")
        else ""
    )

    prompt = f"""你是一个专业的旅行规划师。根据以下信息，为用户规划最佳行程：

{history_block}
{prior_block}
今天是 {date_cls.today().isoformat()}（真实日历；出发日期不得早于今天，更不得出现 2026 之前的年份）。
目的地: {state.get('destination')}
出发日期: {state.get('start_date')}
结束日期: {state.get('end_date')}
{days_line}
预算: {state.get('budget')} 元
人数: {state.get('travelers')} 人
旅行风格: {state.get('travel_style')}

热门景点（来自本地知识库，若为通识兜底则空）:
{spots_block}

天气预报:
{json.dumps(state.get('weather_info', {}), ensure_ascii=False, indent=2)}

请生成一份详细的多日行程规划，包含：
1. 每日主题
2. 具体景点安排（含时间建议）
3. 交通方式推荐
4. 餐饮建议
5. 注意事项
{days_rule}

行程应考虑:
- 景点之间的距离（同一区域集中安排）
- 合理的时间分配（避免过度紧凑）
- 开放时间限制
- 用户偏好 ({state.get('travel_style')}) 风格
{constraints_block}
{changed_block}

返回格式: Markdown 文档"""

    try:
        response = await llm.ainvoke(prompt)
        content = response.content or ""
        state['draft_itinerary'] = {
            "content": content,
            "days": _derive_days(content),  # 结构化对象(供时间线 UI / 增量修改)
            "spots_used": [s['id'] for s in state.get('retrieved_spots', [])[:10]],
            "spots": [  # 供前端地图标注（仅带真实坐标的）
                {
                    "name": s.get("name"),
                    "name_en": s.get("name_en"),  # 英文名供 Unsplash 精确搜图
                    "city": s.get("city"),
                    "latitude": s.get("latitude"),
                    "longitude": s.get("longitude"),
                }
                for s in (state.get('retrieved_spots') or [])[:10]
                if s.get('latitude') and s.get('longitude')
                and (s.get('name_en') or '').strip()  # 有英文名=可验证的真地点(碎片/攻略无 name_en 被过滤)
                and spot_city_ok(s.get('city'), state.get('destination'))
            ],
        }
        state['response'] = content
        # 写入相似行程缓存（供 /chat 等非流式路径复用，减少重复 LLM 生成）
        try:
            await save_plan(
                state.get("destination"), state.get("user_message"),
                state.get("start_date"), state.get("end_date"),
                state.get("travel_style"), state.get("budget"),
                content, state.get("draft_itinerary"),
            )
        except Exception as e:
            logger.warning(f"写入行程缓存失败: {e}")
        logger.info("✅ 行程生成成功")

    except Exception as e:
        logger.error(f"❌ 行程生成失败: {e}")
        state['error'] = str(e)

    return state


async def optimize_route(state: AgentState) -> AgentState:
    """
    节点 5: 优化路线
    对行程中的景点进行路径优化，减少路程时间
    """
    logger.info("🗺️ [Node] 优化旅行路线")

    if not state.get('draft_itinerary'):
        return state

    try:
        # 使用路线优化工具
        route_optimizer = RouteOptimizer()

        # 提取每日景点
        daily_spot_ids = []
        for spot in state.get('retrieved_spots', [])[:10]:
            daily_spot_ids.append({
                'id': spot['id'],
                'lat': spot.get('latitude'),
                'lng': spot.get('longitude'),
                'duration': spot.get('recommend_duration', 120)
            })

        # 优化路线顺序
        optimized = await route_optimizer.optimize(
            spots=daily_spot_ids,
            start_location=state.get('destination')
        )

        state['optimized_itinerary'] = optimized
        logger.info("✅ 路线优化完成")

    except Exception as e:
        logger.warning(f"⚠️ 路线优化失败: {e}")

    return state


async def generate_response(state: AgentState) -> AgentState:
    """
    节点 6: 生成最终回复
    将行程规划整理成友好的回复格式
    """
    logger.info("💬 [Node] 生成最终回复")

    if state.get('error'):
        state['response'] = f"抱歉，规划过程中遇到了一些问题: {state['error']}。请稍后重试"
        return state

    # 如果已有 draft 内容，直接使用
    if not state.get('response'):
        state['response'] = "已经为您准备好了旅行规划，请查看!"

    # 添加建议操作
    state['suggested_actions'] = [
        "修改行程安排",
        "调整预算范围",
        "查看机票推荐",
        "查看酒店推荐",
        "导出行程PDF",
        "分享给好友"
    ]

    return state


def should_retry(state: AgentState) -> bool:
    """判断是否需要重试"""
    return state.get('error') is not None and state.get('retry_count', 0) < 3


def is_trip_planning_complete(state: AgentState) -> bool:
    """判断行程规划是否完成"""
    return state.get('draft_itinerary') is not None and state.get('response') is not None
