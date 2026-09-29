"""Unsplash 动态配图服务：按目的地搜索返回压缩图 + 摄影师署名。

- key 只存服务端（config.UNSPLASH_API_KEY），经 /api/v1/images 代理下发。
- 用 Unsplash CDN 的 urls.regular（已按需压缩优化），不落原始大图。
- 内存缓存（按查询词，TTL 1 天）：同一目的地不重复计 API 配额。
- 任何失败降级为 source=none，前端走本地兜底。

搜索词策略（Unsplash 对中文标签匹配差，英文命中率高得多，按优先级）：
  1) 中文城市映射表 _QUERY_MAP（常见城市 → 英文，离线、零依赖）；
  2) 城市名包含/被包含匹配（如"广州塔"→ Guangzhou）；
  3) 其余中文名用 MyMemory 免费翻译成英文（带缓存，失败回退原文）。
"""
import logging
import re
import time
from typing import Optional, Dict

import httpx

from app.config import get_settings

settings = get_settings()

_SEARCH_URL = "https://api.unsplash.com/search/photos"
_TRANSLATE_URL = "https://api.mymemory.translated.net/get"

# 中文目的地 → Unsplash 英文搜索词（英文城市名命中率高得多）
_QUERY_MAP: Dict[str, str] = {
    # 国内
    "北京": "Beijing", "上海": "Shanghai", "天津": "Tianjin", "重庆": "Chongqing",
    "深圳": "Shenzhen", "厦门": "Xiamen", "南京": "Nanjing", "苏州": "Suzhou",
    "无锡": "Wuxi", "扬州": "Yangzhou", "杭州": "Hangzhou", "宁波": "Ningbo",
    "福州": "Fuzhou", "泉州": "Quanzhou", "长沙": "Changsha", "武汉": "Wuhan",
    "郑州": "Zhengzhou", "济南": "Jinan", "青岛": "Qingdao", "烟台": "Yantai",
    "威海": "Weihai", "大连": "Dalian", "沈阳": "Shenyang", "哈尔滨": "Harbin",
    "兰州": "Lanzhou", "西宁": "Xining", "乌鲁木齐": "Urumqi", "呼和浩特": "Hohhot",
    "南宁": "Nanning", "桂林": "Guilin", "阳朔": "Yangshuo", "张家界": "Zhangjiajie",
    "凤凰古城": "Fenghuang Ancient Town", "贵阳": "Guiyang", "昆明": "Kunming Yunnan",
    "大理": "Dali Yunnan", "丽江": "Lijiang Yunnan", "香格里拉": "Shangri-La Yunnan",
    "成都": "Chengdu", "九寨沟": "Jiuzhaigou Valley", "拉萨": "Lhasa Tibet",
    "敦煌": "Dunhuang", "莫高窟": "Mogao Caves", "嘉峪关": "Jiayuguan",
    "西安": "Xian Terracotta", "华山": "Mount Hua", "泰山": "Mount Tai",
    "黄山": "Mount Huangshan", "三亚": "Sanya", "海口": "Haikou", "珠海": "Zhuhai",
    "澳门": "Macau", "香港": "Hong Kong", "台北": "Taipei", "高雄": "Kaohsiung",
    "广州": "Guangzhou", "开封": "Kaifeng", "洛阳": "Luoyang",
    # 东亚
    "东京": "Tokyo Japan", "大阪": "Osaka Japan", "京都": "Kyoto Japan",
    "奈良": "Nara Japan", "神户": "Kobe Japan", "名古屋": "Nagoya",
    "福冈": "Fukuoka", "札幌": "Sapporo", "冲绳": "Okinawa",
    "首尔": "Seoul", "釜山": "Busan", "济州岛": "Jeju Island",
    # 东南亚 / 南亚
    "曼谷": "Bangkok Thailand", "清迈": "Chiang Mai Thailand",
    "普吉岛": "Phuket Thailand", "芭提雅": "Pattaya", "甲米": "Krabi",
    "苏梅岛": "Koh Samui", "新加坡": "Singapore", "吉隆坡": "Kuala Lumpur",
    "马六甲": "Malacca", "胡志明": "Ho Chi Minh City", "河内": "Hanoi",
    "岘港": "Da Nang", "巴厘岛": "Bali Indonesia", "马尔代夫": "Maldives",
    "尼泊尔": "Nepal Himalaya", "斯里兰卡": "Sri Lanka", "柬埔寨": "Angkor Cambodia",
    "吴哥窟": "Angkor Wat",
    # 欧洲
    "巴黎": "Paris France", "伦敦": "London UK", "罗马": "Rome Italy",
    "米兰": "Milan Italy", "威尼斯": "Venice Italy", "佛罗伦萨": "Florence Italy",
    "马德里": "Madrid Spain", "巴塞罗那": "Barcelona Spain",
    "里斯本": "Lisbon Portugal", "阿姆斯特丹": "Amsterdam", "柏林": "Berlin",
    "慕尼黑": "Munich", "维也纳": "Vienna", "布拉格": "Prague",
    "布达佩斯": "Budapest", "苏黎世": "Zurich", "日内瓦": "Geneva",
    "曼彻斯特": "Manchester", "爱丁堡": "Edinburgh", "伊斯坦布尔": "Istanbul",
    "莫斯科": "Moscow", "圣彼得堡": "Saint Petersburg", "圣托里尼": "Santorini Greece",
    "希腊": "Santorini Greece", "瑞士": "Switzerland Alps", "冰岛": "Iceland landscape",
    "挪威": "Norway fjord", "土耳其": "Turkey Cappadocia",
    # 美洲 / 大洋洲 / 非洲 / 中东
    "纽约": "New York City", "旧金山": "San Francisco", "洛杉矶": "Los Angeles",
    "拉斯维加斯": "Las Vegas", "芝加哥": "Chicago", "波士顿": "Boston",
    "华盛顿": "Washington DC", "西雅图": "Seattle", "多伦多": "Toronto",
    "温哥华": "Vancouver", "悉尼": "Sydney Australia", "墨尔本": "Melbourne",
    "黄金海岸": "Gold Coast Australia", "奥克兰": "Auckland", "皇后镇": "Queenstown",
    "迪拜": "Dubai", "阿布扎比": "Abu Dhabi", "开罗": "Cairo Egypt",
    "摩洛哥": "Morocco", "埃及": "Egypt pyramids", "肯尼亚": "Kenya safari",
}
_DEFAULT_SEARCH = "scenic travel destination landscape"

