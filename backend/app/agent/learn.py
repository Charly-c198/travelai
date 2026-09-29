"""LLM 自学习：把"通识兜底"生成的行程回灌知识库。

目的：
- 覆盖更多城市 → 后续同城市直接命中 RAG → 减少 LLM 调用、降低延迟与成本。
- 学习数据打 `source='learned'` 标记，与人工 seed 区分、可追溯。

本模块所有函数都是 best-effort：任何失败都不影响主流程。
"""
import logging
import re
import uuid
from typing import Any, Dict, List

from app.rag.chain import RAGChain
from app.services.amap_service import geocode_batch

logger = logging.getLogger(__name__)

# 明显不是"独立景点"的线索词，抽取时过滤，避免把交通/餐饮/注意事项当景点入库
_NON_SPOT = re.compile(
    r"(交通|酒店|住宿|入住|餐饮|美食|小吃|门票|注意|温馨提示|费用|预算|花费|前往|乘坐|"
    r"打车|地铁|公交|步行|返回|早餐|午餐|晚餐|建议|开放|地址|评分|人均|位置|距离|大概|大约|推荐)"
)


def _norm(name: str) -> str:
    return re.sub(r"[\s，。、（）()\-—|｜:：·]+", "", name or "")


def extract_spots(itinerary: Dict[str, Any], destination: str) -> List[Dict[str, Any]]:
    """从行程 markdown 尽力抽取景点候选（宁缺毋滥）。

    只取列表项（- / 1. / **xx**）开头的短名称，过滤明显非景点词。
    """
    if not itinerary:
        return []
    content = itinerary.get("content") or ""
    days = itinerary.get("days") or []
    text = "\n".join(d.get("text", "") for d in days) if days else content

    # 行首动作/时间词，剥掉后留给景点名
    _LEAD = re.compile(r"^(?:上午|下午|晚上|中午|午饭后|傍晚|清晨|入园|出发|\d{1,2}[:：]\d{1,2}\s*|去|到|在|前往|来到|逛|游|观|打卡|必去|必看)")
    # 行尾语气/行为词，剥掉
    _TAIL = re.compile(r"(逛逛|看看|游玩|游览|打卡|打卡地|之地|必看|必去|到此一游|散步|走走)$")

    names, seen = [], set()
    for ln in text.splitlines():
        s = ln.strip()
        if not s:
            continue
        m = re.match(r"^[-*•]\s+(.*)$", s) or re.match(r"^\d+[\.、]\s*(.*)$", s)
        if not m:
            continue
        cand = m.group(1).replace("**", "").strip()
        cand = _LEAD.sub("", cand).strip()          # 去掉行首时间/动作
        cand = re.split(r"[，。、；;（）()\-—|｜]", cand)[0].strip()  # 以标点取第一段
        cand = _TAIL.sub("", cand).strip()          # 去掉行尾行为词
        if len(cand) < 2 or len(cand) > 15:
            continue
        if _NON_SPOT.search(cand):
            continue
        key = _norm(cand)
        if not key or key in seen or key in ("today", "day", "place", "景点"):
            continue
        seen.add(key)
        names.append(cand)
        if len(names) >= 12:
            break

    return [
        {
            "id": f"lrn-{uuid.uuid4().hex[:8]}",
            "name": name,
            "name_en": "",
            "city": destination,
            "country": "中国",
            "category": "relaxed",  # 泛类兜底；检索另有"同城不过滤类别"兜底，跨风格也能命中
            "address": "",
            "latitude": None,
            "longitude": None,
            "rating": 0.0,
            "ticket_info": {},
            "recommend_duration": 120,
            "tags": ["AI整理"],  # Chroma 元数据 list 不能为空
            "description": f"由 AI 根据行程自动整理（目的地 {destination}；常识性推荐，坐标与价格以实际为准）",
        }
        for name in names
    ]


async def learn_from_itinerary(itinerary: Dict[str, Any], destination: str) -> int:
    """把行程抽取的景点回灌知识库（先对该城市已有数据去重）。

    返回新增数量；任何异常都被吞掉，绝不干扰主流程。
    """
    if not itinerary or not destination:
        return 0
    try:
        candidates = extract_spots(itinerary, destination)
        if not candidates:
            return 0
        rag = RAGChain()
        try:
            existing = await rag.search_spots(
                query=destination, top_k=50, filters={"city": destination}
            )
            existing_keys = {_norm(s.get("name") or "") for s in existing}
        except Exception:
            existing_keys = set()
        new_spots = [s for s in candidates if _norm(s["name"]) not in existing_keys]
        if not new_spots:
            return 0
        # 给学习景点补真实经纬度（高德地理编码），供地图标注；失败不影响入库
        try:
            new_spots = await geocode_batch(new_spots)
        except Exception as e:
            logger.warning(f"学习景点地理编码失败（忽略）: {e}")
        n = await rag.add_spots(new_spots, source="learned")
        logger.info(f"🧠 自学习入库 {n} 个景点（城市: {destination}）")
        return n
    except Exception as e:
        logger.warning(f"自学习回灌失败（不影响主流程）: {e}")
        return 0