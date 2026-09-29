"""通用动作调度器（把"针对改"的动作变成"注册制"）。

`state.intent → ACTIONS[intent](state, db)` 产出 SSE 事件流。
- 新增动作 = 注册一个 handler + 加一行 map，路由本身通用（不再每消息 if/else）。
- 所有 handler 收**结构化 state**（含 plan_spec/prior_itinerary），不再重新 text 解析。
- trip_plan 与 modify_trip 走同一链路（差别只在 prompt 注入上一版计划 + constraints 累积）。
"""
import json
import logging
import re
from datetime import date as date_cls, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes import (
    search_spots,
    fetch_weather,
    optimize_route,
    generate_response,
    spot_city_ok,
    _format_history,
    _derive_days,
)
from app.agent.plan_cache import get_cached_plan, save_plan, derive_days
from app.services.trip_service import save_trip_from_plan
from app.services.rollinggo import search_hotels as rollinggo_search_hotels
from app.services.profile_service import get_profile, record_trip
from app.services.quota_service import check_and_consume
from app.services.planning_state import save_planning_session, SESSION_KEY
from app.llm.client import get_llm_client

logger = logging.getLogger(__name__)


def _fmt(type_: str, payload: dict) -> str:
    """将事件格式化为一条 SSE data 行"""
    return f"data: {json.dumps({'type': type_, 'payload': payload}, ensure_ascii=False)}\n\n"