_cache: Dict[str, Dict] = {}
_TTL = 86400  # 1 天
_trans_cache: Dict[str, str] = {}  # 中文→英文 翻译缓存


async def _translate_zh(q: str) -> str:
    """MyMemory 免费翻译 zh→en（带缓存 + 失败回退原文）。"""
    if q in _trans_cache:
        return _trans_cache[q]
    try:
        async with httpx.AsyncClient(timeout=6) as c:
            r = await c.get(_TRANSLATE_URL, params={"q": q, "langpair": "zh|en"})
            r.raise_for_status()
            out = (r.json().get("responseData") or {}).get("translatedText") or ""
        out = re.sub(r"<[^>]+>", " ", out)
        out = re.sub(r"&quot;|&#39;|&amp;|&lt;|&gt;", " ", out).strip()
        # 免费额度告警/空结果 → 视为失败
        if not out or "MYMEMORY" in out.upper() or out == q:
            return q
        _trans_cache[q] = out
        return out
    except Exception:
        return q


def scope_query(q: str, city: str) -> str:
    """把地点查询锚定到城市：`{q} {城市英文名首词}`，杜绝跨城串图。

    例如 q="Muslim Quarter"、city="西安" → "Muslim Quarter Xian"（只取首词，不带
    "Terracotta" 等描述符）。q 已含城市英文（如 "Dali Yunnan"）则不再追加。
    """
    q = (q or "").strip()
    if not city:
        return q
    city_en = _QUERY_MAP.get(city.strip())
    if not city_en:
        return q
    city_word = city_en.split()[0].lower()
    if city_word and city_word in q.lower():
        return q
    return f"{q} {city_en.split()[0]}".strip()


_llm_cache: Dict[str, str] = {}


logger = logging.getLogger(__name__)


def _valid_llm_out(out: str, en: str) -> bool:
    """校验 LLM 搜索词：非空、非中文；给了 name_en 时须包含其显著词（防替换成别景）。"""
    out = (out or "").strip()
    if not out or any("一" <= ch <= "鿿" for ch in out):
        return False
    if en:
        en_words = [w for w in re.split(r"[^a-zA-Z]+", en.lower()) if len(w) >= 3]
        if en_words and not any(w in out.lower() for w in en_words):
            return False
    return True


async def _llm_once(prompt: str) -> str:
    try:
        from app.llm.client import get_llm_client
        resp = await get_llm_client().ainvoke(prompt)
        return re.sub(r"[\"'。.，,；;：:！!？?]", "", (resp.content or "").strip()).strip()
    except Exception:
        return ""


