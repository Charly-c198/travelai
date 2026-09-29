"""高德 Web 服务封装：地理编码 / 逆地理编码（用 Web服务 key，服务端调用）。"""
import re
from typing import List, Optional, Dict, Any, Iterator
import httpx

from app.config import get_settings

settings = get_settings()

_GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
_REVERSE_URL = "https://restapi.amap.com/v3/geocode/regeo"

# 非景点类关键词（命中则跳过该候选；注意不要把"前往"放进这里——"前往鼓浪屿"的景点是鼓浪屿）
_NON_SPOT = re.compile(
    r"(入住|住宿|酒店|抵达|返程|早餐|午餐|晚餐|美食|小吃|餐饮|门票|船票|索道票|"
    r"交通|地铁|公交|打车|乘坐|漫步|闲逛|转场|集合|出发|返回|"
    r"费用|预算|花费|温馨提示|注意事项|注意|建议|开放时间|地址|评分|人均|位置|距离|"
    r"大约|大概|推荐|预约|下单|支付|攻略|贴士|路线图|主题|亮点|安排|景点|行程)"
)
# 地点/景点后缀白名单：兜底路径只接受以这些词结尾的候选，过滤"自由探索""夏季闷热多雨"等噪音
_SPOT_SUFFIX = re.compile(
    r"(寺|塔|园|街|桥|山|湖|岛|宫|楼|广场|古镇|碑|岩|台|洞|墙|码头|沙滩|公园|遗址|"
    r"湾|港|峡|峰|陵|祠|阁|亭|馆|庙|城|坊|村|廊|坝|滩|苑|栈道|景区|老街|镇|路|门|"
    r"石窟|长城|瀑布|温泉|峡谷|半岛|乐园|动物园|植物园|博物馆|展览馆|纪念堂)$"
)
# 开头动词（"前往 X"→取 X）
_LEAD_VERB = re.compile(r"^(前往|参观|游览|抵达|入住|打卡|漫步|逛|游玩|探访|体验|登|坐|乘|乘坐|包车|乘车|驱车|骑行|自驾|赏|看|去)\s*")
# emoji（含各种符号）
_EMOJI = re.compile(
    r"[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF️⬀-⯿☀-➿←-⇿⏩-⏺]"
)
# 行首时间区间，如 **09:30–11:00** / 09:00-09:30
_TIME_PREFIX = re.compile(r"^\*{0,2}\d{1,2}[:：]\d{2}\s*[–\-~—至]\s*\d{1,2}[:：]\d{2}\*{0,2}\s*")


def _norm(name: str) -> str:
    return re.sub(r"[\s，。、（）()\-—|｜:：·]+", "", name or "")


def _candidate_names(source: str) -> Iterator[str]:
    """从一段候选文本中产出可能的景点名（先去【】内，再去噪后的主体）。"""
    s = source or ""
    # 1) 【名称】是强信号（重庆格式：【解放碑】【洪崖洞】…；也挡掉【早餐】【景点】这类标签）
    for m in re.finditer(r"【([^】]{2,16})】", s):
        name = re.split(r"\s*[&＆]\s*", m.group(1))[0].strip()  # 去掉 "& 江畔漫步" 后缀
        if 2 <= len(name) <= 16 and not _NON_SPOT.search(name):
            yield name
    # 2) 主体路径：去列表前缀/去 markdown/emoji/时间/开头动词/【标签】后取首段
    body = s.replace("**", "").strip()
    body = re.sub(r"^[-*•◦▪‣\s　]+", "", body)
    body = _EMOJI.sub("", body).strip()
    body = _TIME_PREFIX.sub("", body).strip()
    body = _LEAD_VERB.sub("", body).strip()
    body = re.sub(r"【[^】]*】", "", body).strip()
    body = re.split(r"<br>|\n", body)[0].strip()
    body = re.split(r"[，。、；;（）()]|：|:", body)[0].strip()
    body = re.split(r"\s*[&＆]\s*", body)[0].strip()
    body = re.sub(r"[\[\]【】\"'“”]", "", body).strip()
    if body and 2 <= len(body) <= 20 and _SPOT_SUFFIX.search(body) and not _NON_SPOT.search(body):
        yield body


