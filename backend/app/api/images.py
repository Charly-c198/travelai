"""目的地动态配图代理：转发到 Unsplash（key 存服务端），下发压缩图 + 署名。

中文地点名会先尝试用 `spots` 表的英文名(name_en)解析——Unsplash 对中文标签匹配差，
英文名可精确命中对应地标（历史行程的 spots 未带 name_en 时，这一层兜底也覆盖）。"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.spot import Spot
from app.models.user import User
from app.services.unsplash import search_city_image, scope_query, llm_english_query
from app.services.amap_service import poi_photo
from app.services import wikipedia
from app.utils.auth import get_current_user

settings = get_settings()

router = APIRouter(prefix="/api/v1/images", tags=["Images"])


async def _resolve_query(db: AsyncSession, q: str) -> str:
    """中文地点名 → spots 表英文名（精确/包含匹配）；英文或未命中则原样返回。"""
    q = (q or "").strip()
    if not q:
        return q
    # 已含英文字母的直接用（前端可能已传 name_en）
    if not any("一" <= ch <= "鿿" for ch in q):
        return q
    try:
        # 精确匹配优先，其次包含匹配
        for cond in (Spot.name == q, Spot.name.contains(q)):
            row = (await db.execute(select(Spot.name_en).where(cond).limit(1))).scalar_one_or_none()
            if row:
                return row
    except Exception:
        pass
    return q


@router.get("")
async def image(
    q: str = Query(..., description="城市/目的地（中文或英文）"),
    city: Optional[str] = Query(None, description="兜底城市：地点本身搜不到图时用它（如 大鹏所城→深圳）"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回该目的地的一张可商用配图（压缩 WebP）及摄影师署名。未命中/无key→source=none。"""
    query = await _resolve_query(db, q)
    hit = await search_city_image(query)
    # 地点搜不到图 → 城市兜底（保证照片至少区域正确，绝不串成别处的图）
    if not hit and city:
        cq = await _resolve_query(db, city)
        hit = await search_city_image(cq)
    if not hit:
        return {"source": "none", "url": None, "credit": None}
    return {"source": "unsplash", "url": hit["url"], "credit": hit.get("credit")}


@router.get("/spot")
async def spot_image(
    name: str = Query(..., description="景点名（中文或英文）"),
    name_en: Optional[str] = Query(None, description="英文名（优先用于文本搜索/Unsplash 锚定）"),
    city: Optional[str] = Query(None, description="所在城市（锚定搜索，杜绝跨城串图）"),
    lat: Optional[float] = Query(None, description="纬度（实体 geosearch 锚定）"),
    lng: Optional[float] = Query(None, description="经度"),
    current_user: User = Depends(get_current_user),
):
    """单景点配图（China 可达的实体级解析）。

    优先级链（逐级降级）：
      1) Wikipedia 实体（可选，config WIKIPEDIA_ENABLED；大陆被墙默认关）→ 权威主图
      2) Qwen 消歧中文景点名 → 精确英文搜索词（含城市）→ Unsplash（主路径，防跨城串图）
      3) Unsplash 城市锚定：'{name_en/中文名} {城市英文名}' 兜底
      4) Unsplash 城市兜底（保证照片至少区域正确）
      5) source=none → 前端本地兜底
    """
    # 1) Wikipedia 实体级（海外/代理环境可开）
    if settings.WIKIPEDIA_ENABLED:
        hit = await wikipedia.resolve_spot_image(name, name_en or "", city or "", lat, lng)
        if hit:
            return hit
    # 2) Qwen 消歧 → 精确英文搜索词 → Unsplash
    q = await llm_english_query(name, name_en or "", city or "")
    used = q
    hit = await search_city_image(q) if q else None
    # 3) 高德 POI 实拍图（中国可达；覆盖 Unsplash 缺的中国小景点，如西安回民街）
    if not hit:
        amap = await poi_photo(name, city or "")
        if amap:
            return {"source": "amap", "url": amap["url"],
                    "credit": amap.get("title") or name, "query": name}
    # 4) 城市锚定兜底（q 为空或与锚定结果不同时再试）
    scoped = scope_query(name_en or name or "", city or "") if not hit else ""
    if scoped and scoped != q:
        hit = await search_city_image(scoped)
        used = scoped
    # 5) 城市兜底
    if not hit and city:
        hit = await search_city_image(city)
        used = city
    if not hit:
        return {"source": "none", "url": None, "credit": None}
    return {"source": "unsplash", "url": hit["url"], "credit": hit.get("credit"), "query": used}