async def llm_english_query(name: str, name_en: str = "", city: str = "") -> str:
    """用 Qwen 把中文景点名消歧为精确英文搜索词（含城市），供 Unsplash 精确搜图。

    - name_en 已含城市英文提示（如 "Dali Yunnan"）→ 已消歧，直接用，省一次 LLM 调用。
    - 输出被校验拒绝（空/中文/替换成别景）→ 纠错重试一次（明确要求保留 name_en）。
    - 结果内存缓存（按 name+city）：同景点不重复计 LLM/Unsplash 配额。
    - 仍失败 → 返回空串，调用方走 scope_query/城市兜底。
    """
    n = (name or "").strip()
    if not n:
        return ""
    city_en = (_QUERY_MAP.get((city or "").strip()) or "").lower()
    en = (name_en or "").strip()
    if en and city_en:
        first = city_en.split()[0] if city_en.split() else city_en
        if first and first in en.lower():
            return en  # 已含城市 → 直接当搜索词
    key = f"{n}||{(city or '').strip()}"
    if key in _llm_cache:
        return _llm_cache[key]
    prompt = (
        "你是旅游图片搜索助手。把下面的具体地点转成能在英文图片库(如 Unsplash)精确搜到"
        "该地点照片的英文搜索词。\n"
        "硬性要求：\n"
        "1. 必须保留具体地点本身，只做翻译/加城市限定；\n"
        "2. 不要替换成该城市的其他著名景点（如地点是回民街，绝不能输出兵马俑）；\n"
        "3. 必须包含城市英文名以区分同名地点；\n"
        "4. 只输出搜索词本身，不要解释、引号、标点。\n"
        "示例：\n"
        "地点：西湖 城市：杭州 → Hangzhou West Lake\n"
        "地点：洪崖洞 城市：重庆 → Chongqing Hongya Cave\n"
        f"地点：{n} 城市：{city or '未知'}"
        + (f" 参考英文名：{en}" if en else "")
        + "\n→ "
    )
    out = await _llm_once(prompt)
    if not _valid_llm_out(out, en):
        logger.warning("Qwen 消歧被拒(%s/%s): %r → 纠错重试", n, city, (out or "")[:60])
        retry = (
            f"你上一个答案是「{out or '(空)'}」，被判定为不属于该地点、或是替换成了城市的"
            f"其他景点。请重新输出英文搜索词：必须保留原地点（参考英文名「{en}」的主要词语"
            "），再补上城市英文名；只输出搜索词本身。"
            f"\n地点：{n} 城市：{city or '未知'}"
        )
        out = await _llm_once(retry)
    if _valid_llm_out(out, en) and out:
        _llm_cache[key] = out
        return out
    return ""


async def _to_query(q: str) -> str:
    q = (q or "").strip()
    if not q:
        return _DEFAULT_SEARCH
    if q in _QUERY_MAP:
        return _QUERY_MAP[q]
    for zh, en in _QUERY_MAP.items():
        if zh in q or q in zh:
            return en
    # 不在城市映射(冷门地/具体景点)：先翻译成英文，Unsplash 命中率高得多。
    # 注意：不再维护"按景点的人工映射表"（那是对特定城市的定制，无法覆盖全部，且不一致）。
    if any("一" <= ch <= "鿿" for ch in q):
        return await _translate_zh(q)
    return q


async def search_city_image(q: str) -> Optional[Dict]:
    """返回 {url, credit, credit_url}；失败/空/无 key 返回 None。"""
    key = settings.UNSPLASH_API_KEY
    if not key:
        return None
    query = await _to_query(q)
    now = time.time()
    hit = _cache.get(query)
    if hit and (now - hit["ts"]) < _TTL:
        return {k: v for k, v in hit.items() if k != "ts"}
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(_SEARCH_URL, params={
                "query": query, "per_page": 1,
                "orientation": "landscape", "client_id": key,
            })
            r.raise_for_status()
            data = r.json()
        res = ((data.get("results") or []) + (data.get("photos") or []))
        if not res:
            return None
        first = res[0]
        urls = first.get("urls") or {}
        out = {
            "url": urls.get("regular") or urls.get("small"),
            "credit": (first.get("user") or {}).get("name") or "",
            "credit_url": ((first.get("user") or {}).get("links") or {}).get("html") or "",
        }
        if not out["url"]:
            return None
        out["ts"] = now
        _cache[query] = out
        return {k: v for k, v in out.items() if k != "ts"}
    except Exception:
        return None