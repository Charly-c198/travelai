"""RollingGo（道旅）MCP 客户端：酒店查询。

经实测该 MCP 走标准 JSON-RPC over HTTP（streamable），无强制 session-id。
直接用 httpx 发 JSON-RPC 更稳（避开 mcp SDK 的 WouldBlock 兼容问题）。
对外：
- search_hotels(place, ...) → 酒店候选 + 可追踪 bookingUrl
- get_hotel_detail(hotel_id, ...) → 单酒店房型/价格
- get_hotel_search_tags() → 搜索标签元数据
- list_tools() → 服务器工具清单（用于探索）
"""
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_HOTEL_URL = settings.ROLLINGGO_HOTEL_MCP_URL
_FLIGHT_URL = settings.ROLLINGGO_FLIGHT_MCP_URL

_INIT = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "travelai-backend", "version": "1.0"},
    },
}


def _headers(url: str, key: Optional[str]) -> dict:
    h = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


async def _rpc_tool(url: str, key: Optional[str], name: str, arguments: Dict[str, Any]) -> Any:
    """打开一个连接：initialize → 调用工具 → 解析实际业务返回（result.content[0].text 为 JSON 字符串）。"""
    async with httpx.AsyncClient(headers=_headers(url, key), timeout=30) as c:
        await c.post(url, json=_INIT)
        r = await c.post(
            url,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                  "params": {"name": name, "arguments": arguments or {}}},
        )
        r.raise_for_status()
        envelope = r.json()
    result = envelope.get("result") or {}
    if result.get("isError"):
        raise RuntimeError(f"RollingGo 工具执行失败: {envelope}")
    content = result.get("content") or []
    text = "\n".join(c.get("text", "") for c in content if c.get("type") == "text")
    try:
        return json.loads(text)
    except Exception:
        return {"raw": text}


async def list_tools(url: Optional[str] = None, key: Optional[str] = None) -> List[Dict[str, Any]]:
    url = url or _HOTEL_URL
    key = key or settings.ROLLINGGO_API_KEY
    async with httpx.AsyncClient(headers=_headers(url, key), timeout=20) as c:
        await c.post(url, json=_INIT)
        r = await c.post(url, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        tools = ((r.json().get("result") or {}).get("tools")) or []
        return [
            {"name": t.get("name"), "description": (t.get("description") or "")[:120],
             "schema": t.get("inputSchema") or {}}
            for t in tools
        ]


async def get_hotel_search_tags(key: Optional[str] = None) -> Any:
    return await _rpc_tool(_HOTEL_URL, key or settings.ROLLINGGO_API_KEY, "getHotelSearchTags", {})


async def search_hotels(
    place: str,
    place_type: str = "city",
    origin_query: Optional[str] = None,
    size: int = 10,
    key: Optional[str] = None,
) -> Dict[str, Any]:
    """搜索酒店。返回 RollingGo 原始业务体（含 hotelInformationList + bookingUrl）。"""
    args = {
        "originQuery": origin_query or place,
        "place": place,
        "placeType": place_type,
        "size": size,
    }
    data = await _rpc_tool(_HOTEL_URL, key or settings.ROLLINGGO_API_KEY, "searchHotels", args)
    hotels = data.get("hotelInformationList") or []
    return {"success": data.get("success"), "code": data.get("code"),
            "message": data.get("message"), "hotels": hotels}


async def get_hotel_detail(hotel_id, arguments: Optional[Dict[str, Any]] = None, key: Optional[str] = None) -> Any:
    args = dict(arguments or {})
    args.setdefault("hotelId", hotel_id)
    return await _rpc_tool(_HOTEL_URL, key or settings.ROLLINGGO_API_KEY, "getHotelDetail", args)