def _itinerary_prompt(state: dict) -> str:
    """生成关键词提示词：历史 + 待修改上一版 + 偏好约束(constraints) + 本次改动方向(changed)。"""
    history = _format_history(state.get("messages"))
    history_block = (
        "\n以下是同一对话的最近记录（用于保持行程要求的一致性，勿与当前需求冲突）：\n"
        + history
        + "\n"
    ) if history else ""

    prior = (state.get("prior_itinerary_content") or "").strip()
    # 仅当"同目的地继续/修改"时才带上上一版行程做基座；换了城市则视为全新规划（不注入旧行程）
    dest = state.get("destination")
    prior_dest = state.get("prior_destination")
    show_prior = bool(prior) and (
        not dest or not prior_dest or (dest in prior_dest or prior_dest in dest)
    )
    prior_block = (
        "\n以下是用户在本次对话中已有的行程（当前请求是对它的修改/延续，必须在其基础上调整，"
        "保持目的地、已确定的景点与顺序一致，只改被要求的方面，输出修改后的完整行程）：\n"
        + prior[:2000]
        + "\n"
    ) if show_prior else ""

    spots = (state.get("retrieved_spots") or [])
    if spots:
        spots_block = json.dumps(spots[:15], ensure_ascii=False, indent=2)
    else:
        spots_block = (
            "（本地知识库暂无该目的地的检索结果。请依据你对该目的地的通识来合理规划："
            "自行安排当地知名景点、大致开放时间、交通与餐饮建议，并在正文中说明这些为常识性推荐，"
            "具体门票与价格以购买时为准。）"
        )

    profile = state.get("profile") or {}
    profile_note = ""
    if profile.get("destinations"):
        profile_note = (
            "（画像提示：该用户过去常去 " + "、".join(profile["destinations"][-5:])
            + "，可参考其偏好安排，但以本次目的地为准）"
        )

    days = state.get("days")
    days_line = f"天数: {days} 天" if days else "天数: 未指定（默认合理规划 3-7 天）"
    days_rule = (
        f"\n【硬性要求】本行程必须严格按 {days} 天规划：用 {days} 个“第N天”标题（第1天…第{days}天），"
        "每天都有具体安排，不多不少。"
        if days else ""
    )

    # Schema 泛化重点：constraints 原样透传（新需求=不改代码），模型自行遵守
    spec = state.get("plan_spec") or {}
    spec_constraints = spec.get("constraints") or []
    constraints_block = (
        "\n以下为用户的所有偏好约束，务必逐条满足（时间/住宿/节奏/饮食等）：\n- "
        + "\n- ".join(spec_constraints)
        + "\n"
    ) if spec_constraints else ""
    changed_block = (
        f"\n【本次是在上一版基础上的修改请求】只改这些方面：{('、'.join(str(c) for c in spec.get('changed') or []))}，"
        "其余保持上一版一致。"
        if state.get("intent") == "modify_trip" and spec.get("changed")
        else ""
    )

    return f"""你是一个专业的旅行规划师。根据以下信息，为用户规划最佳行程：

历史对话（参考）：
{history_block or '(无)'}

{prior_block}
今天是 {date_cls.today().isoformat()}（真实日历；出发日期不得早于今天，更不得出现 2026 之前的年份）。
目的地: {state.get('destination')} {profile_note}
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


def _review_plan(content: str, state: dict) -> str:
    """对已生成行程做基础自查：天数是否匹配、是否有超预算风险。返回提示文案（空串=正常）。"""
    notes = []
    req_days = state.get("days") or derive_days(
        state.get("user_message") or "", state.get("start_date"), state.get("end_date")
    )
    if req_days:
        days_seen = set()
        for m in re.finditer(r"(?:第\s*)?(\d{1,2})\s*天|Day\s*(\d+)", content):
            days_seen.add(m.group(1) or m.group(2))
        if days_seen and len(days_seen) != req_days:
            notes.append(f"行程标注 {len(days_seen)} 天，与计划的 {req_days} 天不一致")
    budget = state.get("budget")
    if budget:
        m = re.search(r"(?:总[价费]|合计|总预算)[：:]?\s*[¥￥约]?(\d{3,7})", content)
        if m:
            total = int(m.group(1))
            if total > budget:
                notes.append(f"正文估算总花费约 {total} 元，超出预算 {budget} 元")
        else:
            notes.append(f"预算约束 {budget} 元（正文未给出总价，供参考）")
    return "；".join(notes) if notes else ""


async def _generate(state: dict, db: Optional[AsyncSession]):
    """trip_plan / modify_trip（含 intent=None 兜底）共用：缓存→额度→检索→天气→流式生成→校验→回写规划状态。

    这是"生成与修改走同一链路"的核心：区别只在 prompt 注入上一版计划 + constraints 累积。
    """
    # 画像个性化：消息未指定风格时用画像偏好补全（best-effort，不影响主流程）
    if db is not None:
        try:
            prof = await get_profile(db, state.get("user_id"))
            if not state.get("travel_style") and prof.get("travel_style"):
                state["travel_style"] = prof["travel_style"]
            state["profile"] = prof
        except Exception as e:
            logger.warning(f"读取画像失败: {e}")

    user_message = state.get("user_message") or ""

    # 连目的地都没有（modify/save 的目的地已由 merge 从基线带入，此处即已解析出的目标地）：
    # 不生成、不耗额度、不查缓存，直接引导补充信息
    if not state.get("destination"):
        yield _fmt("done", {
            "message": "请先告诉我要去哪个城市、玩几天，我来为你规划行程～（也可以一并说预算、风格、住哪等偏好）",
            "intent": state.get("intent"), "suggested_actions": [],
            "itinerary": None, "weather_info": None, "knowledge_source": None,
            "destination": None, "start_date": None, "end_date": None,
            "hotels": [], "review_note": "", "follow_up": "想去哪儿玩呀？",
        })
        return

    # 相似行程缓存：命中则直接复用（modify_trip/带约束时跳过，避免返回缺约束的旧版）
    skip_cache = state.get("intent") == "modify_trip" or bool((state.get("plan_spec") or {}).get("constraints"))
    cached = (await get_cached_plan(
        state.get("destination"),
        user_message,
        state.get("start_date"),
        state.get("end_date"),
        state.get("travel_style"),
        state.get("budget"),
    )) if not skip_cache else None
    if cached:
        state["knowledge_source"] = "cache"
        yield _fmt("status", {"step": "cache_hit", "label": "找到了相近的已生成行程，正在为你返回…"})
        yield _fmt("done", {
            "message": cached["content"],
            "intent": state.get("intent"),
            "suggested_actions": [],
            "itinerary": cached["itinerary"],
            "weather_info": None,
            "knowledge_source": "cache",
            "destination": state.get("destination"),
            "start_date": str(state.get("start_date")) if state.get("start_date") else None,
            "end_date": str(state.get("end_date")) if state.get("end_date") else None,
            "hotels": [], "review_note": "", "follow_up":
                "这是复用的相近行程，要不要帮你调整天数/预算，或看看周边酒店？",
        })
        return

    # 额度控制：仅全新生成本计数；缓存命中/免费档超出则提示升级
    if db is not None:
        try:
            ok, _usage = await check_and_consume(db, state.get("user_id"))
            if not ok:
                yield _fmt("done", {
                    "message": "⚠️ 今日免费生成次数已用完。升级 Pro 可无限次生成。",
                    "intent": None, "suggested_actions": [],
                    "itinerary": None, "weather_info": None,
                    "knowledge_source": "quota",
                    "destination": state.get("destination"),
                    "hotels": [], "review_note": "", "follow_up": "",
                })
                return
        except Exception as e:
            logger.warning(f"额度检查失败(放行): {e}")

    if not state.get("destination"):
        yield _fmt("done", {
            "message": "请先告诉我要去哪个城市、玩几天，我来为你规划行程～（也可以一并说预算、风格、住哪等偏好）",
            "intent": state.get("intent"), "suggested_actions": [],
            "itinerary": None, "weather_info": None, "knowledge_source": None,
            "destination": None, "start_date": None, "end_date": None,
            "hotels": [], "review_note": "", "follow_up": "",
        })
        return

    yield _fmt("status", {"step": "searching", "label": "正在检索当地景点…"})
    state = await search_spots(state)

    # 本地知识库无该目的地时的兜底策略：绝不硬失败，依赖 LLM 通识规划并标注数据来源。
    if not state.get("retrieved_spots"):
        state["knowledge_source"] = "llm_knowledge"
        yield _fmt("status", {"step": "planning", "label": "本地暂无该目的地资料，正在基于通用知识为你规划…"})
    else:
        state["knowledge_source"] = "rag"
        yield _fmt("status", {"step": "weather", "label": "正在查询当地天气…"})
        state = await fetch_weather(state)
        yield _fmt("status", {"step": "planning", "label": "正在为你规划行程…"})

    # —— 核心：流式生成行程正文 ——
    llm = get_llm_client()
    req_days = state.get("days") or derive_days(
        user_message, state.get("start_date"), state.get("end_date")
    )
    content = ""
    async for chunk in llm.astream(_itinerary_prompt(state)):
        piece = getattr(chunk, "content", None) or ""
        if piece:
            content += piece
            yield _fmt("token", {"text": piece})

    if not content.strip():
        content = "规划过程中遇到了一些问题，请稍后重试。"

    # 天数校验：首次生成的天数与要求不符 → 前端清屏，按纠错指令重生成一次
    gen_days = len(_derive_days(content))
    if req_days and gen_days and gen_days != req_days:
        yield _fmt("status", {
            "step": "regenerate",
            "label": f"检测到行程是 {gen_days} 天，与你要求的 {req_days} 天不符，正在按 {req_days} 天重新生成…",
        })
        correction = (
            f"\n\n【重要】你上一次生成的行程是 {gen_days} 天，与用户要求的 {req_days} 天不符。"
            f"请严格按 {req_days} 天重新生成：恰好 {req_days} 个“第N天”标题（第1天…第{req_days}天），"
            "每天都有具体安排，不多不少，也不要沿用旧版的天数结构。"
        )
        content = ""
        async for chunk in llm.astream(_itinerary_prompt(state) + correction):
            piece = getattr(chunk, "content", None) or ""
            if piece:
                content += piece
                yield _fmt("token", {"text": piece})
        if not content.strip():
            content = "规划过程中遇到了一些问题，请稍后重试。"

    state["draft_itinerary"] = {
        "content": content,
        "days": _derive_days(content),  # 结构化对象(供时间线 UI / 增量修改)
        "spots_used": [s["id"] for s in state.get("retrieved_spots", [])[:10]],
        "spots": [  # 供前端地图标注（仅带真实坐标的）
            {
                "name": s.get("name"),
                "name_en": s.get("name_en"),  # 英文名供 Unsplash 精确搜图
                "city": s.get("city"),
                "latitude": s.get("latitude"),
                "longitude": s.get("longitude"),
            }
            for s in (state.get("retrieved_spots") or [])[:10]
            if s.get("latitude") and s.get("longitude")
            and (s.get("name_en") or "").strip()  # 有英文名=可验证的真地点(碎片/攻略无 name_en 被过滤)
            and spot_city_ok(s.get("city"), state.get("destination"))
        ],
    }
    state["response"] = content
    state["itinerary"] = state.get("draft_itinerary")

    # 附带目的地周边真实可订酒店（best-effort，失败不影响主流程）
    state["hotels"] = []
    dest = state.get("destination")
    if dest:
        try:
            hr = await rollinggo_search_hotels(dest, size=4)
            state["hotels"] = [
                {
                    "name": h.get("name"),
                    "starRating": h.get("starRating"),
                    "price": (h.get("price") or {}).get("message"),
                    "bookingUrl": h.get("bookingUrl"),
                }
                for h in (hr.get("hotels") or [])[:4]
            ]
        except Exception as e:
            logger.warning(f"附加真实酒店失败: {e}")

    state = await optimize_route(state)
    state = await generate_response(state)

    # 新生成的高质量行程写入缓存，供相似请求复用（较少 LLM 调用）
    try:
        await save_plan(
            state.get("destination"),
            user_message,
            state.get("start_date"),
            state.get("end_date"),
            state.get("travel_style"),
            state.get("budget"),
            content,
            state.get("draft_itinerary"),
        )
    except Exception as e:
        logger.warning(f"写入行程缓存失败: {e}")

    # Phase 2：把规划状态回写 planning_sessions（多轮修改的持久化真源）
    if db is not None:
        try:
            await save_planning_session(
                db, state.get("user_id"),
                plan_spec=state.get("plan_spec"),
                itinerary=state.get("draft_itinerary"),
                destination=state.get("destination"),
                start_date=state.get("start_date"),
                end_date=state.get("end_date"),
                session_key=SESSION_KEY,
            )
        except Exception as e:
            logger.warning(f"回写规划状态失败: {e}")

    # 记录到用户画像（个性化学习：风格/目的地）
    if db is not None:
        try:
            await record_trip(db, state.get("user_id"), state.get("travel_style"), state.get("destination"))
        except Exception as e:
            logger.warning(f"记录画像失败: {e}")

    review_note = _review_plan(content, state)
    follow_up = (
        "要不要顺便看看周边可订酒店，或帮你调整行程？"
        if state.get("hotels")
        else "要不要帮你查一下该地的可订酒店？"
    )
    yield _fmt("done", {
        "message": content,
        "intent": state.get("intent"),
        "suggested_actions": state.get("suggested_actions", []),
        "itinerary": state.get("draft_itinerary"),
        "weather_info": state.get("weather_info"),
        "knowledge_source": state.get("knowledge_source"),
        "destination": state.get("destination"),
        "start_date": str(state.get("start_date")) if state.get("start_date") else None,
        "end_date": str(state.get("end_date")) if state.get("end_date") else None,
        "travel_style": state.get("travel_style"),
        "hotels": state.get("hotels") or [],
        "review_note": review_note,
        "follow_up": follow_up,
    })


async def _save_trip(state: dict, db: Optional[AsyncSession]):
    """save_trip：把最近一份规划状态/行程直接存进「我的行程」。不生成、不耗额度。"""
    it = (state.get("prior_itinerary") or state.get("itinerary") or {})
    content = (it.get("content") or "").strip()
    if not content:
        yield _fmt("done", {
            "message": "你还没有可保存的行程。先告诉我目的地和天数，我为你规划一个吧。",
            "intent": "save_trip", "suggested_actions": [],
            "itinerary": None, "weather_info": None, "knowledge_source": None,
            "destination": state.get("destination") or state.get("prior_destination"),
            "start_date": None, "end_date": None,
            "hotels": [], "review_note": "", "follow_up": "",
        })
        return
    destination = state.get("destination") or state.get("prior_destination") or ""
    if not destination:
        yield _fmt("done", {
            "message": "要保存的是哪里的行程？请先告诉我是去哪个城市，或先让我为你规划一份。",
            "intent": "save_trip", "suggested_actions": [],
            "itinerary": None, "weather_info": None, "knowledge_source": None,
            "destination": None, "start_date": None, "end_date": None,
            "hotels": [], "review_note": "", "follow_up": "",
        })
        return

    days = state.get("days") or len(it.get("days") or []) or 3
    start = state.get("start_date") or state.get("prior_start_date")
    end = state.get("end_date") or state.get("prior_end_date")
    if not start:
        start = (date_cls.today() + timedelta(days=1)).isoformat()
    if not end:
        try:
            s = date_cls(*[int(x) for x in str(start).split("-")[:3]])
            end = (s + timedelta(days=days - 1)).isoformat()
        except Exception:
            end = start

    plan = {"content": content, "days": it.get("days"),
            "spots_used": it.get("spots_used"), "spots": it.get("spots")}
    try:
        if db is None:
            raise RuntimeError("缺少数据库会话")
        trip_id = await save_trip_from_plan(
            db, state.get("user_id"), destination, start, end, plan,
            title=f"{destination}之旅", trip_id=state.get("trip_id"),
        )
        if not trip_id:
            raise RuntimeError("保存失败")
        yield _fmt("done", {
            "message": f"✅ 已把「{destination}」行程（{days} 天）保存到你的行程，可在左侧「我的行程」查看。",
            "intent": "save_trip", "suggested_actions": [],
            "itinerary": None, "weather_info": None, "knowledge_source": None,
            "destination": destination,
            "start_date": str(start) if start else None,
            "end_date": str(end) if end else None,
            "saved_trip_id": str(trip_id),
            "hotels": [], "review_note": "", "follow_up": "要不要继续调整行程，或看看周边酒店？",
        })
    except Exception as e:
        logger.exception("保存行程失败")
        yield _fmt("done", {
            "message": f"保存行程失败了（{e}）。你可以稍后再试，或改用卡片上的「保存为行程」按钮。",
            "intent": "save_trip", "suggested_actions": [],
            "itinerary": None, "weather_info": None, "knowledge_source": None,
            "destination": destination,
            "start_date": None, "end_date": None,
            "hotels": [], "review_note": "", "follow_up": "",
        })


def _plain_done(message: str, *, intent: str, destination=None, weather_info=None,
                hotels=None, follow_up: str = "") -> str:
    return _fmt("done", {
        "message": message, "intent": intent, "suggested_actions": [],
        "itinerary": None, "weather_info": weather_info, "knowledge_source": None,
        "destination": destination, "start_date": None, "end_date": None,
        "hotels": hotels or [], "review_note": "", "follow_up": follow_up,
    })


async def _weather(state: dict, db: Optional[AsyncSession]):
    """weather_query：查目的地天气（不生成行程、不耗额度）。"""
    dest = state.get("destination") or state.get("prior_destination")
    if not dest:
        yield _plain_done("告诉我哪个城市，我帮你查天气～", intent="weather_query")
        return
    try:
        state = await fetch_weather(state)
    except Exception as e:
        logger.warning(f"天气查询失败: {e}")
        yield _plain_done(f"天气查询暂时失败了（{e}），稍后再试试。", intent="weather_query",
                          destination=dest)
        return
    w = state.get("weather_info") or {}
    yield _fmt("done", {
        "message": f"{dest}未来几天的天气如下（若日期未定，按近期天气参考）：\n"
                   f"{json.dumps(w, ensure_ascii=False, indent=2)}（数据仅供参考，出行前请以实时预报为准）",
        "intent": "weather_query", "suggested_actions": [],
        "itinerary": None, "weather_info": w, "knowledge_source": None,
        "destination": dest, "start_date": None, "end_date": None,
        "hotels": [], "review_note": "", "follow_up": "要不要顺便为你规划一份{0}的行程？".format(dest),
    })


async def _hotel(state: dict, db: Optional[AsyncSession]):
    """hotel_query：查目的地周边可订酒店（不生成行程、不耗额度）。"""
    dest = state.get("destination") or state.get("prior_destination")
    if not dest:
        yield _plain_done("告诉我哪个城市，我帮你找附近可订的酒店～", intent="hotel_query")
        return
    hotels = []
    try:
        hr = await rollinggo_search_hotels(dest, size=5)
        hotels = [{
            "name": h.get("name"),
            "starRating": h.get("starRating"),
            "price": (h.get("price") or {}).get("message"),
            "bookingUrl": h.get("bookingUrl"),
        } for h in (hr.get("hotels") or [])[:5]]
    except Exception as e:
        logger.warning(f"酒店查询失败: {e}")
    if not hotels:
        yield _plain_done(f"{dest}暂未查到可订酒店，换个城市试试？", intent="hotel_query",
                          destination=dest, follow_up="要不要帮你重新规划行程？")
        return
    lines = [f"- {h['name']}（{h['starRating']}星）{' /晚 ' + h['price'] if h['price'] else ''}" for h in hotels]
    yield _plain_done(
        f"{dest}附近可订酒店：\n" + "\n".join(lines) + "\n\n每个酒店都有预订链接，直接说“帮我订”或点卡片即可。",
        intent="hotel_query", destination=dest, hotels=hotels,
        follow_up="要选一个帮你订，或继续看看别的？",
    )


async def _chitchat(state: dict, db: Optional[AsyncSession]):
    """chitchat：闲聊引导回正题（不生成、不耗额度）。"""
    yield _plain_done(
        "我在呢～我是你的旅行规划助手，可以帮你安排行程、查天气、找酒店，"
        "或者把规划好的行程保存到「我的行程」。试试告诉我“去西安玩3天”，我就开始啦！",
        intent="chitchat", follow_up="想去哪儿玩呀？告诉我城市和天数~",
    )


# —— 注册表：路由本身通用，新增动作 = 在此加一行 + 一个 handler ——
ACTIONS = {
    "trip_plan": _generate,
    "modify_trip": _generate,
    "save_trip": _save_trip,
    "weather_query": _weather,
    "hotel_query": _hotel,
    "chitchat": _chitchat,
}


async def handle_action(state: dict, db: Optional[AsyncSession]):
    """通用动作调度：state.intent → 注册的 handler → SSE 事件流。未注册/无意图默认走生成。"""
    handler = ACTIONS.get(state.get("intent"), _generate)
    async for ev in handler(state, db):
        yield ev