def _extract_names(text: str) -> List[str]:
    """从行程 markdown 抽取景点候选名（兼容 AI 生成的表格/列表/【】格式）。"""
    if not text:
        return []
    seen, names = set(), []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith((">", "#", "```", "|--", "---", "==")):
            continue
        # 表格行：| 时间 | 活动安排 | 详情 | → 主信号在第 2 列；也可能整个行都相关
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            sources = ([cells[1]] if len(cells) >= 2 else []) + [line]
        else:
            sources = [line]
        for source in sources:
            for cand in _candidate_names(source):
                k = _norm(cand)
                if not k or k in seen or not (2 <= len(cand) <= 20):
                    continue
                seen.add(k)
                names.append(cand)
                if len(names) >= 10:
                    return names
    return names


async def enrich_itinerary(plan: Dict[str, Any], default_city: str,
                           name_en_lookup=None) -> List[Dict[str, Any]]:
    """从行程计划（content / days）抽取景点并补真实坐标，返回 [{name, name_en, city, lat, lng}]。

    name_en_lookup：可选 `async (name) -> str|None`，用于给已知景点回填英文名
    （有英文名=可验证的真地点，图鉴/Unsplash 才能按景点精确配图）。
    """
    if not plan:
        return []
    days = plan.get("days") or []
    text = "\n".join(d.get("text", "") for d in days) if days else (plan.get("content") or "")
    names = _extract_names(text)
    out, cache = [], {}
    for n in names:
        key = (n, default_city or "")
        if key in cache:
            coord = cache[key]
        else:
            try:
                coord = await geocode(n, default_city or None)
            except Exception:
                coord = None
            cache[key] = coord
        if coord:
            name_en = None
            if name_en_lookup is not None:
                try:
                    name_en = await name_en_lookup(n)
                except Exception:
                    name_en = None
            out.append({"name": n, "name_en": name_en, "city": default_city,
                        "latitude": coord["latitude"], "longitude": coord["longitude"]})
    return out


async def geocode(name: str, city: Optional[str] = None) -> Optional[Dict[str, float]]:
    """地理编码：地点名 → {latitude, longitude}。失败返回 None。"""
    if not settings.AMAP_API_KEY:
        return None
    params = {"address": name, "key": settings.AMAP_API_KEY, "citylimit": "true"}
    if city:
        params["city"] = city
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(_GEOCODE_URL, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
        if data.get("status") == "1" and data.get("geocodes"):
            loc = data["geocodes"][0].get("location")  # "lng,lat"
            if loc and "," in loc:
                lng, lat = loc.split(",")
                return {"latitude": float(lat), "longitude": float(lng)}
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).warning(f"高德地理编码失败({name}): {e}")
    return None


async def geocode_batch(spots: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """批量给景点补坐标（缺失时才补，跳过显式 0 的）。"""
    out = []
    for s in spots:
        item = dict(s)
        lat = item.get("latitude")
        lng = item.get("longitude")
        if not (lat and lng):
            got = await geocode(item.get("name") or "", item.get("city"))
            if got:
                item["latitude"] = got["latitude"]
                item["longitude"] = got["longitude"]
        out.append(item)
    return out


_POI_URL = "https://restapi.amap.com/v3/place/text"


async def poi_photo(name: str, city: Optional[str] = None) -> Optional[Dict[str, str]]:
    """高德 POI 搜索：取该地点的用户实拍图（name+city 精确命中）。

    高德对中国地标覆盖好、国内可达；Unsplash 缺的中国小景点由它兜底。
    返回 {url, title}；无图/失败返回 None。只能返回 POI 自带 photos 的第一张。
    """
    if not settings.AMAP_API_KEY or not (name or "").strip():
        return None
    params = {
        "key": settings.AMAP_API_KEY,
        "keywords": (name or "").strip(),
        "offset": 5,
        "page": 1,
        "extensions": "all",  # 需要 extensions=all 才会返回 photos
    }
    if city:
        params["city"] = city
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(_POI_URL, params=params, timeout=8)
            resp.raise_for_status()
            data = resp.json()
        pois = (data.get("pois") or []) if data.get("status") == "1" else []
        for poi in pois:
            for ph in (poi.get("photos") or []):
                url = (ph or {}).get("url")
                if url:
                    return {"url": url, "title": (ph or {}).get("title") or (poi.get("name") or "")}
    except Exception:
        return None
    return None