"""Wikipedia 实体配图服务：按坐标/名称解析景点实体，拿权威主图。

方案B（实体级精确解析）：
- geosearch：按景点真实坐标找最近 Wikipedia 页面（天然消歧，无 SPARQL 限流/多义坑）。
- page/summary：取页面主图 thumbnail（Wikimedia CDN 压缩图）+ 页面链接。
- 许可校验：extmetadata.LicenseShortName 白名单（CC/PD/OGL/GFDL/Attribution），拒 fair-use。
- 词元重合校验：geosearch 路径必须验证页面标题与景点名有显著词元重合（防垃圾坐标串图）。
- 失败全部返回 None，调用方沿链降级（Unsplash 城市锚定 → 城市兜底 → 本地）。

Wikimedia 强制要求自定义 User-Agent，缺失会 403。
"""
import re
import time
from typing import Dict, Optional, Tuple
from urllib.parse import quote, unquote

import httpx

_ACTION_API = "https://{lang}.wikipedia.org/w/api.php"
_SUMMARY = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
_UA = "TravelAI/1.0 (travel-planning demo; contact: dev@example.com)"
_TIMEOUT = 4  # 短超时：大陆不可达时快速失败，不拖慢主链路（LLM 消歧 → Unsplash）

# 许可：明确非自由（fair-use/商标/logo 等）拒绝；其余宽松放行（CC/PD/OGL/GFDL/Attribution）
_LICENSE_BAD = re.compile(r"fair\s*use|non-?free|logo|trademark|proprietary", re.IGNORECASE)

_cache: Dict[Tuple[str, str], dict] = {}
_TTL = 86400  # 1 天


def _lang_for(name: str) -> str:
    """含中文字符 → zh.wikipedia（中国地标覆盖好）；否则 en。"""
    return "zh" if any("一" <= ch <= "鿿" for ch in (name or "")) else "en"


def _file_title_from_url(url: str) -> str:
    """从 Wikimedia 图片 URL 还原 File: 标题。

    直接链接末段即文件名；缩略图（/thumb/.../<尺寸>px-xxx）需先剥掉尺寸段，
    否则会得到非法的 "File:220px-xxx.jpg"。
    """
    u = re.sub(r"/\d+px-[^/]+$", "", url or "")
    segs = [s for s in u.rstrip("/").split("/") if s]
    return unquote(segs[-1]) if segs else ""


def _norm(s: str) -> str:
    return re.sub(r"[\s_，。、（）()\-—|｜:：·【】/\\\"'`]+", "", s or "").lower()


def title_matches(title: str, name: str, name_en: str = "", city: str = "") -> bool:
    """页面标题与景点名/城市有显著词元（≥2字符）重合才通过。"""
    t = _norm(title)
    if not t:
        return False
    for cand in (name, name_en, city):
        n = _norm(cand)
        if not n:
            continue
        if 2 <= len(n) <= 40 and (n in t or t in n):
            return True
        # 英文多词（如 "muslim quarter"）拆词匹配
        for tok in re.split(r"[^一-鿿]+", n):
            if len(tok) >= 3 and tok in t:
                return True
    return False


async def _get(url: str, params: dict) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers={"User-Agent": _UA}) as c:
            r = await c.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except Exception:  # noqa: BLE001
        return None


async def geosearch_titles(lat: float, lng: float, lang: str, radius: int = 1200,
                           limit: int = 5) -> list[str]:
    """坐标 → 附近页面标题（按距离升序，最多 limit 个）。"""
    data = await _get(_ACTION_API.format(lang=lang), {
        "action": "query", "list": "geosearch",
        "gscoord": f"{lat}|{lng}", "gsradius": radius, "gslimit": limit, "format": "json",
    })
    results = ((data or {}).get("query") or {}).get("geosearch") or []
    return [r.get("title") for r in results if r.get("title")]


async def search_title(query: str, lang: str) -> Optional[str]:
    """文本搜索 → 最佳页面标题。"""
    data = await _get(_ACTION_API.format(lang=lang), {
        "action": "query", "list": "search", "srsearch": query, "srlimit": 1, "format": "json",
    })
    results = ((data or {}).get("query") or {}).get("search") or []
    return results[0].get("title") if results else None


async def page_summary(title: str, lang: str) -> Optional[dict]:
    """页面摘要 → {url, title, page_url}。无图返回 None。"""
    url = _SUMMARY.format(lang=lang, title=quote(title, safe=""))
    data = await _get(url, {})
    if not data:
        return None
    thumb = data.get("thumbnail") or {}
    img_url = thumb.get("source") or (data.get("originalimage") or {}).get("source")
    if not img_url:
        return None
    return {
        "url": img_url,
        "title": data.get("title") or title,
        "page_url": ((data.get("content_urls") or {}).get("desktop") or {}).get("page"),
    }


async def image_license(file_title: str, lang: str) -> Optional[str]:
    """按 File: 名查许可短名；取不到返回 None。"""
    data = await _get(_ACTION_API.format(lang=lang), {
        "action": "query", "titles": file_title,
        "prop": "imageinfo", "iiprop": "extmetadata", "format": "json",
    })
    for p in ((data or {}).get("query") or {}).get("pages") or {}:
        ii = (((data["query"]["pages"].get(p) or {}).get("imageinfo")) or [])
        if ii:
            return ((ii[0].get("extmetadata") or {}).get("LicenseShortName") or {}).get("value")
    return None


async def resolve_spot_image(
    name: str,
    name_en: str = "",
    city: str = "",
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> Optional[dict]:
    """单景点实体解析：返回 {source, url, credit, credit_url, license}；失败 None。

    优先级：1) 坐标 geosearch（带词元校验，防垃圾坐标串图）→ 2) 文本搜索（name+city）。
    """
    key = ((name or "").strip(), (city or "").strip())
    now = time.time()
    hit = _cache.get(key)
    if hit and (now - hit["ts"]) < _TTL:
        return {k: v for k, v in hit.items() if k != "ts"}

    lang = _lang_for(name or name_en or city)
    title: Optional[str] = None
    from_geo = False
    if lat and lng:
        cands = await geosearch_titles(float(lat), float(lng), lang)
        # 两段选择：先要"名字/英文名"匹配的地标页，其次才是城市页（避免只取到城市概览图）
        title = next((c for c in cands if title_matches(c, name, name_en)), None)
        if not title:
            title = next((c for c in cands if title_matches(c, "", "", city)), None)
        from_geo = bool(title)
    if not title:
        q = " ".join(x for x in (name_en or name, city) if (x or "").strip()).strip()
        if q:
            title = await search_title(q, lang)
    if not title:
        out = None
    else:
        info = await page_summary(title, lang)
        if not info:
            out = None
        else:
            fname = _file_title_from_url(info["url"])
            lic = await image_license(f"File:{fname}", lang) if fname else None
            if lic and _LICENSE_BAD.search(lic):
                out = None  # 非自由图（fair-use 等）→ 拒绝，走降级
            else:
                out = {
                    "source": "wikipedia",
                    "url": info["url"],
                    "credit": info["title"],
                    "credit_url": info["page_url"],
                    "license": lic or "",
                    "geo": from_geo,
                }
    if out:
        out["ts"] = now
        _cache[key] = out
        return {k: v for k, v in out.items() if k != "ts"}
    return None
